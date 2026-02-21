#!/bin/bash
# install_chat_tool.sh - Installation script for P2P Chat Tool

echo -e "\e[92m[*] Installing P2P Chat Tool for Kali Linux\e[0m"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "\e[91mPlease run as root (sudo)\e[0m"
    exit 1
fi

# Make the script executable
chmod +x p2p_chat.py

# Copy to /usr/local/bin
cp p2p_chat.py /usr/local/bin/p2p-chat

# Create symbolic link
ln -sf /usr/local/bin/p2p-chat /usr/bin/p2p-chat

echo -e "\e[92m[*] Installation complete!\e[0m"
echo -e "\e[94mYou can now run 'p2p-chat' from anywhere\e[0m"