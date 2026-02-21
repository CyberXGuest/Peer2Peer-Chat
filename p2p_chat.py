#!/usr/bin/env python3
"""
p2p_chat.py - Peer-to-peer chat tool for Kali Linux
Usage: 
  ./p2p_chat.py listen [port]              # Start listening mode
  ./p2p_chat.py connect <username> <ip> [port]  # Connect to another user
  ./p2p_chat.py discover [port]            # Discover users on local network
"""

import socket
import threading
import sys
import signal
import time
import json
import select
import hashlib
import os
from datetime import datetime
from typing import Optional, Tuple

# Terminal colors for better visibility
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class P2PChat:
    def __init__(self, username: str = None, port: int = 5000):
        self.username = username or socket.gethostname()
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(1.0)  # 1 second timeout for select
        self.running = True
        self.peers = {}  # {ip: {'username': username, 'last_seen': timestamp}}
        self.current_chat = None  # Current chat partner (ip)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n{Colors.YELLOW}Shutting down...{Colors.ENDC}")
        self.running = False
        if self.socket:
            self.socket.close()
        sys.exit(0)
    
    def start_listener(self):
        """Start listening for incoming messages and discovery requests"""
        try:
            self.socket.bind(('0.0.0.0', self.port))
            print(f"{Colors.GREEN}[*] Listening on port {self.port}{Colors.ENDC}")
            print(f"{Colors.BLUE}[*] Your username: {self.username}{Colors.ENDC}")
            print(f"{Colors.BLUE}[*] Your IP: {self.get_local_ip()}{Colors.ENDC}")
            
            # Start peer discovery broadcast thread
            discovery_thread = threading.Thread(target=self.broadcast_presence)
            discovery_thread.daemon = True
            discovery_thread.start()
            
            # Main listening loop
            while self.running:
                try:
                    data, addr = self.socket.recvfrom(4096)
                    threading.Thread(target=self.handle_message, args=(data, addr)).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"{Colors.RED}Error: {e}{Colors.ENDC}")
                        
        except Exception as e:
            print(f"{Colors.RED}Failed to bind to port {self.port}: {e}{Colors.ENDC}")
            sys.exit(1)
    
    def handle_message(self, data: bytes, addr: Tuple[str, int]):
        """Handle different types of incoming messages"""
        try:
            message = json.loads(data.decode())
            msg_type = message.get('type', 'message')
            from_ip = addr[0]
            
            if msg_type == 'presence':
                # Update peer list
                self.peers[from_ip] = {
                    'username': message['username'],
                    'last_seen': time.time()
                }
                
            elif msg_type == 'message':
                # Regular chat message
                if message.get('to_username') == self.username:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    sender = f"{message['from_username']}@{from_ip}"
                    
                    # Check if this is a command
                    if message['text'].startswith('/'):
                        self.handle_command(message['text'], from_ip)
                    else:
                        print(f"\n{Colors.GREEN}[{timestamp}] {sender}:{Colors.ENDC} {message['text']}")
                        
                    # Set current chat if not set
                    if not self.current_chat:
                        self.current_chat = from_ip
                        
            elif msg_type == 'typing':
                # Typing notification
                if message.get('to_username') == self.username:
                    print(f"\r{Colors.YELLOW}{message['from_username']} is typing...{Colors.ENDC}", end='', flush=True)
                    
            elif msg_type == 'read_receipt':
                # Read receipt
                if message.get('to_username') == self.username:
                    print(f"\n{Colors.BLUE}[Message read by {message['from_username']}]{Colors.ENDC}")
                    
            elif msg_type == 'file_offer':
                # File transfer offer
                if message.get('to_username') == self.username:
                    self.handle_file_offer(message, from_ip)
                    
            elif msg_type == 'disconnect':
                # Peer disconnecting
                if from_ip in self.peers:
                    print(f"\n{Colors.YELLOW}{self.peers[from_ip]['username']}@{from_ip} has disconnected{Colors.ENDC}")
                    if self.current_chat == from_ip:
                        self.current_chat = None
                    del self.peers[from_ip]
                    
        except json.JSONDecodeError:
            print(f"{Colors.RED}Received invalid message from {addr[0]}{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}Error handling message: {e}{Colors.ENDC}")
    
    def handle_command(self, command: str, from_ip: str = None):
        """Handle special commands"""
        if command.startswith('/msg '):
            # Switch chat to specific user
            target = command[5:].strip()
            if target in self.peers:
                self.current_chat = target
                print(f"{Colors.GREEN}Now chatting with {self.peers[target]['username']}@{target}{Colors.ENDC}")
            else:
                print(f"{Colors.RED}User {target} not found{Colors.ENDC}")
                
        elif command == '/list':
            # List available peers
            self.list_peers()
            
        elif command == '/quit' and from_ip:
            # Exit current chat
            if self.current_chat:
                print(f"{Colors.YELLOW}Left chat with {self.peers[self.current_chat]['username']}{Colors.ENDC}")
                self.current_chat = None
                
        elif command == '/help':
            self.show_help()
    
    def broadcast_presence(self):
        """Broadcast presence to local network"""
        broadcast_addr = ('255.255.255.255', self.port)
        presence_msg = {
            'type': 'presence',
            'username': self.username,
            'timestamp': time.time()
        }
        
        while self.running:
            try:
                self.socket.sendto(json.dumps(presence_msg).encode(), broadcast_addr)
                time.sleep(30)  # Broadcast every 30 seconds
            except Exception as e:
                if self.running:
                    print(f"{Colors.RED}Error broadcasting presence: {e}{Colors.ENDC}")
                time.sleep(5)
    
    def connect_to_peer(self, peer_username: str, peer_ip: str, peer_port: int = None):
        """Connect to a specific peer"""
        port = peer_port or self.port
        self.current_chat = peer_ip
        
        # Add to peers list
        self.peers[peer_ip] = {
            'username': peer_username,
            'last_seen': time.time()
        }
        
        print(f"{Colors.GREEN}Connected to {peer_username}@{peer_ip}{Colors.ENDC}")
        print(f"{Colors.YELLOW}Type /help for commands{Colors.ENDC}")
        
        # Send presence to this peer
        self.send_presence(peer_ip, port)
        
        # Start chat loop
        self.chat_loop(peer_ip, peer_username, port)
    
    def chat_loop(self, peer_ip: str, peer_username: str, peer_port: int):
        """Main chat interaction loop"""
        last_typing = 0
        
        while self.running and self.current_chat == peer_ip:
            try:
                # Use select for non-blocking input
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    message = sys.stdin.readline().strip()
                    
                    if not message:
                        continue
                    
                    if message == '/quit':
                        break
                    elif message == '/list':
                        self.list_peers()
                    elif message == '/clear':
                        os.system('clear' if os.name == 'posix' else 'cls')
                    elif message.startswith('/sendfile '):
                        self.send_file_offer(message[10:].strip(), peer_ip, peer_username, peer_port)
                    else:
                        # Send regular message
                        self.send_message(message, peer_ip, peer_username, peer_port)
                        
                        # Send typing notification every 3 seconds while typing
                        if time.time() - last_typing > 3:
                            self.send_typing(peer_ip, peer_username, peer_port)
                            last_typing = time.time()
                            
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"{Colors.RED}Error: {e}{Colors.ENDC}")
                
        # Send disconnect notification
        self.send_disconnect(peer_ip, peer_port)
        self.current_chat = None
    
    def send_message(self, text: str, peer_ip: str, peer_username: str, peer_port: int):
        """Send a chat message to a peer"""
        message = {
            'type': 'message',
            'from_username': self.username,
            'to_username': peer_username,
            'text': text,
            'timestamp': time.time()
        }
        
        try:
            self.socket.sendto(json.dumps(message).encode(), (peer_ip, peer_port))
            
            # Display own message
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"\r{Colors.BLUE}[{timestamp}] You:{Colors.ENDC} {text}")
            
        except Exception as e:
            print(f"{Colors.RED}Failed to send message: {e}{Colors.ENDC}")
    
    def send_typing(self, peer_ip: str, peer_username: str, peer_port: int):
        """Send typing notification"""
        message = {
            'type': 'typing',
            'from_username': self.username,
            'to_username': peer_username,
            'timestamp': time.time()
        }
        
        try:
            self.socket.sendto(json.dumps(message).encode(), (peer_ip, peer_port))
        except:
            pass
    
    def send_presence(self, peer_ip: str, peer_port: int):
        """Send presence to a specific peer"""
        message = {
            'type': 'presence',
            'username': self.username,
            'timestamp': time.time()
        }
        
        try:
            self.socket.sendto(json.dumps(message).encode(), (peer_ip, peer_port))
        except:
            pass
    
    def send_disconnect(self, peer_ip: str, peer_port: int):
        """Send disconnect notification"""
        message = {
            'type': 'disconnect',
            'username': self.username,
            'timestamp': time.time()
        }
        
        try:
            self.socket.sendto(json.dumps(message).encode(), (peer_ip, peer_port))
        except:
            pass
    
    def send_file_offer(self, filename: str, peer_ip: str, peer_username: str, peer_port: int):
        """Offer to send a file"""
        if not os.path.exists(filename):
            print(f"{Colors.RED}File not found: {filename}{Colors.ENDC}")
            return
            
        file_size = os.path.getsize(filename)
        file_hash = self.calculate_file_hash(filename)
        
        message = {
            'type': 'file_offer',
            'from_username': self.username,
            'to_username': peer_username,
            'filename': os.path.basename(filename),
            'size': file_size,
            'hash': file_hash,
            'timestamp': time.time()
        }
        
        try:
            self.socket.sendto(json.dumps(message).encode(), (peer_ip, peer_port))
            print(f"{Colors.GREEN}File offer sent: {os.path.basename(filename)} ({file_size} bytes){Colors.ENDC}")
            print(f"{Colors.YELLOW}Waiting for response...{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.RED}Failed to send file offer: {e}{Colors.ENDC}")
    
    def handle_file_offer(self, offer: dict, from_ip: str):
        """Handle incoming file offer"""
        filename = offer['filename']
        file_size = offer['size']
        file_hash = offer['hash']
        sender = offer['from_username']
        
        print(f"\n{Colors.GREEN}File offer from {sender}@{from_ip}:{Colors.ENDC}")
        print(f"  Filename: {filename}")
        print(f"  Size: {file_size} bytes")
        print(f"  Hash: {file_hash[:16]}...")
        
        response = input(f"{Colors.YELLOW}Accept file? (y/n): {Colors.ENDC}").lower()
        
        if response == 'y':
            # In a real implementation, you'd set up a TCP connection for file transfer
            print(f"{Colors.GREEN}File transfer starting...{Colors.ENDC}")
            print(f"{Colors.YELLOW}Note: Full file transfer not implemented in this demo{Colors.ENDC}")
        else:
            print(f"{Colors.RED}File rejected{Colors.ENDC}")
    
    def calculate_file_hash(self, filename: str) -> str:
        """Calculate SHA-256 hash of a file"""
        sha256 = hashlib.sha256()
        with open(filename, 'rb') as f:
            for block in iter(lambda: f.read(4096), b''):
                sha256.update(block)
        return sha256.hexdigest()
    
    def list_peers(self):
        """List all discovered peers"""
        print(f"\n{Colors.BOLD}Available peers:{Colors.ENDC}")
        if not self.peers:
            print("  No peers discovered")
        else:
            for ip, info in self.peers.items():
                status = "Active" if time.time() - info['last_seen'] < 60 else "Inactive"
                print(f"  {info['username']} @ {ip} [{status}]")
        print()
    
    def discover_peers(self, timeout: int = 5):
        """Discover peers on local network"""
        print(f"{Colors.GREEN}Discovering peers on local network...{Colors.ENDC}")
        
        # Set socket to broadcast mode
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Send discovery broadcast
        discovery_msg = {
            'type': 'presence',
            'username': self.username,
            'timestamp': time.time()
        }
        
        broadcast_addr = ('255.255.255.255', self.port)
        self.socket.sendto(json.dumps(discovery_msg).encode(), broadcast_addr)
        
        # Listen for responses
        start_time = time.time()
        self.peers = {}
        
        while time.time() - start_time < timeout:
            try:
                data, addr = self.socket.recvfrom(4096)
                message = json.loads(data.decode())
                
                if message.get('type') == 'presence' and addr[0] != self.get_local_ip():
                    self.peers[addr[0]] = {
                        'username': message['username'],
                        'last_seen': time.time()
                    }
            except socket.timeout:
                continue
            except Exception:
                pass
        
        self.list_peers()
    
    def get_local_ip(self) -> str:
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return '127.0.0.1'
    
    def show_help(self):
        """Display help information"""
        help_text = f"""
{Colors.BOLD}Available commands:{Colors.ENDC}
  /list           - List all available peers
  /msg <ip>       - Switch chat to specific peer
  /sendfile <file>- Send file to current chat partner
  /clear          - Clear the screen
  /quit           - Exit current chat or application
  /help           - Show this help message

{Colors.BOLD}Usage examples:{Colors.ENDC}
  Start listening:  ./p2p_chat.py listen 5000
  Connect to peer:  ./p2p_chat.py connect alice 192.168.1.100 5000
  Discover peers:   ./p2p_chat.py discover 5000
        """
        print(help_text)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  ./p2p_chat.py listen [port]")
        print("  ./p2p_chat.py connect <username> <ip> [port]")
        print("  ./p2p_chat.py discover [port]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "listen":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
        username = input(f"{Colors.BLUE}Enter your username: {Colors.ENDC}").strip() or socket.gethostname()
        
        chat = P2PChat(username, port)
        chat.start_listener()
        
    elif command == "connect":
        if len(sys.argv) < 4:
            print("Usage: ./p2p_chat.py connect <username> <ip> [port]")
            sys.exit(1)
            
        username = sys.argv[2]
        peer_ip = sys.argv[3]
        port = int(sys.argv[4]) if len(sys.argv) > 4 else 5000
        
        my_username = input(f"{Colors.BLUE}Enter your username: {Colors.ENDC}").strip() or socket.gethostname()
        
        chat = P2PChat(my_username, port)
        
        # Start listener in background
        listener_thread = threading.Thread(target=chat.start_listener)
        listener_thread.daemon = True
        listener_thread.start()
        
        time.sleep(1)  # Give listener time to start
        chat.connect_to_peer(username, peer_ip, port)
        
    elif command == "discover":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
        
        chat = P2PChat(socket.gethostname(), port)
        chat.discover_peers()
        
    else:
        print("Unknown command")

if __name__ == "__main__":
    main()
