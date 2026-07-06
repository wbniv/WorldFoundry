#!/bin/bash
# Run this on the joiner machine after git pull to authorize the debug SSH key.
# Lets Claude SSH in from Will's laptop for collab debugging.
set -euo pipefail

PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAh3rQPFdy/aT204IZKwrLuNJSwmTmSxw6Qu+vgKLG81 wf-debug-collab"

mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

if grep -qF "wf-debug-collab" ~/.ssh/authorized_keys 2>/dev/null; then
    echo "wf-debug-collab key already present"
else
    echo "$PUBKEY" >> ~/.ssh/authorized_keys
    echo "wf-debug-collab key added to ~/.ssh/authorized_keys"
fi
