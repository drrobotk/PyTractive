"""
Utility functions for PyTractive.
"""

import logging
import time
from typing import Optional


def format_time_ago(timestamp: int) -> str:
    """
    Format timestamp as human-readable time ago string.
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        Human-readable time difference string
    """
    now = int(time.time())
    diff = now - timestamp
    
    if diff < 60:
        return f"{diff} seconds ago"
    elif diff < 3600:
        minutes = diff // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif diff < 86400:
        hours = diff // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = diff // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"


def setup_logging(level: int = logging.INFO) -> None:
    """
    Setup logging configuration.
    
    Args:
        level: Logging level
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def validate_coordinates(lat: float, lon: float) -> bool:
    """
    Validate latitude and longitude coordinates.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        True if coordinates are valid
    """
    return -90 <= lat <= 90 and -180 <= lon <= 180


def calculate_battery_health(battery_level: int, time_since_charge: int) -> str:
    """
    Calculate battery health status.
    
    Args:
        battery_level: Current battery level (0-100)
        time_since_charge: Time since last charge in seconds
        
    Returns:
        Battery health status string
    """
    if battery_level >= 80:
        return "Excellent"
    elif battery_level >= 60:
        return "Good"
    elif battery_level >= 40:
        return "Fair"
    elif battery_level >= 20:
        return "Low"
    else:
        return "Critical"


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.calls = []
    
    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = time.time()
        
        # Remove calls older than 1 minute
        self.calls = [call_time for call_time in self.calls if now - call_time < 60]
        
        # Check if we need to wait
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # Record this call
        self.calls.append(now)
