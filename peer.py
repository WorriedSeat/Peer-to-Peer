import socket
import os
import threading
from random import randint
import argparse
# import DHT_node
IP = "0.0.0.0"
MSS = 1024


def thread_function(conn, addr):
    pass


class Peer:
    def __init__(self, port: int, dht_port: int):
        self.address = IP+':'+str(port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((IP, port))
        
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
       
    def send_packet(self, number_of_packet:int):
        pass
        
    def get_packet(self):
        pass

    # def get_peers(self, file_name):
    #     return self.node.get_peers() #XXX имя файла передавать
    
    def send_file(self, file_name:str):
        pass

    def download_file(self, file_name:str): #XXX имя файла тоже передавать
        peers = self.get_peers(file_name)
        if (len(peers) == 0):
            raise Exception("There are no any available peers")
        
        while (True):
            conn, addr = self.socket.accept()
            x = threading.Thread(target=thread_function, args=(conn, addr))
            x.start()

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
    args = parser.parse_args()
    peer = Peer(args.peer_port, args.dht_port)
    
    # peer.runner()
    
    peer.write_file({3:'tretie'.encode(), 1:"pervoe".encode(), 4:'fourth'.encode(), 2:'vtoroe'.encode()}, 'joke.txt')