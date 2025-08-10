"""
PyTractive - A modern Python library for Tractive GPS trackers.

This library provides a comprehensive interface to interact with Tractive GPS pet trackers,
including real-time location tracking, device control, and data export capabilities.

Features:
- Real-time GPS location tracking
- Device status monitoring  
- Remote device control (LED, buzzer, live tracking, battery saver)
- Historical GPS data export
- Pet information management
- Interactive mapping and CLI
- Async support for high-performance applications
- Comprehensive error handling and logging
"""

from .client import TractiveClient, AsyncTractiveClient
from .exceptions import (
    TractiveError, 
    AuthenticationError, 
    APIError, 
    ConfigurationError,
    TrackerNotFoundError,
    GPSDataError
)
from .models import (
    GPSLocation, 
    DeviceStatus, 
    PetData, 
    CommandType, 
    CommandState,
    DeviceState,
    ShareInfo,
    TractiveCredentials
)
from .config import TractiveConfig

__version__ = "2.0.0"
__author__ = "Dr. Usman Kayani"
__email__ = "usman.kayaniphd@gmail.com"

__all__ = [
    # Main client classes
    "TractiveClient",
    "AsyncTractiveClient",
    
    # Configuration
    "TractiveConfig",
    
    # Exceptions
    "TractiveError",
    "AuthenticationError", 
    "APIError",
    "ConfigurationError",
    "TrackerNotFoundError",
    "GPSDataError",
    
    # Data models
    "GPSLocation",
    "DeviceStatus",
    "PetData",
    "ShareInfo", 
    "TractiveCredentials",
    
    # Enums
    "CommandType",
    "CommandState",
    "DeviceState",
]
