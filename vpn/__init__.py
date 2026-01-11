"""
VPN Client Package with Location Switching
"""

from vpn_location import VPNLocation
from config_manager import ConfigManager
from vpn_connection import VPNConnection, ConnectionStatus
from location_manager import LocationManager
from vpn_client import VPNClient

__version__ = "1.0.0"
__all__ = [
    'VPNLocation',
    'ConfigManager',
    'VPNConnection',
    'ConnectionStatus',
    'LocationManager',
    'VPNClient'
]
