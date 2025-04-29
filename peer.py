import socket
import os
import threading
from random import randint
import argparse
import math
import time

# import DHT_node
IP = "0.0.0.0"
MSS = 1024
PACKET_SIZE = MSS
PACKETS_PER_BATCH = 10

packet_map_lock = threading.Lock()
packet_map = {}


class Peer:
    def __init__(self, port: int, dht_port: int):
        self.address = IP+':'+str(port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((IP, port))
        self.files_size = {}
        
        # self.node = DHT_node.DHT(IP, dht_port)
        # self.node.start()
        # self.node.bootstrap(self.get_dht())
        
        if os.path.isdir('./'+self.address):
            all_file_names = os.listdir('./'+self.address)
            for file in all_file_names:
                if os.path.isdir('./'+self.address+'/'+file):
                    print(f'Found directory (will not be sent): {file}')
                else:
                    print(f"Announcing existing file {file}")
                    # self.node.announce(file)
    
    def runner(self):
        pass
    
    def get_dht(self):
        actual_dht = []
        try:
            with open("./main_dht_addresses.txt", "r") as file:
                actual_dht = file.read().splitlines()
        except Exception as e:
            print(f"Error in get_dht {e}")
        return actual_dht
    
    def get_file_size(self, peers: list, filename: str):
        file_size = -1
        counter = 0
        while (file_size == -1):
            # peer_ip, peer_port = peers[randint(0, len(peers) - 1)].split(":")
            peer_ip, peer_port = "0.0.0.0", "5000"
            peer_port = int(peer_port)
            request = f"size|{filename}".encode()
            self.socket.sendto(request, (peer_ip, peer_port))

            data, _ = self.socket.recvfrom(PACKET_SIZE)
            if (data):
                parsed_data = data.split(b'|')
                if (parsed_data[0].decode("utf-8") == "sizeof"):
                    file_size = int(parsed_data[1].decode("utf-8"))
                    self.files_size[filename] = file_size
            
            counter += 1
            if (counter == 1000):
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
                response = parsed_data[0] + b'|' + bytes_
                
            self.socket.sendto(response, (addr))
    
    def get_file_packet(self, file_name, packet_number):
        if not os.path.exists('./'+self.address+'/'+file_name):
            raise NameError(f"Peer {self.address} don't have file {file_name}")
        
        with open('./'+self.address+'/'+file_name, 'rb') as file:
            for i in range(math.ceil(os.path.getsize('./'+self.address+'/'+file_name) / MSS)):
                bytes_ = file.read(MSS)
                if i == packet_number:
                    return bytes_
        
    def get_packet(self):
        pass

    # def get_peers(self, file_name):
    #     return self.node.get_peers() #XXX имя файла передавать

    def download_file(self, filename: str):
        peers = ["0.0.0.0:5000"]
        if (len(peers) == 0):
            raise Exception("There are no any available peers")
        
        self.get_file_size(peers, filename)
        total_packets = self.files_size[filename]

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

            self.write_file(packet_map, filename)
            current_packet += len(packet_map)
            if (current_packet == total_packets):
                break

    def thread_function(self, peers: list, packet_number: int, filename: str):
        peer_ip, peer_port = peers[randint(0, len(peers) - 1)].split(":")
        peer_port = int(peer_port)

        try:
            request = f"{packet_number}|{filename}".encode()
            self.socket.sendto(request, (peer_ip, peer_port))
            self.socket.settimeout(2)

            data, _ = self.socket.recvfrom(PACKET_SIZE)
            parsed_data = data.split(b'|')
            print(parsed_data)
            received_number = -1
            if (parsed_data):
                received_number = int(parsed_data[0].decode("utf-8"))

            packet_data = parsed_data[1]

            with packet_map_lock:
                packet_map[received_number] = packet_data
        except Exception as e:
            print(f"Thread error: {e}")


    def write_file(self, packets:dict, file_name:str):
        keys = list(packets.keys())
        keys.sort()
        
        if os.path.exists('./'+self.address+'/'+file_name):
            mode = 'ab'
        else:
            mode='wb'
            os.makedirs('./' + self.address)
        
        with open('./'+self.address+'/'+file_name, mode=mode) as file:
            for key in keys:
                file.write(packets.get(key))
        
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('peer_port', type=int)
    parser.add_argument('dht_port', type=int)
    parser.add_argument('--file', type=str, required=False)
    args = parser.parse_args()
    peer = Peer(args.peer_port, args.dht_port)
    if (args.peer_port != 5000):
        peer.download_file(args.file)
    else:
        while (True):
            peer.send_packet()
            time.sleep(2)