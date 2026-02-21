p2p_chat.py - Peer-to-peer chat tool for Kali Linux
#Usage: 
  ./p2p_chat.py listen [port]              # Start listening mode
  ./p2p_chat.py connect <username> <ip> [port]  # Connect to another user
  ./p2p_chat.py discover [port]            # Discover users on local network
#. Usage Examples

# Here's how to use the tool:

# On Machine A (Alice):

Start listening mode
./p2p_chat.py listen 5000
# Enter username: alice

# On Machine B (Bob):

 Start listening mode
./p2p_chat.py listen 5000
Enter username: bob

# On Machine B (Bob):

Start listening mode
./p2p_chat.py listen 5000 
Enter username: bob

Bob connects to Alice:


./p2p_chat.py connect alice 192.168.1.100 5000
# Enter your username: bob
