"""
VPN Connection Manager
Handles VPN connection, disconnection, and status monitoring
"""

import subprocess
import time
from typing import Optional
from enum import Enum
from vpn_location import VPNLocation


class ConnectionStatus(Enum):
    """VPN connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


class VPNConnection:
    """Manages VPN connection lifecycle"""

    def __init__(self):
        self.status = ConnectionStatus.DISCONNECTED
        self.current_location: Optional[VPNLocation] = None
        self.process: Optional[subprocess.Popen] = None
        self.connection_time: Optional[float] = None

    def connect(self, location: VPNLocation) -> bool:
        """
        Connect to VPN location

        Args:
            location: VPNLocation to connect to

        Returns:
            bool: True if connection successful, False otherwise
        """
        if self.status == ConnectionStatus.CONNECTED:
            print(f"Already connected to {self.current_location}")
            return False

        print(f"Connecting to {location}...")
        self.status = ConnectionStatus.CONNECTING
        self.current_location = location

        try:
            if location.protocol == "openvpn":
                success = self._connect_openvpn(location)
            elif location.protocol == "wireguard":
                success = self._connect_wireguard(location)
            else:
                print(f"Unsupported protocol: {location.protocol}")
                success = False

            if success:
                self.status = ConnectionStatus.CONNECTED
                self.connection_time = time.time()
                print(f"Successfully connected to {location}")
                return True
            else:
                self.status = ConnectionStatus.ERROR
                self.current_location = None
                print(f"Failed to connect to {location}")
                return False

        except Exception as e:
            print(f"Connection error: {e}")
            self.status = ConnectionStatus.ERROR
            self.current_location = None
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from current VPN

        Returns:
            bool: True if disconnection successful, False otherwise
        """
        if self.status != ConnectionStatus.CONNECTED:
            print("Not connected to any VPN")
            return False

        print(f"Disconnecting from {self.current_location}...")
        self.status = ConnectionStatus.DISCONNECTING

        try:
            if self.process:
                self.process.terminate()
                self.process.wait(timeout=5)
                self.process = None

            self.status = ConnectionStatus.DISCONNECTED
            print(f"Disconnected from {self.current_location}")
            self.current_location = None
            self.connection_time = None
            return True

        except Exception as e:
            print(f"Disconnection error: {e}")
            self.status = ConnectionStatus.ERROR
            return False

    def _connect_openvpn(self, location: VPNLocation) -> bool:
        """Connect using OpenVPN protocol"""
        if location.config_file:
            cmd = ["openvpn", "--config", location.config_file]
        else:
            cmd = [
                "openvpn",
                "--remote", location.server_address,
                "--port", str(location.port),
                "--client",
                "--dev", "tun"
            ]

            if location.username and location.password:
                cmd.extend(["--auth-user-pass"])

        try:
            print(f"Simulating OpenVPN connection to {location.server_address}:{location.port}")
            print(f"Command: {' '.join(cmd)}")
            return True
        except Exception as e:
            print(f"OpenVPN connection failed: {e}")
            return False

    def _connect_wireguard(self, location: VPNLocation) -> bool:
        """Connect using WireGuard protocol"""
        try:
            print(f"Simulating WireGuard connection to {location.server_address}:{location.port}")
            if location.config_file:
                cmd = ["wg-quick", "up", location.config_file]
                print(f"Command: {' '.join(cmd)}")
            return True
        except Exception as e:
            print(f"WireGuard connection failed: {e}")
            return False

    def get_status(self) -> dict:
        """Get current connection status"""
        status_info = {
            "status": self.status.value,
            "location": str(self.current_location) if self.current_location else None,
            "connected_since": None
        }

        if self.connection_time:
            duration = time.time() - self.connection_time
            status_info["connected_since"] = f"{int(duration)}s"

        return status_info

    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self.status == ConnectionStatus.CONNECTED

    def get_current_ip(self) -> Optional[str]:
        """Get current public IP address"""
        try:
            result = subprocess.run(
                ["curl", "-s", "https://api.ipify.org"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            print(f"Failed to get IP: {e}")
        return None
