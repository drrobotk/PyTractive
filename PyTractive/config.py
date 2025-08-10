"""
Configuration management for PyTractive.
"""

import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass, asdict
import json
import logging

from .exceptions import ConfigurationError
from .security import CredentialManager


logger = logging.getLogger(__name__)


@dataclass
class TractiveConfig:
    """Enhanced configuration settings for PyTractive with comprehensive options."""
    
    # API Configuration
    api_base_url: str = "https://graph.tractive.com/3"
    ifttt_base_url: str = "https://maker.ifttt.com/trigger"
    
    # Client Configuration
    user_agent: str = "Mozilla/5.0 (compatible; PyTractive/2.0)"
    client_id: str = "5728aa1fc9077f7c32000186"
    request_timeout: int = 30
    retry_attempts: int = 3
    retry_backoff_factor: float = 1.0
    
    # Rate limiting and connection management
    api_rate_limit: int = 60  # requests per minute
    connection_pool_size: int = 10
    connection_pool_maxsize: int = 20
    
    # File paths
    access_token_file: str = "access_token.txt"
    config_file: str = "pytractive_config.json"
    
    # Default settings
    default_user_id: str = "5f525ea6d3278b5d10e1442c"
    
    # GPS settings
    max_gps_fallback_hours: int = 24
    gps_retry_delay: int = 1
    gps_accuracy_threshold: float = 100.0  # meters
    
    # Caching settings
    cache_duration_seconds: int = 300  # 5 minutes
    enable_response_caching: bool = True
    
    # Logging settings
    log_api_requests: bool = False
    log_response_bodies: bool = False
    log_level: str = "INFO"
    
    # Feature flags
    enable_async_client: bool = True
    enable_location_history: bool = True
    enable_battery_monitoring: bool = True
    
    @classmethod
    def load_from_file(cls, config_path: Optional[Path] = None) -> "TractiveConfig":
        """Load configuration from JSON file."""
        if config_path is None:
            config_path = Path(cls().config_file)
        
        if not config_path.exists():
            logger.info(f"Config file {config_path} not found, using defaults")
            return cls()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Filter out any unknown keys
            valid_keys = set(cls.__dataclass_fields__.keys())
            filtered_data = {k: v for k, v in config_data.items() if k in valid_keys}
            
            return cls(**filtered_data)
        except (json.JSONDecodeError, TypeError) as e:
            raise ConfigurationError(f"Invalid config file format: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load config: {e}")
    
    def save_to_file(self, config_path: Optional[Path] = None) -> None:
        """Save configuration to JSON file."""
        if config_path is None:
            config_path = Path(self.config_file)
        
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, indent=2)
            logger.info(f"Config saved to {config_path}")
        except Exception as e:
            raise ConfigurationError(f"Failed to save config: {e}")


class ConfigManager:
    """Manages application configuration and credentials."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config = TractiveConfig.load_from_file(config_path)
        self.credential_manager = CredentialManager()
    
    def get_credentials(self) -> Tuple[str, str, Tuple[float, float]]:
        """Get user credentials from environment or secure storage."""
        try:
            # Try environment variables first
            email = os.environ.get("TRACTIVE_EMAIL")
            password = os.environ.get("TRACTIVE_PASSWORD")
            home_lat = os.environ.get("TRACTIVE_HOME_LAT")
            home_lon = os.environ.get("TRACTIVE_HOME_LON")
            
            if all([email, password, home_lat, home_lon]):
                return email, password, (float(home_lat), float(home_lon))
            
            # Fall back to secure credential storage
            return self.credential_manager.get_credentials()
            
        except Exception as e:
            raise ConfigurationError(f"Failed to get credentials: {e}")
    
    def set_credentials(
        self, 
        email: str, 
        password: str, 
        home_coordinates: Tuple[float, float]
    ) -> None:
        """Store credentials securely."""
        try:
            self.credential_manager.set_credentials(email, password, home_coordinates)
        except Exception as e:
            raise ConfigurationError(f"Failed to set credentials: {e}")
    
    def get_access_token(self) -> Optional[str]:
        """Get cached access token."""
        token_file = Path(self.config.access_token_file)
        if token_file.exists():
            try:
                return token_file.read_text(encoding='utf-8').strip()
            except Exception as e:
                logger.warning(f"Failed to read access token: {e}")
        return None
    
    def save_access_token(self, token: str) -> None:
        """Save access token to file."""
        try:
            token_file = Path(self.config.access_token_file)
            token_file.write_text(token, encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to save access token: {e}")
            raise ConfigurationError(f"Failed to save access token: {e}")
