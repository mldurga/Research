#!/bin/bash
# VPN Client Installation Script
# Installs OpenVPN and sets up the production VPN client

set -e

echo "========================================"
echo "VPN Client Installation"
echo "========================================"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS"
    exit 1
fi

echo "Detected OS: $OS"
echo

# Install OpenVPN
echo "Installing OpenVPN..."
case $OS in
    ubuntu|debian)
        apt-get update
        apt-get install -y openvpn curl
        ;;
    centos|rhel|fedora)
        yum install -y openvpn curl
        ;;
    arch)
        pacman -Sy --noconfirm openvpn curl
        ;;
    *)
        echo "Unsupported OS: $OS"
        echo "Please install OpenVPN manually"
        exit 1
        ;;
esac

echo
echo "✓ OpenVPN installed successfully"
echo

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed!"
    echo "Please install Python 3.7 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python $PYTHON_VERSION found"
echo

# Make scripts executable
chmod +x vpn_prod.py

echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo
echo "Usage:"
echo "  sudo python3 vpn_prod.py list              # List available servers"
echo "  sudo python3 vpn_prod.py connect 1         # Connect to server #1"
echo "  sudo python3 vpn_prod.py country Japan     # Connect to Japan"
echo "  sudo python3 vpn_prod.py disconnect        # Disconnect"
echo "  sudo python3 vpn_prod.py status            # Show status"
echo
echo "Try it now:"
echo "  sudo python3 vpn_prod.py list"
echo
