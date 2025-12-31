#!/usr/bin/env python3
"""
Direct port scanning demo (bypasses ping)
"""

import socket
import threading
import time
from wifi_network_scanner import scan_host_ports, get_hostname

def start_mock_server(port, name):
    """Start a mock server on a specific port"""
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', port))
        server.listen(1)
        return server
    except Exception as e:
        print(f"  [!] Error starting {name}: {e}")
        return None

# Configuration
mock_services = [
    (8080, "HTTP Server"),
    (8443, "HTTPS Server"),
    (5432, "PostgreSQL"),
    (3306, "MySQL"),
    (22, "SSH"),
]

print("=" * 70)
print("WiFi Network Scanner - Direct Port Scan Demo")
print("=" * 70)

print("\n[Phase 1] Starting mock services...")
servers = []
for port, name in mock_services:
    server = start_mock_server(port, name)
    if server:
        servers.append(server)
        print(f"  [+] {name} listening on port {port}")

time.sleep(0.5)

print("\n[Phase 2] Scanning target host...")
target_ip = "127.0.0.1"
ports_to_scan = [21, 22, 80, 443, 3306, 5432, 8080, 8443, 9000]

print(f"  Target: {target_ip}")
print(f"  Ports: {ports_to_scan}")
print(f"  Scanning...")

open_ports = scan_host_ports(target_ip, ports_to_scan, max_workers=50)

print("\n" + "=" * 70)
print("SCAN RESULTS")
print("=" * 70)

if open_ports:
    hostname = get_hostname(target_ip)
    print(f"\n[+] Host: {target_ip} ({hostname})")
    print(f"    Status: REACHABLE")
    print(f"    Open Ports: {len(open_ports)}")
    print()
    for port, service in open_ports:
        print(f"      Port {port:5d}/tcp  {service if service else 'unknown':<20}  [OPEN]")
else:
    print(f"\n[-] No open ports found on {target_ip}")

print("\n" + "=" * 70)
print("Summary:")
print(f"  • Scanner successfully tested {len(ports_to_scan)} ports")
print(f"  • Detected {len(open_ports)} open services")
print(f"  • Scan completed in concurrent mode")
print("=" * 70)

# Cleanup
for server in servers:
    server.close()
