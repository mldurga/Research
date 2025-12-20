"""
PI System Writer Module
Writes data to OSIsoft PI System using PIconnect.
Designed for secure ADNOC environment.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import time

try:
    import PIconnect as PI
    PI_AVAILABLE = True
except ImportError:
    PI_AVAILABLE = False
    logging.warning("PIconnect not available. PI writes will be simulated.")


class PIWriter:
    """Write data to OSIsoft PI System."""

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize the PI writer.

        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger

        # PI configuration
        self.server_name = config['pi']['server_name']
        self.auth_method = config['pi']['auth_method']
        self.username = config['pi'].get('username', '')
        self.password = config['pi'].get('password', '')
        self.timeout = config['pi']['timeout']
        self.retry_attempts = config['pi']['retry_attempts']
        self.retry_delay = config['pi']['retry_delay']
        self.tag_prefix = config['pi'].get('tag_prefix', '')

        # PI server connection
        self.server = None
        self.connected = False

        # Check if PIconnect is available
        if not PI_AVAILABLE:
            self.logger.warning("PIconnect library not available. Running in simulation mode.")

    def connect(self) -> bool:
        """
        Connect to PI Data Archive server.

        Returns:
            True if connection successful, False otherwise
        """
        if not PI_AVAILABLE:
            self.logger.warning("PIconnect not available. Simulating connection.")
            self.connected = True
            return True

        try:
            self.logger.info(f"Connecting to PI server: {self.server_name}")

            # Connect based on authentication method
            if self.auth_method.lower() == 'windows':
                # Use Windows authentication
                self.server = PI.PIServer(name=self.server_name)
            else:
                # Use explicit authentication
                if not self.username or not self.password:
                    self.logger.error("Username and password required for explicit authentication")
                    return False

                self.server = PI.PIServer(
                    name=self.server_name,
                    username=self.username,
                    password=self.password
                )

            # Test connection
            self.server.connect()
            self.connected = True

            self.logger.info(f"Successfully connected to PI server: {self.server.server_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to PI server: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from PI server."""
        try:
            if self.server:
                self.server = None
                self.connected = False
                self.logger.info("Disconnected from PI server")
        except Exception as e:
            self.logger.error(f"Error disconnecting from PI server: {e}")

    def write_value(self, tag_name: str, value: Any, timestamp: Optional[datetime] = None) -> bool:
        """
        Write a single value to a PI tag.

        Args:
            tag_name: PI tag name
            value: Value to write
            timestamp: Optional timestamp (defaults to current time)

        Returns:
            True if write successful, False otherwise
        """
        if not self.connected:
            self.logger.error("Not connected to PI server")
            return False

        # Add prefix if configured
        full_tag_name = f"{self.tag_prefix}{tag_name}" if self.tag_prefix else tag_name

        # Use current time if no timestamp provided
        if timestamp is None:
            timestamp = datetime.now()

        try:
            if not PI_AVAILABLE:
                # Simulate write
                self.logger.info(f"[SIMULATED] Writing to tag '{full_tag_name}': {value} at {timestamp}")
                return True

            # Get the PI point
            point = self.server.search(full_tag_name)

            if not point:
                self.logger.error(f"PI tag not found: {full_tag_name}")
                return False

            # Get first point from search results
            if isinstance(point, list):
                if len(point) == 0:
                    self.logger.error(f"PI tag not found: {full_tag_name}")
                    return False
                point = point[0]

            # Write value with retry logic
            for attempt in range(self.retry_attempts):
                try:
                    point.update_value(value, timestamp)
                    self.logger.info(f"Successfully wrote to tag '{full_tag_name}': {value} at {timestamp}")
                    return True

                except Exception as e:
                    if attempt < self.retry_attempts - 1:
                        self.logger.warning(f"Write attempt {attempt + 1} failed, retrying: {e}")
                        time.sleep(self.retry_delay)
                    else:
                        raise

            return False

        except Exception as e:
            self.logger.error(f"Error writing to PI tag '{full_tag_name}': {e}")
            return False

    def write_multiple_values(self, data_points: List[Dict[str, Any]]) -> Dict[str, bool]:
        """
        Write multiple values to PI tags.

        Args:
            data_points: List of dictionaries with 'tag_name', 'value', and optional 'timestamp'

        Returns:
            Dictionary mapping tag names to success status
        """
        results = {}

        for data_point in data_points:
            try:
                tag_name = data_point.get('tag_name')
                value = data_point.get('value')
                timestamp = data_point.get('timestamp')

                if not tag_name or value is None:
                    self.logger.warning(f"Invalid data point: {data_point}")
                    results[str(tag_name)] = False
                    continue

                # Parse timestamp if it's a string
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except Exception as e:
                        self.logger.warning(f"Could not parse timestamp '{timestamp}': {e}")
                        timestamp = None

                # Write value
                success = self.write_value(tag_name, value, timestamp)
                results[tag_name] = success

            except Exception as e:
                self.logger.error(f"Error processing data point: {e}")
                results[str(data_point.get('tag_name', 'unknown'))] = False

        # Log summary
        successful = sum(1 for v in results.values() if v)
        total = len(results)
        self.logger.info(f"Wrote {successful}/{total} values to PI")

        return results

    def tag_exists(self, tag_name: str) -> bool:
        """
        Check if a PI tag exists.

        Args:
            tag_name: PI tag name

        Returns:
            True if tag exists, False otherwise
        """
        if not self.connected:
            return False

        # Add prefix if configured
        full_tag_name = f"{self.tag_prefix}{tag_name}" if self.tag_prefix else tag_name

        try:
            if not PI_AVAILABLE:
                # Simulate
                self.logger.debug(f"[SIMULATED] Checking tag existence: {full_tag_name}")
                return True

            point = self.server.search(full_tag_name)

            if isinstance(point, list):
                return len(point) > 0

            return point is not None

        except Exception as e:
            self.logger.error(f"Error checking tag existence: {e}")
            return False

    def get_tag_value(self, tag_name: str) -> Optional[Any]:
        """
        Read current value from a PI tag.

        Args:
            tag_name: PI tag name

        Returns:
            Current tag value or None if failed
        """
        if not self.connected:
            return None

        # Add prefix if configured
        full_tag_name = f"{self.tag_prefix}{tag_name}" if self.tag_prefix else tag_name

        try:
            if not PI_AVAILABLE:
                # Simulate
                self.logger.debug(f"[SIMULATED] Reading tag: {full_tag_name}")
                return 0.0

            point = self.server.search(full_tag_name)

            if not point:
                self.logger.error(f"PI tag not found: {full_tag_name}")
                return None

            if isinstance(point, list):
                if len(point) == 0:
                    return None
                point = point[0]

            current_value = point.current_value
            self.logger.debug(f"Read value from '{full_tag_name}': {current_value}")

            return current_value

        except Exception as e:
            self.logger.error(f"Error reading from PI tag '{full_tag_name}': {e}")
            return None

    def create_tag(self, tag_name: str, point_type: str = 'Float32',
                   engineering_units: str = '', descriptor: str = '') -> bool:
        """
        Create a new PI tag (requires appropriate permissions).

        Args:
            tag_name: PI tag name
            point_type: PI point type (Float32, Int32, String, etc.)
            engineering_units: Engineering units
            descriptor: Tag description

        Returns:
            True if tag created successfully, False otherwise
        """
        if not self.connected:
            return False

        # Add prefix if configured
        full_tag_name = f"{self.tag_prefix}{tag_name}" if self.tag_prefix else tag_name

        try:
            if not PI_AVAILABLE:
                # Simulate
                self.logger.info(f"[SIMULATED] Creating tag: {full_tag_name}")
                return True

            # Check if tag already exists
            if self.tag_exists(tag_name):
                self.logger.warning(f"Tag already exists: {full_tag_name}")
                return True

            # Note: Tag creation typically requires PI administrator access
            # This is a placeholder - actual implementation depends on PIconnect version
            self.logger.warning("Tag creation not implemented. Please create tags manually.")
            return False

        except Exception as e:
            self.logger.error(f"Error creating PI tag '{full_tag_name}': {e}")
            return False
