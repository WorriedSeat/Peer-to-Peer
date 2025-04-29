from socket import socket, AF_INET, SOCK_DGRAM
from threading import Thread
from hashlib import sha1
from time import time, sleep
from random import random, choice


PARALLEL_REQUESTS = 3 # Requests parallelization
ROUTING_REFRESH_INTERVAL = 1800  # Refreshing routing table
ROUTING_TABLE_SIZE = 10 # Number of records in routing tables
CLEANUP_REFRESH_INTERVAL = 1800 # Refreshing storage


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
            last_time = time()
            last_node = None
            for node in self.routing_table.keys():
                if last_time > self.routing_table[node].last_seen:
                    last_time = self.routing_table[node].last_seen
                    last_node = node
            self.routing_table.pop(last_node)
            self.routing_table[node_id] = new_node

    # Start listening for queries and refreshing referencing table
    def start(self):
        Thread(target=self.listen).start()
        Thread(target=self.refresh).start()

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
                # print("Find node", self.port)
                target_id = bytes.fromhex(msg[1])
                sender_id = bytes.fromhex(msg[2])
                self.update_routing_table(sender_id, addr[0], addr[1])
                closest = self.find_closest_nodes(target_id, 3) # 3 - num of closest nodes
                response = "NODES|" + "|".join([f"{nid.hex()}:{ip}:{port}" for nid, (ip, port) in closest])
                self.socket.sendto(response.encode(), addr)
            elif msg[0] == "NODES":
                # print("Nodes", self.port)
                for node_info in msg[1:]:
                    nid_hex, ip, port = node_info.split(':')
                    nid = bytes.fromhex(nid_hex)
                    self.update_routing_table(nid, ip, port)
            elif msg[0] == "STORE":
                # print("Store", self.port)
                file_hash = bytes.fromhex(msg[1])
                peer_ip, peer_port = msg[2].split(':')
                self.store_peer(file_hash, peer_ip, peer_port)
            elif msg[0] == "FIND_PEERS":
                # print("Find Peers", self.port)
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
                # print("Peers", self.port)
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

    # Connect to the dht net using bootstrap node
    def bootstrap(self, bootstrap_nodes):
        for node in bootstrap_nodes:
            self.find_node(self.node_id, node)

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

    def get_peers(self, file_hash):
        self.cleanup_storage()
        if file_hash in self.storage:
            return self.storage[file_hash]
        else:
            return []

    def cleanup_storage(self):
        now = time()
        for file_hash in self.storage.keys():
            self.storage[file_hash] = [p for p in self.storage[file_hash] if now - p.last_seen < CLEANUP_REFRESH_INTERVAL]
            if len(self.storage[file_hash]) == 0:
                self.storage.pop(file_hash)
    
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
                    msg = f"FIND_PEERS|{file_hash.hex()}|{self.node_id.hex()}".split("|")
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

    def announce_peer(self, file_name, ip, port):
        file_hash = sha1(file_name.encode()).digest()
        for node in self.find_closest_nodes(file_hash, 3):
            self.socket.sendto(f"STORE|{file_hash.hex()}|{ip}:{port}".encode(), node[1])

    # Periodically refresh routing table
    def refresh(self):
        while self.running:
            sleep(ROUTING_REFRESH_INTERVAL)
            # Refresh a random node
            rnd_node = self.routing_table[choice(self.routing_table.keys())]
            self.find_node(rnd_node.id, (rnd_node.ip, rnd_node.port))
    
    # Stop running of dht node
    def shutdown(self): 
        self.running = False
        self.socket.close()

# --- Example Usage ---
if __name__ == "__main__":
    # Start bootstrap node
    bootstrap = DHTNode("127.0.0.1", 6881)
    bootstrap.start()

    # Start regular nodes
    node1 = DHTNode("127.0.0.1", 6882)
    node1.start()
    node1.bootstrap((("127.0.0.1", 6881),))

    node2 = DHTNode("127.0.0.1", 6883)
    node2.start()
    node2.bootstrap((("127.0.0.1", 6881),))

    # Let them discover each other
    sleep(5)

    # Now they should know about each other
    print("\nBootstrap node knows about:")
    for n in bootstrap.routing_table.keys():
        node = bootstrap.routing_table[n]
        print(f"- {node.id.hex()[:8]} at {node.ip}:{node.port}")

    print("\nNode1 knows about:")
    for n in node1.routing_table.keys():
        node = node1.routing_table[n]
        print(f"- {node.id.hex()[:8]} at {node.ip}:{node.port}")
    
    print("\nNode2 knows about:")
    for n in node2.routing_table.keys():
        node = node2.routing_table[n]
        print(f"- {node.id.hex()[:8]} at {node.ip}:{node.port}")
    
    # Announcing peers
    node2.announce_peer("file_name", "127.0.0.1", "6884")
    node1.announce_peer("file_name2", "127.0.0.1", "6885")

    sleep(5)

    # Now what files they know
    print("\nBootstrap node knows about:")
    for s in bootstrap.storage.keys():
        print(s.hex())
        for i in bootstrap.storage[s]:
            print(f"- {i.ip}:{i.port}")

    print("\nNode1 knows about:")
    for s in node1.storage.keys():
        print(s.hex())
        for i in node1.storage[s]:
            print(f"- {i.ip}:{i.port}")
    
    print("\nNode2 knows about:")
    for s in node2.storage.keys():
        print(s.hex())
        for i in node2.storage[s]:
            print(f"- {i.ip}:{i.port}")
    
    # Find peers for file 2
    print("\nNode1 finds file 'file_name2'")
    print(node1.find_peers("file_name2"))

    # Clean up
    sleep(5)
    bootstrap.shutdown()
    node1.shutdown()
    node2.shutdown()