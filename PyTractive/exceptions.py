"""
Custom exceptions for PyTractive.
"""

from typing import Optional, Any, Dict


class TractiveError(Exception):
    """Base exception for all Tractive-related errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class AuthenticationError(TractiveError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, "AUTH_FAILED")


class APIError(TractiveError):
    """Raised when API requests fail."""
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "API_ERROR")
        self.status_code = status_code
        self.response_data = response_data


class ConfigurationError(TractiveError):
    """Raised when configuration is invalid."""
    
    def __init__(self, message: str = "Configuration error") -> None:
        super().__init__(message, "CONFIG_ERROR")


class TrackerNotFoundError(TractiveError):
    """Raised when no trackers are found for the user."""
    
    def __init__(self, message: str = "No trackers found") -> None:
        super().__init__(message, "TRACKER_NOT_FOUND")


class GPSDataError(TractiveError):
    """Raised when GPS data cannot be retrieved."""
    
    def __init__(self, message: str = "GPS data unavailable") -> None:
        super().__init__(message, "GPS_DATA_ERROR")
