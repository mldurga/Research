"""
Location Manager
Handles switching between VPN locations and managing location preferences
"""

from typing import List, Optional
from vpn_location import VPNLocation
from config_manager import ConfigManager
from vpn_connection import VPNConnection


class LocationManager:
    """Manages VPN location switching and preferences"""

    def __init__(self, config_manager: ConfigManager, vpn_connection: VPNConnection):
        self.config = config_manager
        self.connection = vpn_connection
        self.location_history: List[str] = []

    def switch_location(self, location_id: str, auto_reconnect: bool = True) -> bool:
        """
        Switch to a different VPN location

        Args:
            location_id: ID of the location to switch to
            auto_reconnect: Automatically reconnect to new location

        Returns:
            bool: True if switch successful, False otherwise
        """
        new_location = self.config.get_location(location_id)
        if not new_location:
            print(f"Location '{location_id}' not found")
            return False

        was_connected = self.connection.is_connected()
        current_location = self.connection.current_location

        if current_location and current_location.id == location_id:
            print(f"Already connected to {new_location}")
            return True

        if was_connected:
            print(f"Switching from {current_location} to {new_location}")
            self.connection.disconnect()

        self.config.set_current_location(location_id)

        if was_connected and auto_reconnect:
            success = self.connection.connect(new_location)
            if success:
                self._add_to_history(location_id)
            return success
        else:
            print(f"Location switched to {new_location} (not connected)")
            return True

    def quick_connect(self) -> bool:
        """
        Quickly connect to the best available location
        Currently uses the first location or last used location
        """
        current_loc = self.config.get_current_location()
        if current_loc:
            return self.connection.connect(current_loc)

        locations = self.config.get_all_locations()
        if locations:
            self.config.set_current_location(locations[0].id)
            return self.connection.connect(locations[0])

        print("No locations available")
        return False

    def connect_to_country(self, country: str) -> bool:
        """
        Connect to any server in the specified country

        Args:
            country: Country name

        Returns:
            bool: True if connection successful
        """
        locations = self.get_locations_by_country(country)
        if not locations:
            print(f"No locations found in {country}")
            return False

        return self.switch_location(locations[0].id)

    def get_locations_by_country(self, country: str) -> List[VPNLocation]:
        """Get all locations in a specific country"""
        return [
            loc for loc in self.config.get_all_locations()
            if loc.country.lower() == country.lower()
        ]

    def get_locations_by_city(self, city: str) -> List[VPNLocation]:
        """Get all locations in a specific city"""
        return [
            loc for loc in self.config.get_all_locations()
            if loc.city.lower() == city.lower()
        ]

    def list_available_locations(self) -> List[VPNLocation]:
        """List all available VPN locations"""
        return self.config.get_all_locations()

    def list_countries(self) -> List[str]:
        """List all available countries"""
        countries = set()
        for loc in self.config.get_all_locations():
            countries.add(loc.country)
        return sorted(list(countries))

    def get_fastest_location(self) -> Optional[VPNLocation]:
        """
        Get the fastest location based on ping/latency
        Currently returns first location (would need ping implementation)
        """
        locations = self.config.get_all_locations()
        if locations:
            print("Note: Returning first location (ping-based selection not implemented)")
            return locations[0]
        return None

    def _add_to_history(self, location_id: str) -> None:
        """Add location to connection history"""
        if location_id in self.location_history:
            self.location_history.remove(location_id)
        self.location_history.insert(0, location_id)
        if len(self.location_history) > 10:
            self.location_history.pop()

    def get_recent_locations(self, limit: int = 5) -> List[VPNLocation]:
        """Get recently used locations"""
        recent = []
        for loc_id in self.location_history[:limit]:
            loc = self.config.get_location(loc_id)
            if loc:
                recent.append(loc)
        return recent

    def add_favorite(self, location_id: str) -> bool:
        """Add location to favorites"""
        location = self.config.get_location(location_id)
        if location:
            print(f"Added {location} to favorites (feature placeholder)")
            return True
        return False
