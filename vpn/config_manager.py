"""
VPN Configuration Manager
Handles loading and saving VPN configurations and locations
"""

import json
import os
from typing import List, Optional
from vpn_location import VPNLocation


class ConfigManager:
    """Manages VPN configuration and available locations"""

    def __init__(self, config_path: str = "vpn_config.json"):
        self.config_path = config_path
        self.locations: List[VPNLocation] = []
        self.current_location_id: Optional[str] = None
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.locations = [
                        VPNLocation.from_dict(loc)
                        for loc in data.get('locations', [])
                    ]
                    self.current_location_id = data.get('current_location_id')
            except Exception as e:
                print(f"Error loading config: {e}")
                self._create_default_config()
        else:
            self._create_default_config()

    def save_config(self) -> None:
        """Save configuration to file"""
        data = {
            'locations': [loc.to_dict() for loc in self.locations],
            'current_location_id': self.current_location_id
        }
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _create_default_config(self) -> None:
        """Create default configuration with sample locations"""
        self.locations = [
            VPNLocation(
                id="us-ny-01",
                name="US New York 01",
                country="United States",
                city="New York",
                server_address="us-ny-01.vpn.example.com",
                port=1194
            ),
            VPNLocation(
                id="uk-lon-01",
                name="UK London 01",
                country="United Kingdom",
                city="London",
                server_address="uk-lon-01.vpn.example.com",
                port=1194
            ),
            VPNLocation(
                id="jp-tok-01",
                name="Japan Tokyo 01",
                country="Japan",
                city="Tokyo",
                server_address="jp-tok-01.vpn.example.com",
                port=1194
            ),
            VPNLocation(
                id="de-ber-01",
                name="Germany Berlin 01",
                country="Germany",
                city="Berlin",
                server_address="de-ber-01.vpn.example.com",
                port=1194
            ),
            VPNLocation(
                id="au-syd-01",
                name="Australia Sydney 01",
                country="Australia",
                city="Sydney",
                server_address="au-syd-01.vpn.example.com",
                port=1194
            )
        ]
        self.save_config()

    def get_location(self, location_id: str) -> Optional[VPNLocation]:
        """Get location by ID"""
        for loc in self.locations:
            if loc.id == location_id:
                return loc
        return None

    def get_all_locations(self) -> List[VPNLocation]:
        """Get all available locations"""
        return self.locations

    def add_location(self, location: VPNLocation) -> None:
        """Add a new location"""
        self.locations.append(location)
        self.save_config()

    def remove_location(self, location_id: str) -> bool:
        """Remove a location by ID"""
        for i, loc in enumerate(self.locations):
            if loc.id == location_id:
                self.locations.pop(i)
                self.save_config()
                return True
        return False

    def set_current_location(self, location_id: str) -> bool:
        """Set the current location"""
        if self.get_location(location_id):
            self.current_location_id = location_id
            self.save_config()
            return True
        return False

    def get_current_location(self) -> Optional[VPNLocation]:
        """Get the current location"""
        if self.current_location_id:
            return self.get_location(self.current_location_id)
        return None
