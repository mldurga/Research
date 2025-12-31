#!/usr/bin/env python3
"""
WiFi Network Information Gatherer
Retrieves current WiFi connection details and metadata
"""

import socket
import subprocess
import platform
import os

print("=" * 70)
print("WiFi Network Information")
print("=" * 70)

# 1. Get hostname
print(f"\n[System Information]")
print(f"  Hostname: {socket.gethostname()}")
print(f"  Platform: {platform.system()} {platform.release()}")

# 2. Get IP address and network info
print(f"\n[Network Configuration]")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]
    s.close()
    print(f"  Local IP: {local_ip}")
    network = '.'.join(local_ip.split('.')[:-1]) + '.0/24'
    print(f"  Network: {network}")
except Exception as e:
    print(f"  Could not detect IP: {e}")

# 3. Try to get WiFi SSID using various methods
print(f"\n[WiFi Information]")

# Method 1: nmcli (Linux NetworkManager)
try:
    result = subprocess.run(['nmcli', '-t', '-f', 'active,ssid', 'dev', 'wifi'],
                          capture_output=True, text=True, timeout=2)
    if result.returncode == 0:
        for line in result.stdout.split('\n'):
            if line.startswith('yes:'):
                ssid = line.split('yes:')[1]
                print(f"  WiFi SSID: {ssid}")

        # Get more details
        result2 = subprocess.run(['nmcli', 'connection', 'show', '--active'],
                               capture_output=True, text=True, timeout=2)
        if result2.returncode == 0:
            print(f"\n  Connection Details:")
            for line in result2.stdout.split('\n')[:10]:
                print(f"    {line}")
except:
    pass

# Method 2: iwgetid (Linux)
try:
    result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=2)
    if result.returncode == 0 and result.stdout.strip():
        print(f"  WiFi SSID: {result.stdout.strip()}")
except:
    pass

# Method 3: iw (Linux)
try:
    result = subprocess.run(['iw', 'dev'], capture_output=True, text=True, timeout=2)
    if result.returncode == 0:
        print(f"\n  Wireless Device Info:")
        print(result.stdout)
except:
    pass

# Method 4: Check /proc/net files
try:
    if os.path.exists('/proc/net/wireless'):
        with open('/proc/net/wireless', 'r') as f:
            content = f.read()
            if content:
                print(f"\n  Wireless Stats:")
                print(content)
except:
    pass

# Method 5: netsh (Windows)
if platform.system() == 'Windows':
    try:
        result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            print(f"\n  Windows WiFi Info:")
            for line in result.stdout.split('\n'):
                if 'SSID' in line or 'Signal' in line or 'Channel' in line:
                    print(f"    {line.strip()}")
    except:
        pass

# Method 6: airport (macOS)
if platform.system() == 'Darwin':
    try:
        result = subprocess.run(['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-I'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            print(f"\n  macOS WiFi Info:")
            print(result.stdout)
    except:
        pass

# 4. Get gateway/router info
print(f"\n[Gateway Information]")
try:
    # Try to get default gateway
    if platform.system() == 'Linux':
        try:
            with open('/proc/net/route', 'r') as f:
                for line in f.readlines()[1:]:
                    fields = line.split()
                    if fields[1] == '00000000':  # Default route
                        gateway = socket.inet_ntoa(bytes.fromhex(fields[2])[::-1])
                        print(f"  Default Gateway: {gateway}")
        except:
            pass

    # Alternative method
    result = subprocess.run(['netstat', '-rn'], capture_output=True, text=True, timeout=2)
    if result.returncode == 0:
        for line in result.stdout.split('\n'):
            if 'default' in line.lower() or '0.0.0.0' in line:
                print(f"  Route: {line.strip()}")
                break
except:
    pass

# 5. DNS Information
print(f"\n[DNS Configuration]")
try:
    if os.path.exists('/etc/resolv.conf'):
        with open('/etc/resolv.conf', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    print(f"  {line.strip()}")
except:
    pass

print("\n" + "=" * 70)
print("Note: Limited information available in this environment")
print("On a real system with WiFi, this would show:")
print("  • WiFi SSID (network name)")
print("  • Signal strength")
print("  • Channel and frequency")
print("  • MAC address (BSSID)")
print("  • Security type (WPA2/WPA3)")
print("  • Connection speed")
print("=" * 70)
