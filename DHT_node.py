from socket import socket, AF_INET, SOCK_DGRAM
from threading import Thread
from hashlib import sha1
from time import time, sleep
from random import random, choice


ROUTING_REFRESH_INTERVAL = 1800  # Refreshing routing table
CLEANUP_REFRESH_INTERVAL = 1800 # Refreshing storage
ROUTING_TABLE_SIZE = 10 # Number of records in routing tables


# Info about dht nodes
class DHTNodeInfo:
    def __init__(self, ip, port, distance, id):
        self.ip = ip
        self.port = port
        self.last_seen = time()
        self.distance = distance
        self.id = id
    
    def ping(self):
        self.last_seen = time()


# Info about peers
class PeerInfo:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.last_seen = time()
    
    def ping(self):
        self.last_seen = time()


# DHT node class
class DHTNode:
    def __init__(self, ip, port):
        # Node info
        self.ip = ip
        self.port = port
        self.node_id = sha1(str(random()).encode()).digest() # Random 120 bit id
        # Tables
        self.routing_table = {}  # node_id -> DHTNodeInfo
        self.storage = {}  # file_hash -> [PeerInfo]
        # Socket
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.socket.bind((ip, port))
        self.running = True
        # Logs
        print(f"Node {self.node_id.hex()[:8]} running at {ip}:{port}")
    
    # Stop running dht node
    def shutdown(self): 
        self.running = False
        self.socket.close()
        exit()

    # Kademlia XOR distance measure
    def distance(self, id1, id2):
        return int.from_bytes(bytes(a ^ b for a, b in zip(id1, id2)), 'big')

    # Add node to routing table
    def update_routing_table(self, node_id, ip, port):
        # Check if node is itself
        if node_id == self.node_id:
            return
        # Check if node already exists
        if node_id in self.routing_table:
            self.routing_table[node_id].ping()
            return
        # Add new node if table is not full
        new_node = DHTNodeInfo(ip, port, self.distance(self.node_id, node_id), node_id)
        if len(self.routing_table) < ROUTING_TABLE_SIZE:
            self.routing_table[node_id] = new_node
        else:
            # Replace the oldest node
            last_time = time()
            last_node = None
            for node in self.routing_table.keys():
                if last_time > self.routing_table[node].last_seen:
                    last_time = self.routing_table[node].last_seen
                    last_node = node
            self.routing_table.pop(last_node)
            self.routing_table[node_id] = new_node
    
    # Connect to the dht net using bootstrap node
    def bootstrap(self, bootstrap_nodes):
        for node in bootstrap_nodes:
            self.find_node(self.node_id, node)

    # Start listening for queries and refreshing referencing table
    def start(self):
        Thread(target=self.refresh).start()
        Thread(target=self.listen).start()
    
    # Periodically refresh routing table
    def refresh(self):
        while self.running:
            sleep(ROUTING_REFRESH_INTERVAL)
            # Refresh a random node
            rnd_node = self.routing_table[choice(self.routing_table.keys())]
            self.find_node(rnd_node.id, (rnd_node.ip, rnd_node.port))
    
    # Delete old peers from storage
    def cleanup_storage(self):
        now = time()
        for file_hash in self.storage.keys():
            self.storage[file_hash] = [p for p in self.storage[file_hash] if now - p.last_seen < CLEANUP_REFRESH_INTERVAL]
            if len(self.storage[file_hash]) == 0:
                self.storage.pop(file_hash)

    # Listen for messages
    def listen(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                self.handle_message(data, addr)
            except Exception as e:
                if self.running:
                    # Logs
                    print(f"Error in listener: {e}")

    # Handle incomming message
    def handle_message(self, data, addr):
        try:
            msg = data.decode().split('|')
            if msg[0] == "PING":
                self.socket.sendto(b"PONG", addr)
            elif msg[0] == "FIND_NODE":
                target_id = bytes.fromhex(msg[1])
                sender_id = bytes.fromhex(msg[2])
                self.update_routing_table(sender_id, addr[0], addr[1])
                closest = self.find_closest_nodes(target_id, 3) # 3 - num of closest nodes
                response = "NODES|" + "|".join([f"{nid.hex()}:{ip}:{port}" for nid, (ip, port) in closest])
                self.socket.sendto(response.encode(), addr)
            elif msg[0] == "NODES":
                for node_info in msg[1:]:
                    nid_hex, ip, port = node_info.split(':')
                    nid = bytes.fromhex(nid_hex)
                    self.update_routing_table(nid, ip, port)
            elif msg[0] == "STORE":
                file_hash = bytes.fromhex(msg[1])
                peer_ip, peer_port = msg[2].split(':')
                self.store_peer(file_hash, peer_ip, peer_port)
            elif msg[0] == "FIND_PEERS":
                file_hash = bytes.fromhex(msg[1])
                sender_id = bytes.fromhex(msg[2])
                self.update_routing_table(sender_id, addr[0], addr[1])
                peers = self.get_peers(file_hash)
                if len(peers) > 0:
                    response = "PEERS|" + file_hash.hex() + "|" + "|".join([f"{p.ip}:{p.port}" for p in peers])
                else:
                    closest = self.find_closest_nodes(file_hash, 3)  # 3 - num of closest nodes
                    response = "NODES|" + "|".join([f"{nid.hex()}:{ip}:{port}" for nid, (ip, port) in closest])
                self.socket.sendto(response.encode(), addr)
            elif msg[0] == "PEERS":
                file_hash = bytes.fromhex(msg[1])
                for p in msg[2:]:
                    peer_ip, peer_port = p.split(':')
                    self.store_peer(file_hash, peer_ip, peer_port)
        except Exception as e:
            # Logs
            print(f"Error handling message from {addr}: {e}")

    # Find nodes closest to a specific node
    def find_closest_nodes(self, target_id, count):
        # Collect all nodes
        all_nodes = []
        for n in self.routing_table.keys():
            node = self.routing_table[n]
            all_nodes.append((node.id, (node.ip, int(node.port))))
        
        # Include self in candidates
        all_nodes.append((self.node_id, (self.ip, self.port)))
        
        # Sort by distance to target
        all_nodes.sort(key=lambda x: self.distance(x[0], target_id))
        return all_nodes[:count]

    # Query a node to find closest nodes to target
    def find_node(self, target_id, addr):
        self.socket.sendto(f"FIND_NODE|{target_id.hex()}|{self.node_id.hex()}".encode(), addr)

    # Update or add peer info:
    def store_peer(self, file_hash, ip, port):
        if file_hash in self.storage:
            for p in self.storage[file_hash]:
                if p.ip == ip and p.port == port:
                    p.ping()
                    return
        else:
            self.storage[file_hash] = []
        self.storage[file_hash].append(PeerInfo(ip, port))

    # Get peers for a specific file
    def get_peers(self, file_hash):
        self.cleanup_storage()
        if file_hash in self.storage:
            return self.storage[file_hash]
        else:
            return []
    
    # DHT Lookup
    def find_peers(self, file_name):
        file_hash = sha1(file_name.encode()).digest()
        contacted = set()
        while True:
            new_messages = 0
            closest_nodes = self.find_closest_nodes(file_hash, 3)
            for node_id, addr in closest_nodes:
                if addr not in contacted:
                    self.socket.sendto(f"FIND_PEERS|{file_hash.hex()}|{self.node_id.hex()}".encode(), addr)
                    contacted.add(addr)
                    new_messages += 1
            if new_messages == 0:
                break
            sleep(2)
        
        peers = []
        if file_hash in self.storage: 
            for p in self.storage[file_hash]:
                peers.append((p.ip, p.port))
        return peers

    # Announce a new peer for a file
    def announce_peer(self, file_name, ip, port):
        file_hash = sha1(file_name.encode()).digest()
        # Find closest nodes
        while True:
            new_messages = 0
            closest_nodes = self.find_closest_nodes(file_hash, 3)
            for node_id, addr in closest_nodes:
                if node_id not in self.routing_table and node_id != self.node_id:
                    self.find_node(file_hash, addr)
                    new_messages += 1
            if new_messages == 0:
                break
            sleep(2)
        # Send store message
        for node in self.find_closest_nodes(file_hash, 3):
            self.socket.sendto(f"STORE|{file_hash.hex()}|{ip}:{port}".encode(), node[1])


# --- Example Usage ---
if __name__ == "__main__":
    # Start bootstrap nodes
    bootstrap1 = DHTNode("127.0.0.1", 6881)
    bootstrap1.start()

    bootstrap2 = DHTNode("127.0.0.1", 6882)
    bootstrap2.start()
    bootstrap2.bootstrap((("127.0.0.1", 6881),))


    # Start regular nodes
    node1 = DHTNode("127.0.0.1", 6883)
    node1.start()
    node1.bootstrap((("127.0.0.1", 6881),))

    node2 = DHTNode("127.0.0.1", 6884)
    node2.start()
    node2.bootstrap((("127.0.0.1", 6881),))

    node3 = DHTNode("127.0.0.1", 6885)
    node3.start()
    node3.bootstrap((("127.0.0.1", 6882),))

    node4 = DHTNode("127.0.0.1", 6886)
    node4.start()
    node4.bootstrap((("127.0.0.1", 6882),))

    # Let them discover each other
    sleep(2)
    
    # Announcing peers
    node1.announce_peer("file_name", "127.0.0.1", "1")
    node4.announce_peer("file_name", "127.0.0.1", "2")

    sleep(2)
    
    # Find peers for file
    print("\nNode finds file 'file_name'")
    print(node4.find_peers("file_name"))

    # Clean up
    bootstrap1.shutdown()
    bootstrap2.shutdown()
    node1.shutdown()
    node2.shutdown()
    node3.shutdown()
    node4.shutdown()