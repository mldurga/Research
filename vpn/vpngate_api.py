"""
VPNGate API Client
Fetches real free VPN servers from VPN Gate (University of Tsukuba)
"""

import urllib.request
import base64
import csv
from typing import List, Optional
from io import StringIO
from vpn_location import VPNLocation


class VPNGateAPI:
    """Client for VPN Gate public VPN service API"""

    API_URL = "https://www.vpngate.net/api/iphone/"

    def __init__(self):
        self.servers = []

    def fetch_servers(self, min_speed: int = 1000000, max_servers: int = 50) -> List[VPNLocation]:
        """
        Fetch active VPN servers from VPN Gate

        Args:
            min_speed: Minimum speed in bytes/sec (default 1 Mbps)
            max_servers: Maximum number of servers to return

        Returns:
            List of VPNLocation objects
        """
        try:
            print("Fetching VPN servers from VPN Gate...")

            # Fetch CSV data from VPN Gate API
            response = urllib.request.urlopen(self.API_URL, timeout=10)
            data = response.read().decode('utf-8')

            # Parse CSV (skip first 2 lines which are comments)
            lines = data.split('\n')
            csv_data = '\n'.join(lines[2:])  # Skip header comments

            reader = csv.reader(StringIO(csv_data))
            headers = next(reader)  # Get column names

            servers = []
            for row in reader:
                if len(row) < 15:  # Skip incomplete rows
                    continue

                try:
                    # Parse server data
                    # CSV format: HostName,IP,Score,Ping,Speed,CountryLong,CountryShort,
                    #             NumVpnSessions,Uptime,TotalUsers,TotalTraffic,LogType,
                    #             Operator,Message,OpenVPN_ConfigData_Base64

                    hostname = row[0]
                    ip = row[1]
                    score = int(row[2]) if row[2] else 0
                    ping = int(row[3]) if row[3] else 9999
                    speed = int(row[4]) if row[4] else 0
                    country = row[5]
                    country_code = row[6]
                    openvpn_config_base64 = row[14]

                    # Filter by speed
                    if speed < min_speed:
                        continue

                    # Skip if no OpenVPN config
                    if not openvpn_config_base64:
                        continue

                    # Create VPNLocation
                    location = VPNLocation(
                        id=f"vpngate-{country_code.lower()}-{hostname[:8]}",
                        name=f"VPNGate {country}",
                        country=country,
                        city=hostname.split('.')[0] if '.' in hostname else "Unknown",
                        server_address=ip,
                        port=1194,  # Standard OpenVPN port
                        protocol="openvpn",
                        metadata={
                            'hostname': hostname,
                            'score': score,
                            'ping': ping,
                            'speed': speed,
                            'speed_mbps': round(speed / 1000000, 2),
                            'openvpn_config': openvpn_config_base64
                        }
                    )

                    servers.append(location)

                    if len(servers) >= max_servers:
                        break

                except (ValueError, IndexError) as e:
                    continue  # Skip problematic rows

            # Sort by score (best first)
            servers.sort(key=lambda x: x.metadata.get('score', 0), reverse=True)

            self.servers = servers
            print(f"Found {len(servers)} VPN servers")
            return servers

        except Exception as e:
            print(f"Error fetching VPN Gate servers: {e}")
            return []

    def get_openvpn_config(self, location: VPNLocation) -> Optional[str]:
        """
        Get decoded OpenVPN configuration for a location

        Args:
            location: VPNLocation object

        Returns:
            OpenVPN configuration string or None
        """
        if not location.metadata or 'openvpn_config' not in location.metadata:
            return None

        try:
            config_base64 = location.metadata['openvpn_config']
            config_bytes = base64.b64decode(config_base64)
            config_str = config_bytes.decode('utf-8')
            return config_str
        except Exception as e:
            print(f"Error decoding OpenVPN config: {e}")
            return None

    def save_openvpn_config(self, location: VPNLocation, filename: str) -> bool:
        """
        Save OpenVPN configuration to file

        Args:
            location: VPNLocation object
            filename: Output filename

        Returns:
            True if successful, False otherwise
        """
        config = self.get_openvpn_config(location)
        if not config:
            return False

        try:
            with open(filename, 'w') as f:
                f.write(config)
            print(f"Saved OpenVPN config to {filename}")
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get_servers_by_country(self, country: str) -> List[VPNLocation]:
        """Get all servers for a specific country"""
        return [s for s in self.servers if country.lower() in s.country.lower()]

    def get_fastest_server(self) -> Optional[VPNLocation]:
        """Get the fastest available server"""
        if not self.servers:
            return None
        return max(self.servers, key=lambda x: x.metadata.get('speed', 0))

    def get_lowest_ping_server(self) -> Optional[VPNLocation]:
        """Get server with lowest ping"""
        if not self.servers:
            return None
        return min(self.servers, key=lambda x: x.metadata.get('ping', 9999))
