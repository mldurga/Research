#!/bin/bash
# Quick start script for iPhone VPN web server

set -e

echo "========================================"
echo "Starting VPN Web Server for iPhone"
echo "========================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo "Please install Python 3.7 or higher"
    exit 1
fi

# Check if Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "Flask is not installed. Installing dependencies..."
    pip install -r requirements.txt
    echo
fi

# Get local IP address
echo "Detecting your IP address..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    LOCAL_IP=$(hostname -I | awk '{print $1}')
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    LOCAL_IP=$(ipconfig getifaddr en0)
else
    LOCAL_IP="YOUR_IP_ADDRESS"
fi

echo
echo "========================================"
echo "Your computer's IP address: $LOCAL_IP"
echo "========================================"
echo
echo "On your iPhone:"
echo "1. Connect to the same WiFi network"
echo "2. Open Safari and go to:"
echo
echo "   http://$LOCAL_IP:5000"
echo
echo "========================================"
echo "Starting server..."
echo "Press Ctrl+C to stop"
echo "========================================"
echo

# Start the server
python3 vpn_web_server.py
