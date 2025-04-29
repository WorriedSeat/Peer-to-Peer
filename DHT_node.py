from socket import socket, AF_INET, SOCK_DGRAM
from threading import Thread
from hashlib import sha1
from time import time, sleep
from random import random, choice


PARALLEL_REQUESTS = 3 # Requests parallelization
REFRESH_INTERVAL = 30  # Seconds
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
                file_hash = sha1(msg[1]).digest()
                peer_ip, peer_port = msg[2].split(':')
                self.store_peer(file_hash, peer_ip, peer_port)
        except Exception as e:
            # Logs
            print(f"Error handling message from {addr}: {e}")

    # Find nodes closest to a specific node
    def find_closest_nodes(self, target_id, count):
        # Collect all nodes
        all_nodes = []
        for node in self.routing_table.values():
            all_nodes.append((node.id, (node.ip, node.port)))
        
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

    # Periodically refresh routing table
    def refresh(self):
        while self.running:
            sleep(REFRESH_INTERVAL)
            # Refresh a random node
            rnd_node = self.routing_table[choice(self.routing_table.keys())]
            self.find_node(rnd_node.id, (rnd_node.ip, rnd_node.port))


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

    # Clean up
    sleep(5)
    bootstrap.running = False
    node1.running = False
    node2.running = False
    bootstrap.socket.close()
    node1.socket.close()
    node2.socket.close()