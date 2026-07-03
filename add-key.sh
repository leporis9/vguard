#!/bin/bash
# ==============================================================
# Add a user's SSH public key to authorized_keys
# Usage: bash add-key.sh "ssh-rsa AAAAB3..."
# ==============================================================
PUBKEY="$1"
if [ -z "$PUBKEY" ]; then
    echo "用法: bash add-key.sh 'ssh-rsa AAAB3...'"
    exit 1
fi
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "$PUBKEY" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
echo "已添加公钥"
