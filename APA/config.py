"""
Configuration for AVEVA Predictive Analytics MCP Server

This module provides configuration classes and settings for connecting to
the AVEVA Predictive Analytics Web API.
"""

import os
from typing import Optional
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class APAConfig:
    """Configuration for AVEVA Predictive Analytics API connections"""
    base_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    domain: Optional[str] = None
    verify_ssl: bool = True
    timeout: int = 60
    api_version: str = "v1"

    @property
    def api_base_url(self) -> str:
        """Get the full API base URL"""
        base = self.base_url.rstrip('/')
        return f"{base}/api/{self.api_version}"

    @property
    def token_url(self) -> str:
        """Get the token endpoint URL"""
        return f"{self.base_url.rstrip('/')}/token"

    @property
    def identity_url(self) -> str:
        """Get the identity endpoint URL"""
        return f"{self.base_url.rstrip('/')}/api/identity"


class EnterpriseConfig:
    """Main configuration class for the APA MCP server"""

    def __init__(self):
        self.apa = APAConfig(
            base_url=os.getenv("APA_BASE_URL", "https://localhost/avevapredictiveanalytics"),
            username=os.getenv("APA_USERNAME"),
            password=os.getenv("APA_PASSWORD"),
            domain=os.getenv("APA_DOMAIN"),
            verify_ssl=os.getenv("APA_VERIFY_SSL", "true").lower() == "true",
            timeout=int(os.getenv("APA_TIMEOUT", "60")),
            api_version=os.getenv("APA_API_VERSION", "v1")
        )

        # Server configuration
        self.server_port = int(os.getenv("SERVER_PORT", "8002"))
        self.server_host = os.getenv("SERVER_HOST", "0.0.0.0")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        # Token refresh settings
        self.token_refresh_buffer_seconds = int(os.getenv("TOKEN_REFRESH_BUFFER", "300"))


# Global configuration instance
config = EnterpriseConfig()


# Alert state definitions based on API documentation
ALERT_STATE_ICONS = {
    1: {"name": "Clear", "category": "Clear", "mode": "Resolve"},
    2: {"name": "New Alert", "category": "ActionDue", "mode": "Act"},
    3: {"name": "Pending", "category": "Pending", "mode": "Monitor"},
    4: {"name": "Sensor Issue", "category": "SensorIssue", "mode": "Investigate"},
}

# Point types as defined in the API
POINT_TYPES = {
    1: "InputSignal",
    2: "OutputClusterDistance",  # OMR
    3: "OutputActual",
    4: "OutputPredicted",
    5: "OutputDeviation",
    6: "OutputContribution",
}

# Alert threshold types
ALERT_THRESHOLD_TYPES = {
    "HighAlert": 1,
    "LowAlert": 2,
    "HighWarning": 3,
    "LowWarning": 4,
}

# Sensor result formats
SENSOR_RESULTS_FORMAT = {
    "List": 0,
    "Summary": 1,
}

# Sensor result types
SENSOR_RESULTS_TYPE = {
    "All": 0,
    "InAlert": 1,
    "NotInAlert": 2,
}

# Data record status
DATA_RECORD_STATUS = {
    "Good": 0,
    "Error": 1,
    "Questionable": 2,
}

# Deviation directions
DEVIATION_DIRECTION = {
    "Any": 0,
    "Positive": 1,
    "Negative": 2,
}

# Fault diagnostic states
FAULT_DIAGNOSTIC_STATE = {
    "Unknown": 0,
    "Active": 1,
    "Inactive": 2,
}
