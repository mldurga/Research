#!/usr/bin/env python3
"""
VPN CLI - Command Line Interface for VPN operations
"""

import argparse
import sys
from vpn_client import VPNClient
from vpn_location import VPNLocation


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="VPN Client with Location Switching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vpn_cli.py connect                    # Quick connect to default location
  vpn_cli.py connect --location us-ny-01 # Connect to specific location
  vpn_cli.py disconnect                 # Disconnect from VPN
  vpn_cli.py status                     # Show connection status
  vpn_cli.py list                       # List all locations
  vpn_cli.py switch us-ny-01            # Switch to different location
  vpn_cli.py country "United Kingdom"   # Connect to UK server
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Connect command
    connect_parser = subparsers.add_parser('connect', help='Connect to VPN')
    connect_parser.add_argument(
        '-l', '--location',
        help='Location ID to connect to'
    )

    # Disconnect command
    subparsers.add_parser('disconnect', help='Disconnect from VPN')

    # Status command
    subparsers.add_parser('status', help='Show VPN status')

    # List command
    subparsers.add_parser('list', help='List all available locations')

    # Countries command
    subparsers.add_parser('countries', help='List all available countries')

    # Switch command
    switch_parser = subparsers.add_parser('switch', help='Switch to different location')
    switch_parser.add_argument('location_id', help='Location ID to switch to')

    # Country command
    country_parser = subparsers.add_parser('country', help='Connect to country')
    country_parser.add_argument('country_name', help='Country name')

    # Recent command
    subparsers.add_parser('recent', help='Show recent locations')

    # Add location command
    add_parser = subparsers.add_parser('add', help='Add new VPN location')
    add_parser.add_argument('--id', required=True, help='Location ID')
    add_parser.add_argument('--name', required=True, help='Location name')
    add_parser.add_argument('--country', required=True, help='Country')
    add_parser.add_argument('--city', required=True, help='City')
    add_parser.add_argument('--server', required=True, help='Server address')
    add_parser.add_argument('--port', type=int, default=1194, help='Server port')
    add_parser.add_argument('--protocol', default='openvpn', help='Protocol (openvpn/wireguard)')
    add_parser.add_argument('--config', help='Config file path')

    # Remove location command
    remove_parser = subparsers.add_parser('remove', help='Remove VPN location')
    remove_parser.add_argument('location_id', help='Location ID to remove')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize VPN client
    client = VPNClient()

    # Handle commands
    if args.command == 'connect':
        success = client.connect(args.location)
        return 0 if success else 1

    elif args.command == 'disconnect':
        success = client.disconnect()
        return 0 if success else 1

    elif args.command == 'status':
        client.show_status()
        return 0

    elif args.command == 'list':
        client.list_locations()
        return 0

    elif args.command == 'countries':
        client.list_countries()
        return 0

    elif args.command == 'switch':
        success = client.switch_location(args.location_id)
        return 0 if success else 1

    elif args.command == 'country':
        success = client.connect_to_country(args.country_name)
        return 0 if success else 1

    elif args.command == 'recent':
        client.get_recent_locations()
        return 0

    elif args.command == 'add':
        location = VPNLocation(
            id=args.id,
            name=args.name,
            country=args.country,
            city=args.city,
            server_address=args.server,
            port=args.port,
            protocol=args.protocol,
            config_file=args.config
        )
        client.add_location(location)
        return 0

    elif args.command == 'remove':
        success = client.remove_location(args.location_id)
        return 0 if success else 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
