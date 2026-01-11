"""
Main VPN Client
Provides the main interface for VPN operations
"""

from typing import Optional
from config_manager import ConfigManager
from vpn_connection import VPNConnection
from location_manager import LocationManager
from vpn_location import VPNLocation


class VPNClient:
    """Main VPN client interface"""

    def __init__(self, config_path: str = "vpn_config.json"):
        self.config_manager = ConfigManager(config_path)
        self.vpn_connection = VPNConnection()
        self.location_manager = LocationManager(
            self.config_manager,
            self.vpn_connection
        )

    def connect(self, location_id: Optional[str] = None) -> bool:
        """
        Connect to VPN

        Args:
            location_id: Optional location ID. If not provided, uses quick connect

        Returns:
            bool: True if connection successful
        """
        if location_id:
            location = self.config_manager.get_location(location_id)
            if not location:
                print(f"Location '{location_id}' not found")
                return False
            self.config_manager.set_current_location(location_id)
            return self.vpn_connection.connect(location)
        else:
            return self.location_manager.quick_connect()

    def disconnect(self) -> bool:
        """Disconnect from VPN"""
        return self.vpn_connection.disconnect()

    def switch_location(self, location_id: str) -> bool:
        """Switch to a different location"""
        return self.location_manager.switch_location(location_id)

    def connect_to_country(self, country: str) -> bool:
        """Connect to any server in the specified country"""
        return self.location_manager.connect_to_country(country)

    def get_status(self) -> dict:
        """Get current VPN status"""
        status = self.vpn_connection.get_status()
        status['current_ip'] = self.vpn_connection.get_current_ip()
        return status

    def list_locations(self) -> None:
        """List all available locations"""
        locations = self.location_manager.list_available_locations()
        current = self.vpn_connection.current_location

        print("\nAvailable VPN Locations:")
        print("-" * 70)
        for loc in locations:
            marker = " (connected)" if current and current.id == loc.id else ""
            print(f"  [{loc.id}] {loc.name}")
            print(f"    Location: {loc.city}, {loc.country}")
            print(f"    Server: {loc.server_address}:{loc.port}")
            print(f"    Protocol: {loc.protocol}{marker}")
            print()

    def list_countries(self) -> None:
        """List all available countries"""
        countries = self.location_manager.list_countries()
        print("\nAvailable Countries:")
        print("-" * 40)
        for country in countries:
            locations = self.location_manager.get_locations_by_country(country)
            print(f"  {country} ({len(locations)} server(s))")

    def show_status(self) -> None:
        """Display detailed connection status"""
        status = self.get_status()
        print("\nVPN Status:")
        print("-" * 40)
        print(f"  Status: {status['status']}")
        if status['location']:
            print(f"  Location: {status['location']}")
        if status['connected_since']:
            print(f"  Connected for: {status['connected_since']}")
        if status.get('current_ip'):
            print(f"  Current IP: {status['current_ip']}")
        print()

    def add_location(self, location: VPNLocation) -> None:
        """Add a new VPN location"""
        self.config_manager.add_location(location)
        print(f"Added location: {location}")

    def remove_location(self, location_id: str) -> bool:
        """Remove a VPN location"""
        if self.config_manager.remove_location(location_id):
            print(f"Removed location: {location_id}")
            return True
        else:
            print(f"Location '{location_id}' not found")
            return False

    def get_recent_locations(self) -> None:
        """Show recently used locations"""
        recent = self.location_manager.get_recent_locations()
        if recent:
            print("\nRecent Locations:")
            print("-" * 40)
            for loc in recent:
                print(f"  {loc}")
        else:
            print("No recent locations")
