#!/usr/bin/env python3
"""
Example usage of the VPN Client library
"""

from vpn_client import VPNClient
from vpn_location import VPNLocation


def main():
    """Demonstrate VPN client usage"""

    print("=" * 60)
    print("VPN Client with Location Switching - Example Usage")
    print("=" * 60)

    # Initialize the VPN client
    client = VPNClient()

    # Example 1: List all available locations
    print("\n1. Listing all available VPN locations:")
    client.list_locations()

    # Example 2: Show available countries
    print("\n2. Listing available countries:")
    client.list_countries()

    # Example 3: Quick connect (uses default or first available location)
    print("\n3. Quick connect to VPN:")
    client.connect()

    # Example 4: Show connection status
    print("\n4. Checking VPN status:")
    client.show_status()

    # Example 5: Switch to a different location
    print("\n5. Switching to UK location:")
    client.switch_location("uk-lon-01")
    client.show_status()

    # Example 6: Connect to a specific country
    print("\n6. Connecting to Japan:")
    client.connect_to_country("Japan")
    client.show_status()

    # Example 7: Connect to specific location
    print("\n7. Connecting to specific location (Germany):")
    client.disconnect()
    client.connect("de-ber-01")
    client.show_status()

    # Example 8: Add a new custom location
    print("\n8. Adding a new custom location:")
    new_location = VPNLocation(
        id="fr-par-01",
        name="France Paris 01",
        country="France",
        city="Paris",
        server_address="fr-par-01.vpn.example.com",
        port=1194,
        protocol="openvpn"
    )
    client.add_location(new_location)
    client.list_locations()

    # Example 9: Get recent locations
    print("\n9. Showing recent locations:")
    client.get_recent_locations()

    # Example 10: Disconnect from VPN
    print("\n10. Disconnecting from VPN:")
    client.disconnect()
    client.show_status()

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
