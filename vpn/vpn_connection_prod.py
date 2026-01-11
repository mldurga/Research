"""
Production VPN Connection Manager
Handles REAL VPN connections using OpenVPN
"""

import subprocess
import time
import os
import signal
import tempfile
from typing import Optional
from enum import Enum
from vpn_location import VPNLocation
from vpngate_api import VPNGateAPI


class ConnectionStatus(Enum):
    """VPN connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


class VPNConnectionProd:
    """Production VPN connection manager"""

    def __init__(self):
        self.status = ConnectionStatus.DISCONNECTED
        self.current_location: Optional[VPNLocation] = None
        self.process: Optional[subprocess.Popen] = None
        self.connection_time: Optional[float] = None
        self.config_file: Optional[str] = None
        self.vpngate_api = VPNGateAPI()

    def check_openvpn_installed(self) -> bool:
        """Check if OpenVPN is installed"""
        try:
            result = subprocess.run(
                ["which", "openvpn"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def check_root_privileges(self) -> bool:
        """Check if running with root privileges"""
        return os.geteuid() == 0

    def connect(self, location: VPNLocation, use_vpngate: bool = True) -> bool:
        """
        Connect to VPN location

        Args:
            location: VPNLocation to connect to
            use_vpngate: If True, use VPNGate API to get config

        Returns:
            bool: True if connection successful, False otherwise
        """
        # Pre-flight checks
        if not self.check_openvpn_installed():
            print("ERROR: OpenVPN is not installed!")
            print("Install with: sudo apt-get install openvpn")
            return False

        if not self.check_root_privileges():
            print("ERROR: Root privileges required!")
            print("Run with: sudo python ...")
            return False

        if self.status == ConnectionStatus.CONNECTED:
            print(f"Already connected to {self.current_location}")
            return False

        print(f"Connecting to {location}...")
        self.status = ConnectionStatus.CONNECTING
        self.current_location = location

        try:
            # Get OpenVPN configuration
            if use_vpngate and location.metadata.get('openvpn_config'):
                # Use VPNGate config
                config_content = self.vpngate_api.get_openvpn_config(location)
                if not config_content:
                    raise Exception("Failed to get OpenVPN config")

                # Create temporary config file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.ovpn', delete=False) as f:
                    f.write(config_content)
                    self.config_file = f.name

            elif location.config_file and os.path.exists(location.config_file):
                self.config_file = location.config_file
            else:
                raise Exception("No valid OpenVPN configuration available")

            # Start OpenVPN connection
            success = self._start_openvpn()

            if success:
                self.status = ConnectionStatus.CONNECTED
                self.connection_time = time.time()
                print(f"✓ Successfully connected to {location}")
                print(f"  Server: {location.server_address}")
                if location.metadata.get('speed_mbps'):
                    print(f"  Speed: {location.metadata['speed_mbps']} Mbps")
                return True
            else:
                self.status = ConnectionStatus.ERROR
                self.current_location = None
                print(f"✗ Failed to connect to {location}")
                return False

        except Exception as e:
            print(f"Connection error: {e}")
            self.status = ConnectionStatus.ERROR
            self.current_location = None
            if self.config_file and self.config_file.startswith('/tmp'):
                try:
                    os.unlink(self.config_file)
                except:
                    pass
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
                # Send SIGTERM to OpenVPN process
                self.process.send_signal(signal.SIGTERM)
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if doesn't terminate
                    self.process.kill()
                    self.process.wait()
                self.process = None

            # Clean up temp config file
            if self.config_file and self.config_file.startswith('/tmp'):
                try:
                    os.unlink(self.config_file)
                except:
                    pass
                self.config_file = None

            self.status = ConnectionStatus.DISCONNECTED
            print(f"✓ Disconnected from {self.current_location}")
            self.current_location = None
            self.connection_time = None
            return True

        except Exception as e:
            print(f"Disconnection error: {e}")
            self.status = ConnectionStatus.ERROR
            return False

    def _start_openvpn(self) -> bool:
        """Start OpenVPN process"""
        try:
            cmd = [
                "openvpn",
                "--config", self.config_file,
                "--daemon"  # Run in background
            ]

            print(f"Starting OpenVPN: {' '.join(cmd)}")

            # Start OpenVPN process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait a bit for connection to establish
            time.sleep(3)

            # Check if process is still running
            if self.process.poll() is None:
                # Process is running
                return True
            else:
                # Process exited
                stdout, stderr = self.process.communicate()
                print(f"OpenVPN failed to start:")
                if stderr:
                    print(stderr)
                return False

        except Exception as e:
            print(f"Failed to start OpenVPN: {e}")
            return False

    def get_status(self) -> dict:
        """Get current connection status"""
        status_info = {
            "status": self.status.value,
            "location": str(self.current_location) if self.current_location else None,
            "connected_since": None,
            "server": None,
            "speed": None
        }

        if self.current_location:
            status_info["server"] = self.current_location.server_address
            if self.current_location.metadata.get('speed_mbps'):
                status_info["speed"] = f"{self.current_location.metadata['speed_mbps']} Mbps"

        if self.connection_time:
            duration = time.time() - self.connection_time
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            status_info["connected_since"] = f"{minutes}m {seconds}s"

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

    def test_connection(self) -> bool:
        """Test if VPN connection is working"""
        if not self.is_connected():
            return False

        try:
            # Try to ping a public server through VPN
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
