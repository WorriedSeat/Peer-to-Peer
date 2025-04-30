import socket
import os
import threading
from random import randint
import argparse
import math
from progress.bar import FillingSquaresBar
from datetime import datetime
import DHT_node
import sys

IP = "0.0.0.0"
MSS = 1024
PACKET_SIZE = MSS
PACKETS_PER_BATCH = 10

WELL_KNOWN_NODES_PORTS = [6881, 6882]

log_lock = threading.Lock()

packet_map_lock = threading.Lock()
packet_map = {}

def log_time():
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")

class Peer:
    def __init__(self, port: int, dht_port: int):
        self.port = port
        self.address = IP+':'+str(port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((IP, port))
        self.files_size = {}
        
        self.node = DHT_node.DHTNode(IP, dht_port)
        self.node.start()
        self.node.bootstrap(self.get_dht())
                
        with log_lock:
            with open('./log_file.txt', 'a') as log_file:
                log_file.write(f"[{log_time()}] Peer {self.address} Connected\n")
                log_file.write(f"[{log_time()}] Peer {self.address} Created node {self.node.ip}:{self.node.port}\n")
        
        if os.path.isdir('./'+self.address):
            all_file_names = os.listdir('./'+self.address)
            for file in all_file_names:
                if not os.path.isdir('./'+self.address+'/'+file):
                    
                    with log_lock:
                        with open('./log_file.txt', 'a') as log_file:
                            log_file.write(f"[{log_time()}] Peer {self.address} Announced {file}\n")
                    
                    self.node.announce_peer(file, IP, port)
    
    def get_dht(self):
        parsed_addr = []
        try:
            with open("./well_known_nodes.txt", "r") as file:
                actual_dht = []
                actual_dht = file.read().splitlines()
                for dht_addr in actual_dht:
                    ip, port = dht_addr[1:-1].split(',')
                    dht_addr = (ip[1:-1], int(port[1:]))
                    parsed_addr.append(dht_addr)

        except Exception as e:
            with log_lock:
                with open('./log_file.txt', 'a') as log_file:
                    log_file.write(f"[{log_time()}] Peer {self.address} Error: {e}\n")
                
            print(f"Error in get_dht {e}")
        
        return parsed_addr
    
    def get_file_size(self, peers: list, filename: str):
        file_size = -1
        counter = 0
        while (file_size == -1):
            peer_ip, peer_port = peers[randint(0, len(peers) - 1)]
            peer_port = int(peer_port)
            request = f"size|{filename}".encode()
            self.socket.sendto(request, (peer_ip, peer_port))
            
            data, _ = self.socket.recvfrom(PACKET_SIZE)
            if (data):
                parsed_data = data.split(b'|')
                if (parsed_data[0].decode("utf-8") == "sizeof"):
                    file_size = int(parsed_data[1].decode("utf-8"))
                    self.files_size[filename] = file_size
                
                    with log_lock:
                        with open('./log_file.txt', 'a') as log_file:
                            log_file.write(f"[{log_time()}] Peer {self.address} Recieved size({file_size} packets) From {peer_ip}:{peer_port}\n")
                        
            counter += 1
            if (counter == 1000):
                with log_lock:
                    with open('./log_file.txt', 'a') as log_file:
                        log_file.write(f"[{log_time()}] Peer {self.address} Error: Impossible to get {filename} size\n")
                
                raise Exception(f"Impossible to get {filename} size")
            
    def send_packet(self):
        data, addr = self.socket.recvfrom(MSS) 
        if (data):
            parsed_data = data.split(b'|')
            if (parsed_data[0].decode("utf-8") == "size"):
                file_size = math.ceil(os.path.getsize('./'+self.address+'/'+parsed_data[1].decode("utf-8")) / MSS)
                response = f"sizeof|{file_size}".encode()
            else:
                bytes_ = self.get_file_packet(parsed_data[1].decode("utf-8"), int(parsed_data[0].decode("utf-8")))
                response = bytes(f"{parsed_data[0].decode()}|", "utf-8") + bytes_
            self.socket.sendto(response, (addr))
            
                
    def get_file_packet(self, file_name, packet_number):
        if not os.path.exists('./'+self.address+'/'+file_name):
            with log_lock:
                with open('./log_file.txt', 'a') as log_file:
                    log_file.write(f"[{log_time()}] Peer {self.address} Error: don't have file {file_name}\n")
                
            raise NameError(f"Peer {self.address} don't have file {file_name}")
        
        with open('./'+self.address+'/'+file_name, 'rb') as file:
            file.seek(MSS * packet_number)
            bytes_ = file.read(MSS)
            return bytes_

    def download_file(self, filename: str):
        print(f'Requested {filename}')
        peers = self.node.find_peers(filename)
        if (len(peers) == 0):
            with log_lock:
                with open('./log_file.txt', 'a') as log_file:
                    log_file.write(f"[{log_time()}] Peer {self.address} Error: No available peers\n")
                
            raise Exception("No available peers")
        
        with log_lock:
            with open('./log_file.txt', 'a') as log_file:
                log_file.write(f"[{log_time()}] Peer {self.address} Requested {filename}\n")
            
        self.get_file_size(peers, filename)
        total_packets = self.files_size[filename]

        bar = FillingSquaresBar('Downloading', max = total_packets)
        current_packet = 0
        while (current_packet < self.files_size[filename]):
            with packet_map_lock:
                packet_map.clear()

            expected_packets = set(range(current_packet, min(current_packet + PACKETS_PER_BATCH, total_packets)))

            while True:
                with packet_map_lock:
                    missing = expected_packets - set(packet_map.keys())

                if not missing:
                    break

                threads = []
                for pkt_num in missing:
                    t = threading.Thread(target=self.thread_function,
                                        args=(peers, pkt_num, filename))
                    t.start()
                    threads.append(t)

                for t in threads:
                    t.join()

            for _ in range(PACKETS_PER_BATCH):
                bar.next()
            
            self.write_file(packet_map, filename)
            current_packet += len(packet_map)
        
        with log_lock:
            with open('./log_file.txt', 'a') as log_file:    
                log_file.write(f"[{log_time()}] Peer {self.address} Recieved {filename}\n")
                log_file.write(f"[{log_time()}] Peer {self.address} Announced {filename}\n")
        
        print(f"\n{filename} successfully downloaded!")
        self.node.announce_peer(filename, IP, self.port)

    def thread_function(self, peers: list, packet_number: int, filename: str):
        peer_ip, peer_port = peers[randint(0, len(peers) - 1)]
        peer_port = int(peer_port)

        try:
            request = f"{packet_number}|{filename}".encode()
            self.socket.sendto(request, (peer_ip, peer_port))
                
            data, _ = self.socket.recvfrom(PACKET_SIZE + len(str(packet_number)) + 1)
            parsed_data = data.split(b'|')
            received_number = -1
            if (parsed_data):
                received_number = int(parsed_data[0].decode("utf-8"))

            with log_lock:
                with open('./log_file.txt', 'a') as log_file:    
                    log_file.write(f"[{log_time()}] Peer {self.address} Recieved Packet {packet_number} From {peer_ip}:{peer_port}\n")
                
            with packet_map_lock:
                packet_map[received_number] = data

        except Exception as e:
            print(f"Thread error: {e}")

    def write_file(self, packets:dict, file_name:str):
        keys = list(packets.keys())
        keys.sort()
        
        if not os.path.exists('./'+self.address):
            os.makedirs('./' + self.address)
        
        if (keys[0] == 0):
            file = open('./'+self.address+'/'+file_name, mode='w')
            file.close()

        file = open('./'+self.address+'/'+file_name, mode='ab')

        for key in keys:
            file.write(packets[key][len(str(key)) + 1:])
        file.close()
    
    def shutdown(self):
        self.socket.close()
        self.node.shutdown()
        with log_lock:
            with open('./log_file.txt', 'a') as log_file:
                log_file.write(f"[{log_time()}] Peer {self.address} Shut down Node {self.node.ip}:{self.node.port}\n")
                log_file.write(f"[{log_time()}] Peer {self.address} Disconnected\n")
        

if __name__ == '__main__':
    if not os.path.exists('./log_file.txt'):
        open('./log_file.txt', 'w')
        
    parser = argparse.ArgumentParser()
    parser.add_argument('peer_port', type=int)
    parser.add_argument('dht_port', type=int)
    parser.add_argument('--file', type=str, required=False)

    if not os.path.exists('./well_known_nodes.txt'):
        well_known_nodes = []
        with open('./well_known_nodes.txt', 'w') as file:
            for port in WELL_KNOWN_NODES_PORTS:
                addr = (IP, port)
                bootstrap = DHT_node.DHTNode(IP, port)
                bootstrap.start()
                if len(well_known_nodes) > 1:
                    bootstrap.bootstrap(well_known_nodes)
                
                well_known_nodes.append(addr)
                file.write(f"{addr}\n")
                
                with log_lock:
                    with open('./log_file.txt', 'a') as log_file:
                        log_file.write(f"[{log_time()}] Created well-known node {IP}:{port}\n")

    args = parser.parse_args()
    peer = Peer(args.peer_port, args.dht_port)
    try:
        if not args.file:
            while True:
                peer.send_packet()
        else:
            peer.download_file(args.file)
            while True:
                peer.send_packet()
    except KeyboardInterrupt:
        peer.shutdown()
        with log_lock:
            with open('./log_file.txt', 'a') as log_file:
                log_file.write(f"[{log_time()}] Peer {peer.address} Shut down Node {peer.node.ip}:{peer.node.port}\n")
                log_file.write(f"[{log_time()}] Peer {peer.address} Disconnected\n")

        sys.exit(0)