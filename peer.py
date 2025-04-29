import socket
import os
import threading
from random import randint
import argparse
import math
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
       
    def send_packet(self):
        packet, reciever_address = self.socket.recvfrom(MSS)
        packet_as_list = str(packet, encoding='utf8').split('|')
        
        if packet_as_list[0] == 'size':
            file_size = os.path.getsize('./'+self.address+'/'+packet_as_list[1])
            response = f"sizeof|{packet_as_list[1]}|{file_size}".encode()
        else:
            bytes_ = self.get_file_packet(packet_as_list[1], int(packet_as_list[0]))
            response = f"{packet_as_list[0]}|{bytes_}".encode()
            
        self.socket.sendto(response, (reciever_address))
    
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