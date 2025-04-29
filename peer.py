import socket
import os
import threading
from random import randint
import argparse
import dht_node
IP = "0.0.0.0"
MSS = 1024


def thread_function(conn, addr):
    pass


class Peer:
    def __init__(self, port: int, dht_port: int):
        self.address = IP+':'+str(port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((IP, port))
        self.socket.listen()
        
        self.node = dht_node.DHT(IP, dht_port)
        
        if os.path.isdir('./'+self.address):
            all_file_names = os.listdir('./'+self.address)
            for file in all_file_names:
                if os.path.isdir('./'+self.address+'/'+file):
                    print(f'Found directory (will not be sent): {file}')
                else:
                    self.announce(file)

    def announce(self, file_name:str):
        ...
    
    def get_dht(self):
        actual_dht = []
        try:
            with open("./main_dht_addresses.txt", "r") as file:
                actual_dht = file.read().splitlines()
        except Exception as e:
            print(f"Error in get_dht {e}")
        return actual_dht
        
    
    def send_packet(self, number_of_packet:int):
        pass
        
    def get_packet(self):
        pass

    def get_peers(self):
        return self.node.get_peers()
    
    def download_file(self):
        peers = self.get_peers()
        if (len(peers) == 0):
            raise Exception("There are no any available peers")
        
        while (True):
            conn, addr = self.socket.accept()
            x = threading.Thread(target=thread_function, args=(conn, addr))
            x.start()




if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=int)
    args = parser.parse_args()
    example_peer = Peer(args.port)