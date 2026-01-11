"""
VPN Location Model
Represents a VPN server location with connection details
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class VPNLocation:
    """Represents a VPN server location"""

    id: str
    name: str
    country: str
    city: str
    server_address: str
    port: int
    protocol: str = "openvpn"
    username: Optional[str] = None
    password: Optional[str] = None
    config_file: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.name} ({self.city}, {self.country})"

    def to_dict(self) -> dict:
        """Convert location to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "country": self.country,
            "city": self.city,
            "server_address": self.server_address,
            "port": self.port,
            "protocol": self.protocol,
            "username": self.username,
            "password": self.password,
            "config_file": self.config_file,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'VPNLocation':
        """Create location from dictionary"""
        # Handle metadata field for backward compatibility
        if 'metadata' not in data:
            data['metadata'] = {}
        return cls(**data)
