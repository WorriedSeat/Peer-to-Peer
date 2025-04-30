# Peer-to-Peer File Sharing System
Project for Innopolis University Distributed Network Programming Course with realization of the Peer-to-Peer file sharing system using DHT.
___

A simple peer-to-peer (P2P) file sharing system implemented in Python, allowing users to share files directly between connected peers without a central server.

## Features

- **Decentralized Architecture**: No central server required - peers communicate directly
- **File Sharing**: Share and download files from connected peers
- **Peer Discovery**: Automatically discover other peers on the same network
- **Multi-threaded**: Handles multiple connections simultaneously
- **Simple CLI**: Easy-to-use command line interface

## Requirements

- Python 3.6+
- Additional Library `progress` to show the progress bar:
  ```bash
  #Run the following command to download needed library
  pip install progress
  ```

## Installation

1. Make sure that all Requirements are met.

2. Clone the repository:
   ```bash
   git clone https://github.com/WorriedSeat/Peer-to-Peer.git
   cd Peer-to-Peer
   ```

## Usage

### Project Structure
  1. `DHT_node.py` - code of the DHT-Node
  2. `peer.py` - code of the Peer
  3. Folders with the name of peer address IP:PORT (ex: 0.0.0.0:5000) represent the Peer Storage which store all files that Peer have and able to share.  

### Starting a Peer Node
```bash
python peer.py [peer_port PORT] [dht_port PORT] [--file NAME]
```

Options:
- `peer_port`: Port of the peer
- `dht_port`: Port of the corresponding DHT-Node
- `--file`: Name of the file to download.
**Note!** if `--file` not stated than the peer able only to send packets  

### Example of Usage

**Note!** You need to run these commands in the different terminals

```bash
python peer.py 5000 6883
```
```bash
python peer.py 5001 6884
```
```bash
python peer.py 5002 6885 --file image.png
```

**Result**  A folder '0.0.0.0:5002' will be created in the project directory and the downloaded 'image.png' file will appear in it.

 A more detailed description of the project can be found in `DNP_project.pdf`
