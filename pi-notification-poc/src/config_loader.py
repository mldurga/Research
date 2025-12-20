"""
Configuration Loader Module
Loads and validates configuration from YAML file.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    """Load and manage configuration."""

    def __init__(self, config_path: str = None):
        """
        Initialize configuration loader.

        Args:
            config_path: Path to configuration file
        """
        if config_path is None:
            # Default to config/config.yaml relative to project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / 'config' / 'config.yaml'

        self.config_path = Path(config_path)

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file not found
            yaml.YAMLError: If config file is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r') as file:
            config = yaml.safe_load(file)

        # Validate configuration
        self._validate_config(config)

        return config

    def _validate_config(self, config: Dict[str, Any]):
        """
        Validate configuration structure.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        required_sections = ['email', 'pdf', 'ollama', 'pi', 'logging', 'service']

        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")

        # Validate email section
        if 'target_subject' not in config['email']:
            raise ValueError("Missing 'target_subject' in email configuration")

        # Validate ollama section
        if 'base_url' not in config['ollama']:
            raise ValueError("Missing 'base_url' in ollama configuration")
        if 'model' not in config['ollama']:
            raise ValueError("Missing 'model' in ollama configuration")

        # Validate PI section
        if 'server_name' not in config['pi']:
            raise ValueError("Missing 'server_name' in PI configuration")

    def get_log_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract logging configuration.

        Args:
            config: Full configuration dictionary

        Returns:
            Logging configuration
        """
        log_config = config.get('logging', {})

        # Ensure log directory exists
        log_file = log_config.get('file_path', './logs/pi_notification.log')
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        return log_config

    def save_config(self, config: Dict[str, Any], output_path: str = None):
        """
        Save configuration to YAML file.

        Args:
            config: Configuration dictionary
            output_path: Output file path (defaults to original config path)
        """
        if output_path is None:
            output_path = self.config_path

        with open(output_path, 'w') as file:
            yaml.safe_dump(config, file, default_flow_style=False, indent=2)
