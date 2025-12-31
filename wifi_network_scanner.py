#!/usr/bin/env python3
"""
WiFi Network and Port Scanner
Scans the local network for active hosts and open ports.

IMPORTANT: Only use this tool on networks you own or have explicit permission to scan.
"""

import socket
import subprocess
import sys
import ipaddress
import concurrent.futures
from typing import List, Tuple, Dict
import argparse
import time

# Common ports to scan
COMMON_PORTS = [
    21,    # FTP
    22,    # SSH
    23,    # Telnet
    25,    # SMTP
    53,    # DNS
    80,    # HTTP
    110,   # POP3
    143,   # IMAP
    443,   # HTTPS
    445,   # SMB
    3306,  # MySQL
    3389,  # RDP
    5432,  # PostgreSQL
    5900,  # VNC
    8080,  # HTTP-Alt
    8443,  # HTTPS-Alt
    9200,  # Elasticsearch
    27017, # MongoDB
]

def get_local_network() -> str:
    """Get the local network CIDR."""
    try:
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()

        # Assume /24 subnet
        network = '.'.join(local_ip.split('.')[:-1]) + '.0/24'
        print(f"[*] Detected local network: {network}")
        print(f"[*] Your IP: {local_ip}")
        return network
    except Exception as e:
        print(f"[!] Error detecting network: {e}")
        return None

def ping_host(ip: str, timeout: int = 1) -> bool:
    """Check if a host is alive using ping."""
    try:
        # Use ping command (Linux)
        result = subprocess.run(
            ['ping', '-c', '1', '-W', str(timeout), ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 1
        )
        return result.returncode == 0
    except Exception:
        return False

def scan_port(ip: str, port: int, timeout: float = 0.5) -> Tuple[int, bool, str]:
    """Scan a single port on a host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()

        if result == 0:
            try:
                service = socket.getservbyport(port)
            except:
                service = "unknown"
            return port, True, service
        return port, False, ""
    except Exception:
        return port, False, ""

def scan_host_ports(ip: str, ports: List[int], max_workers: int = 50) -> List[Tuple[int, str]]:
    """Scan multiple ports on a host concurrently."""
    open_ports = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_port = {executor.submit(scan_port, ip, port): port for port in ports}

        for future in concurrent.futures.as_completed(future_to_port):
            port, is_open, service = future.result()
            if is_open:
                open_ports.append((port, service))

    return sorted(open_ports)

def scan_network(network: str, ports: List[int], ping_only: bool = False) -> Dict[str, List[Tuple[int, str]]]:
    """Scan all hosts in a network."""
    results = {}
    network_obj = ipaddress.ip_network(network, strict=False)

    print(f"\n[*] Scanning network: {network}")
    print(f"[*] Total hosts to check: {network_obj.num_addresses - 2}")
    print(f"[*] This may take a few minutes...\n")

    active_hosts = []

    # First, find active hosts
    print("[*] Phase 1: Discovering active hosts...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        future_to_ip = {executor.submit(ping_host, str(ip)): str(ip)
                        for ip in network_obj.hosts()}

        for i, future in enumerate(concurrent.futures.as_completed(future_to_ip), 1):
            ip = future_to_ip[future]
            if future.result():
                active_hosts.append(ip)
                print(f"  [+] Found active host: {ip}")

            if i % 50 == 0:
                print(f"  [*] Checked {i}/{network_obj.num_addresses - 2} hosts...")

    print(f"\n[*] Found {len(active_hosts)} active hosts")

    if ping_only:
        return {host: [] for host in active_hosts}

    # Then scan ports on active hosts
    print("\n[*] Phase 2: Scanning ports on active hosts...")
    for host in active_hosts:
        print(f"\n[*] Scanning {host}...")
        open_ports = scan_host_ports(host, ports)

        if open_ports:
            results[host] = open_ports
            print(f"  [+] Found {len(open_ports)} open ports on {host}")
            for port, service in open_ports:
                print(f"      Port {port} ({service})")
        else:
            print(f"  [-] No open ports found on {host}")

    return results

def get_hostname(ip: str) -> str:
    """Try to resolve hostname for an IP."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except:
        return "Unknown"

def main():
    parser = argparse.ArgumentParser(
        description='WiFi Network and Port Scanner',
        epilog='WARNING: Only scan networks you own or have permission to scan!'
    )
    parser.add_argument('-n', '--network', help='Network to scan (e.g., 192.168.1.0/24)')
    parser.add_argument('-p', '--ports', help='Ports to scan (comma-separated, e.g., 22,80,443)')
    parser.add_argument('--all-ports', action='store_true', help='Scan all ports 1-1024')
    parser.add_argument('--ping-only', action='store_true', help='Only ping hosts, do not scan ports')
    parser.add_argument('--timeout', type=float, default=0.5, help='Port scan timeout in seconds (default: 0.5)')

    args = parser.parse_args()

    print("=" * 70)
    print("WiFi Network and Port Scanner")
    print("=" * 70)
    print("\nWARNING: Only use this tool on networks you own or have permission to scan!")
    print("\nPress Ctrl+C to cancel...")
    time.sleep(2)

    # Determine network to scan
    if args.network:
        network = args.network
    else:
        network = get_local_network()
        if not network:
            print("[!] Could not detect network. Please specify with -n")
            sys.exit(1)

    # Determine ports to scan
    if args.ping_only:
        ports = []
    elif args.all_ports:
        ports = list(range(1, 1025))
        print(f"[*] Scanning ports 1-1024")
    elif args.ports:
        ports = [int(p.strip()) for p in args.ports.split(',')]
        print(f"[*] Scanning ports: {ports}")
    else:
        ports = COMMON_PORTS
        print(f"[*] Scanning common ports: {ports}")

    # Run the scan
    start_time = time.time()
    results = scan_network(network, ports, args.ping_only)
    elapsed_time = time.time() - start_time

    # Print summary
    print("\n" + "=" * 70)
    print("SCAN RESULTS")
    print("=" * 70)

    if not results:
        print("\n[!] No active hosts with open ports found.")
    else:
        for ip, open_ports in results.items():
            hostname = get_hostname(ip)
            print(f"\n[+] Host: {ip} ({hostname})")
            print(f"    Pingable: Yes")

            if open_ports:
                print(f"    Open Ports:")
                for port, service in open_ports:
                    print(f"      - {port:5d}/tcp  {service}")
            else:
                print(f"    Open Ports: None (but host is pingable)")

    print(f"\n[*] Scan completed in {elapsed_time:.2f} seconds")
    print(f"[*] Total hosts scanned: {len(results)}")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Scan cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Error: {e}")
        sys.exit(1)
