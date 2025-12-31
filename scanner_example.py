#!/usr/bin/env python3
"""
Example usage of the WiFi Network Scanner functions
"""

import sys
sys.path.insert(0, '/home/user/Research')

from wifi_network_scanner import (
    get_local_network,
    scan_port,
    COMMON_PORTS
)

def demo_functions():
    """Demonstrate the scanner functions"""

    print("=" * 70)
    print("WiFi Network Scanner - Function Demo")
    print("=" * 70)

    # Demo 1: Network detection
    print("\n1. Network Detection:")
    network = get_local_network()
    if network:
        print(f"   ✓ Detected network: {network}")
    else:
        print("   ✗ Could not detect network")

    # Demo 2: Port scanning function
    print("\n2. Port Scanning Functions:")
    print(f"   Common ports to scan: {len(COMMON_PORTS)} ports")
    print(f"   Port list: {COMMON_PORTS[:10]}... (showing first 10)")

    # Demo 3: Example scan results (simulated)
    print("\n3. Example Scan Results (from a typical home network):")
    print("\n   [+] Host: 192.168.1.1 (router.home)")
    print("       Pingable: Yes")
    print("       Open Ports:")
    print("          -    80/tcp  http")
    print("          -   443/tcp  https")

    print("\n   [+] Host: 192.168.1.25 (desktop-pc)")
    print("       Pingable: Yes")
    print("       Open Ports:")
    print("          -    22/tcp  ssh")
    print("          -  3389/tcp  ms-wbt-server")

    print("\n   [+] Host: 192.168.1.50 (nas-server)")
    print("       Pingable: Yes")
    print("       Open Ports:")
    print("          -    21/tcp  ftp")
    print("          -    22/tcp  ssh")
    print("          -    80/tcp  http")
    print("          -   445/tcp  microsoft-ds")
    print("          -  8080/tcp  http-alt")

    # Demo 4: Usage examples
    print("\n4. Usage Examples:")
    print("   Basic scan:")
    print("   $ python3 wifi_network_scanner.py")

    print("\n   Scan specific network:")
    print("   $ python3 wifi_network_scanner.py -n 192.168.1.0/24")

    print("\n   Ping only (fast host discovery):")
    print("   $ python3 wifi_network_scanner.py --ping-only")

    print("\n   Scan specific ports:")
    print("   $ python3 wifi_network_scanner.py -p 22,80,443")

    print("\n   Scan all common ports:")
    print("   $ python3 wifi_network_scanner.py --all-ports")

    print("\n" + "=" * 70)
    print("Scanner ready! Use on your own network for:")
    print("  • Network discovery and mapping")
    print("  • Security auditing")
    print("  • Finding open services")
    print("  • Troubleshooting network issues")
    print("=" * 70)

if __name__ == "__main__":
    demo_functions()
