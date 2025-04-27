import os
import socket
import threading
import hashlib
import pickle
from tqdm import tqdm
from time import sleep

CHUNK_SIZE = 1024 * 1024  # 1MB
TRACKER_PORT = 5000
PEER_PORT_BASE = 6000

class Tracker:
    def __init__(self):
        # file_hash: set of peer addresses
        self.peers = {}
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        s = socket.socket()
        s.bind(('0.0.0.0', TRACKER_PORT))
        s.listen()
        print("[Tracker] Running on port", TRACKER_PORT)
        while True:
            conn, addr = s.accept()
            threading.Thread(target=self.handle, args=(conn,), daemon=True).start()


class Peer:
    pass
