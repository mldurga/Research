import os
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, use environment variables directly
    pass

@dataclass
class PISystemConfig:
    """Configuration for PI System connections"""
    pi_web_api_url: str
    af_server_name: str
    af_database_name: str
    data_server_name: str
    username: Optional[str] = None
    password: Optional[str] = None
    auth_type: str = "windows"  # windows, basic, kerberos
    verify_ssl: bool = True
    timeout: int = 30

@dataclass
class ChromaDBConfig:
    """Configuration for ChromaDB vector database"""
    client_type: str = "persistent"  # persistent, ephemeral, http, cloud
    data_dir: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    tenant: Optional[str] = None
    database: Optional[str] = None
    api_key: Optional[str] = None
    ssl: bool = True
    collection_name: str = "af_elements"

@dataclass
class IndexingConfig:
    """Configuration for automatic indexing"""
    enabled: bool = True
    refresh_interval_hours: int = 24
    batch_size: int = 1000
    max_depth: int = 10
    include_attributes: bool = True
    include_templates: bool = True
    include_eventframes: bool = False

# Enterprise-specific configuration
class EnterpriseConfig:
    """Main configuration class for the enterprise MCP server"""
    
    def __init__(self):
        # PI System Configuration
        self.pi_system = PISystemConfig(
            pi_web_api_url=os.getenv("PI_WEBAPI_URL", "https://ddoddi-int.dev.osisoft.int/piwebapi"),
            af_server_name=os.getenv("AF_SERVER_NAME", "DDODDI-AF"),
            af_database_name=os.getenv("AF_DATABASE_NAME", "APA-PI-Integration"),
            data_server_name=os.getenv("DATA_SERVER_NAME", "DDODDI-DA"),
            username=os.getenv("PI_USERNAME"),
            password=os.getenv("PI_PASSWORD"),
            auth_type=os.getenv("PI_AUTH_METHOD", "windows"),
            verify_ssl=os.getenv("PI_VERIFY_SSL", "true").lower() == "true",
            timeout=int(os.getenv("PI_TIMEOUT", "30"))
        )
        
        # ChromaDB Configuration
        self.chroma = ChromaDBConfig(
            client_type=os.getenv("CHROMA_CLIENT_TYPE", "persistent"),
            data_dir=os.getenv("CHROMA_DATA_DIR", "./chroma_data"),
            host=os.getenv("CHROMA_HOST"),
            port=int(os.getenv("CHROMA_PORT", "8000")) if os.getenv("CHROMA_PORT") else None,
            tenant=os.getenv("CHROMA_TENANT"),
            database=os.getenv("CHROMA_DATABASE"),
            api_key=os.getenv("CHROMA_API_KEY"),
            ssl=os.getenv("CHROMA_SSL", "true").lower() == "true",
            collection_name=os.getenv("CHROMA_COLLECTION", "af_elements")
        )
        
        # Indexing Configuration
        self.indexing = IndexingConfig(
            enabled=os.getenv("INDEXING_ENABLED", "true").lower() == "true",
            refresh_interval_hours=int(os.getenv("INDEXING_REFRESH_HOURS", "24")),
            batch_size=int(os.getenv("INDEXING_BATCH_SIZE", "1000")),
            max_depth=int(os.getenv("INDEXING_MAX_DEPTH", "10")),
            include_attributes=os.getenv("INDEXING_INCLUDE_ATTRIBUTES", "true").lower() == "true",
            include_templates=os.getenv("INDEXING_INCLUDE_TEMPLATES", "true").lower() == "true",
            include_eventframes=os.getenv("INDEXING_INCLUDE_EVENTFRAMES", "false").lower() == "true"
        )
    
    @property
    def af_database_path(self) -> str:
        """Get the full AF database path"""
        return f"\\\\{self.pi_system.af_server_name}\\{self.pi_system.af_database_name}"
    
    @property
    def data_server_path(self) -> str:
        """Get the full data server path"""
        return f"\\\\{self.pi_system.data_server_name}"

# Global configuration instance
config = EnterpriseConfig()

# Common AF element templates and their purposes
AF_TEMPLATE_CATEGORIES = {
    "BAS.1.Containers.L2": "Level 2 Container",
    "BAS.1.Containers.L3": "Level 3 Container", 
    "BAS.3.Acc.Sensors.SimpleAnalog": "Analog Sensor",
    "APA.3.Acc.Integ.APAConfig.Tpl": "APA Configuration",
    "Enterprise": "Enterprise Root Element"
}

# Commonly searched element types
ELEMENT_SEARCH_PATTERNS = {
    "sensors": ["sensor", "measurement", "analog", "digital"],
    "containers": ["container", "unit", "area", "plant"],
    "equipment": ["pump", "valve", "motor", "generator", "turbine"],
    "processes": ["process", "operation", "control", "automation"],
    "monitoring": ["alarm", "alert", "warning", "status"]
}

# Attribute categories for enhanced search
ATTRIBUTE_CATEGORIES = {
    "measurements": ["temperature", "pressure", "flow", "level", "power"],
    "status": ["status", "state", "alarm", "alert", "health"],
    "control": ["setpoint", "output", "control", "command"],
    "configuration": ["config", "parameter", "setting", "limit"]
}
