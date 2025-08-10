"""
Simple Tractive client using only requests library.

This is a lightweight alternative to client.py that uses the SimpleHTTPClient
for easier debugging and customization.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

from .http_client_simple import SimpleHTTPClient, RequestsResponseLogger
from .exceptions import TractiveError, AuthenticationError, APIError
from .models import GPSLocation, DeviceStatus, PetData, TrackerInfo
from .config import load_credentials
from .utils import format_time_ago


logger = logging.getLogger(__name__)


class SimpleTractiveClient:
    """
    Simple Tractive client using only requests library.
    
    Features:
    - Easy to understand and modify
    - Direct requests usage
    - Basic caching
    - Simple error handling
    - Detailed request/response logging
    """
    
    API_BASE = "https://graph.tractive.com/3"
    
    def __init__(self, config_path: Optional[Path] = None, enable_logging: bool = False):
        """
        Initialize simple Tractive client.
        
        Args:
            config_path: Path to configuration file (optional)
            enable_logging: Enable detailed request/response logging
        """
        # Load configuration
        self.credentials = load_credentials(config_path)
        
        # Initialize HTTP client
        self.http_client = SimpleHTTPClient(timeout=30, retries=3)
        
        # Enable detailed logging if requested
        if enable_logging:
            self.logger = RequestsResponseLogger(self.http_client, log_bodies=True)
        
        # Authentication and caching
        self._access_token: Optional[str] = None
        self._user_id: Optional[str] = None
        self._tracker_id: Optional[str] = None
        
        # Simple cache with timestamps
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timeout = 60  # 1 minute cache
        
        # Stats
        self.start_time = time.time()
        
        # Initialize client
        self._authenticate()
        self._load_user_info()
    
    def _authenticate(self) -> None:
        """Authenticate with Tractive API."""
        logger.info("Authenticating with Tractive API...")
        
        auth_data = {
            "platform_email": self.credentials.email,
            "platform_token": self.credentials.password,
            "grant_type": "tractive"
        }
        
        try:
            response = self.http_client.post(
                f"{self.API_BASE}/auth/token",
                data=auth_data
            )
            
            self._access_token = response["access_token"]
            self._user_id = response["user_id"]
            
            # Set auth token for future requests
            self.http_client.set_auth_token(self._access_token)
            
            logger.info(f"Successfully authenticated user: {self._user_id}")
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate: {e}")
    
    def _load_user_info(self) -> None:
        """Load user information and find tracker."""
        logger.info("Loading user information...")
        
        try:
            # Get user data
            user_data = self.http_client.get(f"{self.API_BASE}/user/{self._user_id}")
            
            # Get trackables (pets with trackers)
            trackables = self.http_client.get(f"{self.API_BASE}/user/{self._user_id}/trackables")
            
            if not trackables:
                raise TractiveError("No trackable devices found for this user")
            
            # Use the first trackable device
            trackable = trackables[0]
            self._tracker_id = trackable["device_id"]
            
            logger.info(f"Found tracker: {self._tracker_id} for pet: {trackable.get('details', {}).get('name', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to load user info: {e}")
            raise TractiveError(f"Failed to load user info: {e}")
    
    def _get_cached_or_fetch(self, cache_key: str, fetch_func) -> Any:
        """Get data from cache or fetch from API."""
        now = time.time()
        
        # Check if we have valid cached data
        if cache_key in self._cache:
            cache_entry = self._cache[cache_key]
            if now - cache_entry["timestamp"] < self._cache_timeout:
                logger.debug(f"Using cached data for {cache_key}")
                return cache_entry["data"]
        
        # Fetch fresh data
        logger.debug(f"Fetching fresh data for {cache_key}")
        data = fetch_func()
        
        # Cache the result
        self._cache[cache_key] = {
            "data": data,
            "timestamp": now
        }
        
        return data
    
    def get_device_status(self) -> DeviceStatus:
        """Get current device status."""
        def fetch():
            response = self.http_client.get(
                f"{self.API_BASE}/device_hw_report/{self._tracker_id}"
            )
            return DeviceStatus.from_dict(response)
        
        return self._get_cached_or_fetch("device_status", fetch)
    
    def get_gps_location(self) -> GPSLocation:
        """Get current GPS location."""
        def fetch():
            response = self.http_client.get(
                f"{self.API_BASE}/device_pos_report/{self._tracker_id}"
            )
            return GPSLocation.from_dict(response)
        
        return self._get_cached_or_fetch("gps_location", fetch)
    
    def get_pet_data(self) -> PetData:
        """Get pet information."""
        def fetch():
            # Get trackables to find pet info
            trackables = self.http_client.get(f"{self.API_BASE}/user/{self._user_id}/trackables")
            
            for trackable in trackables:
                if trackable["device_id"] == self._tracker_id:
                    return PetData.from_dict(trackable)
            
            raise TractiveError("Pet data not found")
        
        return self._get_cached_or_fetch("pet_data", fetch)
    
    def get_tracker_info(self) -> TrackerInfo:
        """Get tracker hardware information."""
        def fetch():
            response = self.http_client.get(
                f"{self.API_BASE}/tracker/{self._tracker_id}"
            )
            return TrackerInfo.from_dict(response)
        
        return self._get_cached_or_fetch("tracker_info", fetch)
    
    def send_command(self, command: str, state: str) -> None:
        """
        Send command to tracker.
        
        Args:
            command: Command type (battery_saver, live_tracking, led_control, buzzer_control)
            state: Command state (on, off)
        """
        logger.info(f"Sending command: {command} {state}")
        
        # Map command types to API endpoints
        command_map = {
            "battery_saver": "power_saving_mode",
            "live_tracking": "live_tracking", 
            "led_control": "led",
            "buzzer_control": "buzzer"
        }
        
        if command not in command_map:
            raise ValueError(f"Unknown command: {command}")
        
        api_command = command_map[command]
        active = state.lower() == "on"
        
        # Send command
        command_data = {
            "active": active
        }
        
        try:
            self.http_client.post(
                f"{self.API_BASE}/device_command/{self._tracker_id}/{api_command}",
                data=command_data
            )
            logger.info(f"Command sent successfully: {command} {state}")
            
            # Clear cache to get fresh data
            self._cache.clear()
            
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            raise TractiveError(f"Failed to send command: {e}")
    
    def get_location_history(
        self, 
        hours: int = 24, 
        include_analytics: bool = True
    ) -> Dict[str, Any]:
        """
        Get location history with analytics.
        
        Args:
            hours: Number of hours of history to retrieve
            include_analytics: Whether to include analytics calculations
            
        Returns:
            Dictionary with location history and analytics
        """
        logger.info(f"Getting {hours} hours of location history")
        
        # Calculate time range
        end_time = int(time.time())
        start_time = end_time - (hours * 3600)
        
        try:
            # Get position reports for time range
            response = self.http_client.get(
                f"{self.API_BASE}/tracker/{self._tracker_id}/positions",
                params={
                    "time_from": start_time,
                    "time_to": end_time,
                    "format": "json_segments"
                }
            )
            
            locations = []
            for segment in response:
                for point in segment:
                    locations.append(GPSLocation.from_dict(point))
            
            result = {
                "location_count": len(locations),
                "locations": locations
            }
            
            if include_analytics and locations:
                # Calculate basic analytics
                result.update(self._calculate_analytics(locations))
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get location history: {e}")
            raise TractiveError(f"Failed to get location history: {e}")
    
    def _calculate_analytics(self, locations: List[GPSLocation]) -> Dict[str, Any]:
        """Calculate analytics for location history."""
        if not locations:
            return {}
        
        # Sort by timestamp
        sorted_locations = sorted(locations, key=lambda x: x.timestamp)
        
        total_distance = 0.0
        speeds = []
        
        for i in range(1, len(sorted_locations)):
            prev_loc = sorted_locations[i-1]
            curr_loc = sorted_locations[i]
            
            # Simple distance calculation (approximation)
            lat_diff = abs(curr_loc.coordinates[0] - prev_loc.coordinates[0])
            lon_diff = abs(curr_loc.coordinates[1] - prev_loc.coordinates[1])
            distance = ((lat_diff ** 2 + lon_diff ** 2) ** 0.5) * 111000  # Rough meters
            
            total_distance += distance
            
            # Calculate speed if we have time difference
            time_diff = curr_loc.timestamp - prev_loc.timestamp
            if time_diff > 0:
                speed_ms = distance / time_diff
                speed_kmh = speed_ms * 3.6
                speeds.append(speed_kmh)
        
        time_span_hours = (sorted_locations[-1].timestamp - sorted_locations[0].timestamp) / 3600
        
        return {
            "total_distance": total_distance,
            "max_speed": max(speeds) if speeds else 0.0,
            "average_speed": sum(speeds) / len(speeds) if speeds else 0.0,
            "time_span_hours": time_span_hours,
            "start_location": sorted_locations[0],
            "end_location": sorted_locations[-1]
        }
    
    def get_distance_from_home(self, location: GPSLocation) -> float:
        """Calculate distance from home coordinates."""
        if not self.credentials.home_coordinates:
            logger.warning("Home coordinates not configured")
            return 0.0
        
        home_lat, home_lon = self.credentials.home_coordinates
        pet_lat, pet_lon = location.coordinates
        
        # Simple distance calculation (approximation)
        lat_diff = abs(pet_lat - home_lat)
        lon_diff = abs(pet_lon - home_lon)
        distance_degrees = (lat_diff ** 2 + lon_diff ** 2) ** 0.5
        distance_meters = distance_degrees * 111000  # Rough conversion to meters
        
        return distance_meters
    
    def is_pet_at_home(self, threshold: float = 50.0) -> bool:
        """Check if pet is at home within threshold distance."""
        location = self.get_gps_location()
        distance = self.get_distance_from_home(location)
        return distance <= threshold
    
    @property
    def tracker_id(self) -> str:
        """Get tracker ID."""
        return self._tracker_id
    
    @property 
    def user_id(self) -> str:
        """Get user ID."""
        return self._user_id
    
    @property
    def home_coordinates(self) -> Optional[tuple]:
        """Get home coordinates."""
        return self.credentials.home_coordinates
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        runtime = time.time() - self.start_time
        http_stats = self.http_client.stats
        
        return {
            "session_runtime_seconds": runtime,
            "requests_made": http_stats["requests_made"],
            "cache_entries": len(self._cache),
            "cache_hit_rate": 0.0,  # Simple client doesn't track hits
            "errors_encountered": 0  # Simple client doesn't track errors separately
        }
    
    def close(self) -> None:
        """Close the client and HTTP session."""
        logger.info("Closing simple Tractive client")
        self.http_client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Example usage
if __name__ == "__main__":
    import logging
    
    # Enable detailed logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Create simple client with request logging
    with SimpleTractiveClient(enable_logging=True) as client:
        print(f"Connected to tracker: {client.tracker_id}")
        
        # Get device status
        status = client.get_device_status()
        print(f"Battery: {status.battery_level}%")
        
        # Get GPS location
        location = client.get_gps_location()
        print(f"Location: {location.coordinates}")
        
        # Check if at home
        at_home = client.is_pet_at_home()
        print(f"At home: {at_home}")
        
        # Get statistics
        stats = client.stats
        print(f"Stats: {stats}")
