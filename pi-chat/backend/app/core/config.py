"""
Configuration management using Pydantic settings
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class PISystemConfig(BaseSettings):
    """PI System configuration"""
    af_server: str = Field(alias="AFServer")
    pi_data_archive: str = Field(alias="PIDataArchive")
    default_database: str = Field(alias="DefaultDatabase")
    connection_timeout: int = Field(default=30, alias="ConnectionTimeout")
    use_windows_auth: bool = Field(default=True, alias="UseWindowsAuth")


class PIWebAPIConfig(BaseSettings):
    """PI Web API configuration"""
    base_url: str = Field(alias="BaseUrl")
    auth_mode: str = Field(default="kerberos", alias="AuthMode")
    username: str = Field(default="", alias="Username")
    password: str = Field(default="", alias="Password")
    verify_ssl: bool = Field(default=True, alias="VerifySSL")


class OllamaConfig(BaseSettings):
    """Ollama LLM configuration"""
    base_url: str = Field(default="http://localhost:11434", alias="BaseUrl")
    default_model: str = Field(default="llama3", alias="DefaultModel")
    temperature_default: float = Field(default=0.7, alias="TemperatureDefault")
    max_tokens: int = Field(default=2048, alias="MaxTokens")
    models: Dict[str, Any] = Field(default_factory=dict, alias="Models")


class VectorDBConfig(BaseSettings):
    """Vector database configuration"""
    type: str = Field(default="chromadb", alias="Type")
    persist_directory: str = Field(default="./chroma_db", alias="PersistDirectory")
    collection_name: str = Field(default="pi_metadata", alias="CollectionName")
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EmbeddingModel"
    )
    chunk_size: int = Field(default=500, alias="ChunkSize")
    chunk_overlap: int = Field(default=50, alias="ChunkOverlap")


class SecurityConfig(BaseSettings):
    """Security configuration"""
    enable_windows_auth: bool = Field(default=True, alias="EnableWindowsAuth")
    require_element_permissions: bool = Field(default=True, alias="RequireElementPermissions")
    require_point_permissions: bool = Field(default=True, alias="RequirePointPermissions")
    allowed_domains: List[str] = Field(default_factory=list, alias="AllowedDomains")
    admin_groups: List[str] = Field(default_factory=list, alias="AdminGroups")
    cache_permissions: bool = Field(default=True, alias="CachePermissions")
    cache_ttl_seconds: int = Field(default=300, alias="CacheTTLSeconds")


class APIConfig(BaseSettings):
    """API server configuration"""
    host: str = Field(default="0.0.0.0", alias="Host")
    port: int = Field(default=8000, alias="Port")
    enable_cors: bool = Field(default=True, alias="EnableCORS")
    allowed_origins: List[str] = Field(default_factory=list, alias="AllowedOrigins")
    enable_swagger: bool = Field(default=True, alias="EnableSwagger")
    log_level: str = Field(default="INFO", alias="LogLevel")


class AgentsConfig(BaseSettings):
    """Agents configuration"""
    default_timeout: int = Field(default=60, alias="DefaultTimeout")
    max_concurrent_agents: int = Field(default=5, alias="MaxConcurrentAgents")
    enable_mcp: bool = Field(default=True, alias="EnableMCP")
    mcp_tools_directory: str = Field(default="./mcp_tools", alias="MCPToolsDirectory")


class Settings:
    """Application settings loaded from appsettings.json"""

    def __init__(self):
        self.config_path = Path(__file__).parent.parent.parent / "config" / "appsettings.json"
        self._load_config()

    def _load_config(self):
        """Load configuration from JSON file"""
        if not self.config_path.exists():
            # Try example config
            example_path = self.config_path.parent / "appsettings.example.json"
            if example_path.exists():
                self.config_path = example_path
            else:
                raise FileNotFoundError(
                    f"Configuration file not found: {self.config_path}. "
                    "Please create appsettings.json from appsettings.example.json"
                )

        with open(self.config_path) as f:
            config_data = json.load(f)

        # Load configurations
        self.pi_system = PISystemConfig(**config_data.get("PISystem", {}))
        self.pi_webapi = PIWebAPIConfig(**config_data.get("PIWebAPI", {}))
        self.ollama = OllamaConfig(**config_data.get("Ollama", {}))
        self.vector_db = VectorDBConfig(**config_data.get("VectorDB", {}))
        self.security = SecurityConfig(**config_data.get("Security", {}))
        self.api_config = APIConfig(**config_data.get("API", {}))
        self.agents = AgentsConfig(**config_data.get("Agents", {}))

        # Convenience properties
        self.host = self.api_config.host
        self.port = self.api_config.port
        self.debug = self.api_config.log_level == "DEBUG"
        self.allowed_origins = self.api_config.allowed_origins
        self.enable_swagger = self.api_config.enable_swagger
        self.use_af_sdk = True  # Primary choice

    def reload(self):
        """Reload configuration from file"""
        self._load_config()


# Global settings instance
settings = Settings()
