import socket
import os
import threading
from random import randint
import argparse
IP = 'localhost'


class Peer:
    def __init__(self, port:int):
        self.address = IP+':'+str(port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((IP, port))
        self.actual_dhts = self.get_dht()
        if len(self.actual_dhts) == 0:
            raise ValueError("No DHTs avaliable found")
        
        self.dht = self.actual_dhts[randint(0, len(self.actual_dhts)-1)]
        
        if os.path.isdir('./'+self.address):
            all_file_names = os.listdir('./'+self.address)
            for file in all_file_names:
                if os.path.isdir('./'+self.address+'/'+file): #асьюмим что папки не отправляюся
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
            print(f"Непредвиденный пиздец в get_dht {e}")
        return actual_dht
        
    
    def send_packet(self, number_of_packet:int):
        pass
        
    def get_packet(self):
        pass
        
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=int)
    args = parser.parse_args()
    example_peer = Peer(args.port)