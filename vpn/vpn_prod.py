#!/usr/bin/env python3
"""
Production VPN Client CLI
Connects to REAL free VPN servers from VPN Gate
"""

import sys
import argparse
import os
from vpngate_api import VPNGateAPI
from vpn_connection_prod import VPNConnectionProd


class VPNProductionCLI:
    """Production VPN CLI"""

    def __init__(self):
        self.api = VPNGateAPI()
        self.connection = VPNConnectionProd()
        self.servers = []

    def fetch_servers(self, min_speed: int = 5000000, max_servers: int = 30):
        """Fetch available VPN servers"""
        print("=" * 70)
        print("Fetching free VPN servers from VPN Gate...")
        print("=" * 70)
        self.servers = self.api.fetch_servers(min_speed=min_speed, max_servers=max_servers)
        return len(self.servers) > 0

    def list_servers(self):
        """List available VPN servers"""
        if not self.servers:
            if not self.fetch_servers():
                print("No servers available")
                return

        print("\n" + "=" * 70)
        print("Available Free VPN Servers")
        print("=" * 70)

        for i, server in enumerate(self.servers, 1):
            speed_mbps = server.metadata.get('speed_mbps', 0)
            ping = server.metadata.get('ping', '?')
            score = server.metadata.get('score', 0)

            print(f"\n[{i}] {server.name}")
            print(f"    Country: {server.country}")
            print(f"    Server: {server.server_address}")
            print(f"    Speed: {speed_mbps} Mbps | Ping: {ping}ms | Score: {score}")

        print("\n" + "=" * 70)

    def connect(self, server_index: int = 1):
        """Connect to VPN server"""
        if not self.servers:
            if not self.fetch_servers():
                print("ERROR: No servers available")
                return False

        if server_index < 1 or server_index > len(self.servers):
            print(f"ERROR: Invalid server index. Choose 1-{len(self.servers)}")
            return False

        # Check prerequisites
        if not self.connection.check_openvpn_installed():
            print("\n" + "!" * 70)
            print("ERROR: OpenVPN is not installed!")
            print("!" * 70)
            print("\nInstall OpenVPN first:")
            print("  Ubuntu/Debian: sudo apt-get install openvpn")
            print("  CentOS/RHEL:   sudo yum install openvpn")
            print("  macOS:         brew install openvpn")
            return False

        if not self.connection.check_root_privileges():
            print("\n" + "!" * 70)
            print("ERROR: Root privileges required to create VPN connection")
            print("!" * 70)
            print("\nPlease run with sudo:")
            print(f"  sudo python3 {sys.argv[0]} connect {server_index}")
            return False

        server = self.servers[server_index - 1]

        print("\n" + "=" * 70)
        print(f"Connecting to: {server.name} ({server.country})")
        print(f"Server: {server.server_address}")
        print(f"Speed: {server.metadata.get('speed_mbps')} Mbps")
        print("=" * 70)

        # Get current IP before connection
        print("\nChecking your current IP...")
        ip_before = self.connection.get_current_ip()
        if ip_before:
            print(f"Current IP: {ip_before}")

        # Connect
        success = self.connection.connect(server, use_vpngate=True)

        if success:
            print("\n" + "✓" * 70)
            print("VPN CONNECTION ESTABLISHED!")
            print("✓" * 70)

            # Get new IP after connection
            print("\nVerifying new IP...")
            ip_after = self.connection.get_current_ip()
            if ip_after:
                print(f"New IP: {ip_after}")
                if ip_before and ip_after != ip_before:
                    print("✓ IP address changed successfully!")

            print("\nYou are now connected to the VPN.")
            print("Use 'disconnect' command to disconnect.")
            return True
        else:
            print("\n" + "✗" * 70)
            print("CONNECTION FAILED")
            print("✗" * 70)
            print("\nTroubleshooting:")
            print("1. Try a different server")
            print("2. Check your internet connection")
            print("3. Make sure you have root privileges")
            return False

    def disconnect(self):
        """Disconnect from VPN"""
        if not self.connection.is_connected():
            print("Not connected to any VPN")
            return False

        success = self.connection.disconnect()
        if success:
            print("\n" + "✓" * 70)
            print("VPN DISCONNECTED")
            print("✓" * 70)
        return success

    def status(self):
        """Show VPN status"""
        status = self.connection.get_status()

        print("\n" + "=" * 70)
        print("VPN Status")
        print("=" * 70)
        print(f"Status: {status['status'].upper()}")

        if status['location']:
            print(f"Location: {status['location']}")
            print(f"Server: {status['server']}")
            if status['speed']:
                print(f"Speed: {status['speed']}")
            if status['connected_since']:
                print(f"Connected for: {status['connected_since']}")

        # Show current IP
        current_ip = self.connection.get_current_ip()
        if current_ip:
            print(f"Current IP: {current_ip}")

        print("=" * 70)

    def connect_to_country(self, country: str):
        """Connect to any server in specified country"""
        if not self.servers:
            if not self.fetch_servers():
                print("ERROR: No servers available")
                return False

        # Find servers in country
        country_servers = [s for s in self.servers
                          if country.lower() in s.country.lower()]

        if not country_servers:
            print(f"No servers found in {country}")
            print("\nAvailable countries:")
            countries = set(s.country for s in self.servers)
            for c in sorted(countries):
                print(f"  - {c}")
            return False

        # Use fastest server in country
        best_server = max(country_servers,
                         key=lambda x: x.metadata.get('speed', 0))
        server_index = self.servers.index(best_server) + 1

        print(f"Found {len(country_servers)} server(s) in {country}")
        print(f"Using fastest: {best_server.name}")

        return self.connect(server_index)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Production VPN Client - Connect to free VPN servers worldwide',
        epilog='Examples:\n'
               '  sudo python3 vpn_prod.py list              # List servers\n'
               '  sudo python3 vpn_prod.py connect 1         # Connect to server #1\n'
               '  sudo python3 vpn_prod.py country Japan     # Connect to Japan\n'
               '  sudo python3 vpn_prod.py disconnect        # Disconnect\n'
               '  sudo python3 vpn_prod.py status            # Show status\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('command',
                       choices=['list', 'connect', 'disconnect', 'status', 'country'],
                       help='Command to execute')
    parser.add_argument('arg', nargs='?', default='1',
                       help='Server index (for connect) or country name (for country)')
    parser.add_argument('--speed', type=int, default=5,
                       help='Minimum speed in Mbps (default: 5)')
    parser.add_argument('--max', type=int, default=30,
                       help='Maximum servers to fetch (default: 30)')

    args = parser.parse_args()

    cli = VPNProductionCLI()

    try:
        if args.command == 'list':
            cli.fetch_servers(min_speed=args.speed * 1000000, max_servers=args.max)
            cli.list_servers()

        elif args.command == 'connect':
            try:
                server_index = int(args.arg)
            except ValueError:
                print(f"ERROR: Server index must be a number")
                return 1

            cli.fetch_servers(min_speed=args.speed * 1000000, max_servers=args.max)
            success = cli.connect(server_index)
            return 0 if success else 1

        elif args.command == 'country':
            if not args.arg or args.arg == '1':
                print("ERROR: Please specify a country name")
                print("Example: sudo python3 vpn_prod.py country Japan")
                return 1

            cli.fetch_servers(min_speed=args.speed * 1000000, max_servers=args.max)
            success = cli.connect_to_country(args.arg)
            return 0 if success else 1

        elif args.command == 'disconnect':
            cli.disconnect()

        elif args.command == 'status':
            cli.status()

        return 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
