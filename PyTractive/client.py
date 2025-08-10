"""
Enhanced Tractive API client with comprehensive functionality.

This module provides both synchronous and asynchronous clients for interacting with
Tractive GPS trackers, featuring advanced error handling, caching, and monitoring.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Callable, Union
import pandas as pd
from datetime import datetime, timedelta
import json

from .config import TractiveConfig, ConfigManager
from .http_client import HTTPClient, AsyncHTTPClient
from .models import (
    GPSLocation, DeviceStatus, PetData, ShareInfo, CommandType, CommandState,
    TractiveCredentials, TrackerInfo, LocationHistory, BatteryState,
    DeviceState, TemperatureState
)
from .exceptions import (
    TractiveError, AuthenticationError, APIError, TrackerNotFoundError,
    GPSDataError, ConfigurationError
)
from .utils import RateLimiter, format_time_ago


logger = logging.getLogger(__name__)


class TractiveClient:
    """
    Enhanced synchronous Tractive API client.
    
    Features:
    - Comprehensive GPS tracking and location services
    - Device status monitoring with alerts
    - Remote device control
    - Historical data export with analytics
    - Pet information management
    - Public sharing functionality
    - Event callbacks and monitoring
    - Response caching for performance
    - Automatic token refresh
    - Rate limiting and retry logic
    """
    
    def __init__(
        self, 
        config_path: Optional[Path] = None,
        callback_handlers: Optional[Dict[str, Callable]] = None
    ):
        """
        Initialize Tractive client.
        
        Args:
            config_path: Optional path to config file
            callback_handlers: Optional event callback handlers
            
        Raises:
            ConfigurationError: If configuration is invalid
            AuthenticationError: If authentication fails
        """
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        self.http_client = HTTPClient(self.config)
        self.callback_handlers = callback_handlers or {}
        
        # Client state
        self._access_token: Optional[str] = None
        self._user_id: Optional[str] = None
        self._tracker_id: Optional[str] = None
        self._home_coordinates: Optional[Tuple[float, float]] = None
        self._tracker_info: Optional[TrackerInfo] = None
        
        # Caching
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_device_status: Optional[DeviceStatus] = None
        self._last_gps_location: Optional[GPSLocation] = None
        
        # Statistics
        self._stats = {
            'requests_made': 0,
            'cache_hits': 0,
            'errors_encountered': 0,
            'session_start': time.time()
        }
        
        # Initialize client
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize client with authentication and tracker setup."""
        try:
            logger.info("Initializing Tractive client...")
            
            # Get credentials
            email, password, home_coords = self.config_manager.get_credentials()
            self._home_coordinates = home_coords
            
            # Authenticate
            self._authenticate(email, password)
            
            # Get tracker information
            self._tracker_id = self._get_tracker_id()
            self._tracker_info = self._get_tracker_info()
            
            # Setup monitoring if enabled
            if self.config.enable_battery_monitoring:
                self._setup_battery_monitoring()
            
            logger.info(f"Tractive client initialized successfully (Tracker: {self._tracker_id})")
            self._trigger_callback('client_initialized', {'tracker_id': self._tracker_id})
            
        except Exception as e:
            logger.error(f"Failed to initialize Tractive client: {e}")
            self._stats['errors_encountered'] += 1
            self._trigger_callback('initialization_failed', {'error': str(e)})
            raise
    
    def _authenticate(self, email: str, password: str) -> None:
        """Authenticate with Tractive API using cached token or credentials."""
        try:
            # Try cached token first
            cached_token = self.config_manager.get_access_token()
            if cached_token:
                self._access_token = cached_token
                self.http_client.set_auth_token(cached_token)
                self._user_id = self.config.default_user_id
                
                # Validate token
                try:
                    self._get_user_trackers()
                    logger.info("Using cached access token")
                    self._trigger_callback('authentication_success', {'method': 'cached_token'})
                    return
                except (AuthenticationError, APIError):
                    logger.info("Cached token invalid, authenticating with credentials")
                    self.http_client.clear_auth_token()
            
            # Authenticate with credentials
            logger.info("Authenticating with email/password")
            auth_data = {
                'platform_email': email,
                'platform_token': password,
                'grant_type': 'tractive'
            }
            
            response = self.http_client.post(f'{self.config.api_base_url}/auth/token', auth_data)
            self._stats['requests_made'] += 1
            
            self._access_token = response['access_token']
            self._user_id = response['user_id']
            
            # Set token and cache it
            self.http_client.set_auth_token(self._access_token)
            self.config_manager.save_access_token(self._access_token)
            
            logger.info("Authentication successful")
            self._trigger_callback('authentication_success', {'method': 'credentials'})
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            self._stats['errors_encountered'] += 1
            self._trigger_callback('authentication_failed', {'error': str(e)})
            raise AuthenticationError(f"Authentication failed: {e}")
    
    def _get_tracker_id(self) -> str:
        """Get the first available tracker ID for the user."""
        try:
            trackers = self._get_user_trackers()
            if not trackers:
                raise TrackerNotFoundError("No trackers found for user")
            
            tracker_id = trackers[0]['_id']
            logger.info(f"Using tracker ID: {tracker_id}")
            return tracker_id
            
        except Exception as e:
            logger.error(f"Failed to get tracker ID: {e}")
            self._stats['errors_encountered'] += 1
            raise TrackerNotFoundError(f"Failed to get tracker ID: {e}")
    
    def _get_user_trackers(self) -> List[Dict[str, Any]]:
        """Get all trackers for the current user."""
        url = f'{self.config.api_base_url}/user/{self._user_id}/trackers'
        response = self.http_client.get(url)
        self._stats['requests_made'] += 1
        return response
    
    def _get_tracker_info(self) -> TrackerInfo:
        """Get detailed tracker information."""
        try:
            url = f'{self.config.api_base_url}/tracker/{self._tracker_id}'
            tracker_data = self.http_client.get(url)
            self._stats['requests_made'] += 1
            
            return TrackerInfo(
                tracker_id=self._tracker_id,
                model_number=tracker_data.get('model_number', 'Unknown'),
                hardware_version=tracker_data.get('hw_edition', 'Unknown'),
                firmware_version=tracker_data.get('fw_version', 'Unknown')
            )
        except Exception as e:
            logger.warning(f"Could not get tracker info: {e}")
            return TrackerInfo(
                tracker_id=self._tracker_id,
                model_number='Unknown',
                hardware_version='Unknown',
                firmware_version='Unknown'
            )
    
    def _setup_battery_monitoring(self) -> None:
        """Setup automatic battery level monitoring."""
        try:
            status = self.get_device_status()
            if status.is_low_battery:
                self._trigger_callback('low_battery_alert', {
                    'battery_level': status.battery_level, 
                    'battery_state': status.battery_state.value
                })
        except Exception as e:
            logger.warning(f"Battery monitoring setup failed: {e}")
    
    def _trigger_callback(self, event: str, data: Dict[str, Any]) -> None:
        """Trigger event callback if handler exists."""
        if event in self.callback_handlers:
            try:
                self.callback_handlers[event](data)
            except Exception as e:
                logger.error(f"Callback error for event '{event}': {e}")
    
    def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if valid."""
        if not self.config.enable_response_caching:
            return None
        
        if cache_key in self._cache:
            cached_data = self._cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.config.cache_duration_seconds:
                self._stats['cache_hits'] += 1
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_data['data']
            else:
                # Remove expired cache entry
                del self._cache[cache_key]
        
        return None
    
    def _set_cached_response(self, cache_key: str, data: Dict[str, Any]) -> None:
        """Cache response data."""
        if self.config.enable_response_caching:
            self._cache[cache_key] = {
                'data': data,
                'timestamp': time.time()
            }
    
    # Properties
    @property
    def home_coordinates(self) -> Tuple[float, float]:
        """Get home coordinates."""
        if self._home_coordinates is None:
            raise ConfigurationError("Home coordinates not set")
        return self._home_coordinates
    
    @property
    def tracker_id(self) -> str:
        """Get current tracker ID."""
        if self._tracker_id is None:
            raise TrackerNotFoundError("No tracker ID available")
        return self._tracker_id
    
    @property
    def tracker_info(self) -> TrackerInfo:
        """Get tracker information."""
        if self._tracker_info is None:
            raise TrackerNotFoundError("No tracker info available")
        return self._tracker_info
    
    @property
    def is_authenticated(self) -> bool:
        """Check if client is authenticated."""
        return bool(self._access_token and self._user_id)
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        runtime = time.time() - self._stats['session_start']
        return {
            **self._stats,
            'session_runtime_seconds': runtime,
            'cache_hit_rate': self._stats['cache_hits'] / max(self._stats['requests_made'], 1)
        }
    
    # Core API Methods
    def get_device_status(self, partial: bool = False, use_cache: bool = True) -> DeviceStatus:
        """
        Get comprehensive device status information.
        
        Args:
            partial: If True, return only basic status info for faster response
            use_cache: Whether to use cached response if available
            
        Returns:
            DeviceStatus object with device information
            
        Raises:
            APIError: If API request fails
        """
        try:
            cache_key = f"device_status_{partial}"
            
            if use_cache:
                cached_result = self._get_cached_response(cache_key)
                if cached_result:
                    return DeviceStatus.from_api_data(cached_result['tracker_data'], cached_result['hw_data'])
            
            # Get hardware report
            hw_url = f'{self.config.api_base_url}/device_hw_report/{self.tracker_id}'
            hw_data = self.http_client.get(hw_url)
            self._stats['requests_made'] += 1
            
            if partial:
                # Return minimal status info
                status = DeviceStatus(
                    battery_level=hw_data.get('battery_level', 0),
                    hardware_status=hw_data.get('hw_status', 'unknown'),
                    timestamp=hw_data.get('time', 0)
                )
                self._last_device_status = status
                return status
            
            # Get full tracker data
            tracker_url = f'{self.config.api_base_url}/tracker/{self.tracker_id}'
            tracker_data = self.http_client.get(tracker_url)
            self._stats['requests_made'] += 1
            
            # Cache the response
            self._set_cached_response(cache_key, {
                'tracker_data': tracker_data,
                'hw_data': hw_data
            })
            
            status = DeviceStatus.from_api_data(tracker_data, hw_data)
            self._last_device_status = status
            
            # Check for battery alerts
            if status.is_low_battery and self.config.enable_battery_monitoring:
                self._trigger_callback('low_battery_alert', {
                    'battery_level': status.battery_level,
                    'battery_state': status.battery_state.value
                })
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get device status: {e}")
            self._stats['errors_encountered'] += 1
            raise APIError(f"Failed to get device status: {e}")
    
    def get_gps_location(self, use_cache: bool = True, max_age_minutes: int = 5) -> GPSLocation:
        """
        Get current GPS location using primary method with intelligent fallback.
        
        Args:
            use_cache: Whether to use cached location if recent enough
            max_age_minutes: Maximum age of cached location in minutes
            
        Returns:
            GPSLocation object with current location data
            
        Raises:
            GPSDataError: If GPS data cannot be retrieved
        """
        try:
            # Check cache first
            if use_cache and self._last_gps_location:
                age_minutes = (time.time() - self._last_gps_location.timestamp) / 60
                if age_minutes <= max_age_minutes:
                    logger.debug(f"Using cached GPS location ({age_minutes:.1f} minutes old)")
                    return self._last_gps_location
            
            # Try primary GPS method
            url = f'{self.config.api_base_url}/device_pos_report/{self.tracker_id}'
            gps_data = self.http_client.get(url)
            self._stats['requests_made'] += 1
            
            try:
                location = GPSLocation.from_api_data(gps_data)
                self._last_gps_location = location
                
                # Check GPS accuracy
                if location.uncertainty > self.config.gps_accuracy_threshold:
                    self._trigger_callback('poor_gps_accuracy', {
                        'uncertainty': location.uncertainty,
                        'threshold': self.config.gps_accuracy_threshold
                    })
                
                return location
                
            except (KeyError, IndexError, ValueError) as e:
                logger.warning(f"Primary GPS method failed: {e}. Trying fallback.")
                return self._get_gps_fallback()
                
        except Exception as e:
            logger.error(f"Failed to get GPS location: {e}")
            self._stats['errors_encountered'] += 1
            raise GPSDataError(f"Failed to get GPS location: {e}")
    
    def _get_gps_fallback(self) -> GPSLocation:
        """Get GPS location using historical data fallback with progressive search."""
        for hours_back in range(1, self.config.max_gps_fallback_hours + 1):
            try:
                location = self.get_historical_gps_location(hours_back)
                logger.info(f"GPS fallback successful after {hours_back} hour(s)")
                self._last_gps_location = location
                
                self._trigger_callback('gps_fallback_used', {
                    'hours_back': hours_back,
                    'location': location.to_dict()
                })
                
                return location
            except (GPSDataError, KeyError, IndexError, ValueError):
                continue
                
        raise GPSDataError("Unable to retrieve GPS data using fallback methods")
    
    def get_historical_gps_location(self, hours_back: int) -> GPSLocation:
        """
        Get historical GPS location.
        
        Args:
            hours_back: Number of hours back to search
            
        Returns:
            GPSLocation object with historical location data
            
        Raises:
            GPSDataError: If historical GPS data cannot be retrieved
        """
        try:
            now = int(time.time())
            before = now - (3600 * hours_back)
            
            gps_segments = self._get_raw_gps_data(now, before)
            
            if not gps_segments or not gps_segments[0]:
                raise GPSDataError(f"No GPS data found for {hours_back} hours back")
            
            # Get the latest entry from the first segment
            latest_entry = gps_segments[0][-1]
            return GPSLocation.from_api_data(latest_entry)
            
        except Exception as e:
            logger.error(f"Failed to get historical GPS location: {e}")
            self._stats['errors_encountered'] += 1
            raise GPSDataError(f"Failed to get historical GPS location: {e}")
    
    def get_location_history(
        self, 
        hours_back: int = 24,
        include_analytics: bool = True
    ) -> LocationHistory:
        """
        Get comprehensive location history with analytics.
        
        Args:
            hours_back: Number of hours of history to retrieve
            include_analytics: Whether to calculate distance and speed analytics
            
        Returns:
            LocationHistory object with locations and analytics
        """
        try:
            now = int(time.time())
            start_time = now - (3600 * hours_back)
            
            # Get raw GPS data
            raw_segments = self._get_raw_gps_data(now, start_time)
            all_locations = []
            
            for segment in raw_segments:
                for point in segment:
                    try:
                        location = GPSLocation.from_api_data(point)
                        all_locations.append(location)
                    except (ValueError, KeyError):
                        continue  # Skip invalid points
            
            if not all_locations:
                # Return empty location history instead of raising error
                logger.info("No location history found, returning empty history")
                # Create a simple object that mimics LocationHistory for empty case
                class EmptyLocationHistory:
                    def __init__(self):
                        self.locations = []
                        self.total_distance = 0.0
                        self.max_speed = 0.0
                        self.average_speed = 0.0
                        self.time_span_hours = 0.0
                        self.location_count = 0
                    
                    @property
                    def start_location(self):
                        return None
                    
                    @property 
                    def end_location(self):
                        return None
                
                return EmptyLocationHistory()
            
            # Sort by timestamp
            all_locations.sort(key=lambda x: x.timestamp)
            
            if not include_analytics:
                return LocationHistory(
                    locations=all_locations,
                    total_distance=0.0,
                    max_speed=0.0,
                    average_speed=0.0,
                    time_span_hours=hours_back
                )
            
            # Calculate analytics
            total_distance = 0.0
            max_speed = 0.0
            speeds = []
            
            for i in range(1, len(all_locations)):
                prev_loc = all_locations[i-1]
                curr_loc = all_locations[i]
                
                # Calculate distance between points
                distance = prev_loc.distance_to(curr_loc)
                total_distance += distance
                
                # Track speed data
                if curr_loc.speed > max_speed:
                    max_speed = curr_loc.speed
                speeds.append(curr_loc.speed)
            
            average_speed = sum(speeds) / len(speeds) if speeds else 0.0
            actual_time_span = (all_locations[-1].timestamp - all_locations[0].timestamp) / 3600
            
            return LocationHistory(
                locations=all_locations,
                total_distance=total_distance,
                max_speed=max_speed,
                average_speed=average_speed,
                time_span_hours=actual_time_span
            )
            
        except Exception as e:
            logger.error(f"Failed to get location history: {e}")
            self._stats['errors_encountered'] += 1
            raise GPSDataError(f"Failed to get location history: {e}")
    
    def _get_raw_gps_data(self, start_time: int, end_time: int) -> List[Dict[str, Any]]:
        """Get raw GPS data between two timestamps."""
        # Ensure we don't query too far back (API limit appears to be around 30 days)
        max_days_back = 30
        earliest_allowed = int(time.time()) - (max_days_back * 24 * 3600)
        
        if end_time < earliest_allowed:
            end_time = earliest_allowed
            logger.info(f"Adjusted end_time to {max_days_back} days back due to API limits")
        
        params = {
            'time_from': end_time,  # Earlier time
            'time_to': start_time,  # Later time
            'format': 'json_segments'
        }
        
        url = f'{self.config.api_base_url}/tracker/{self.tracker_id}/positions'
        response = self.http_client.get(url, params=params)
        self._stats['requests_made'] += 1
        return response
    
    def export_gps_data(
        self,
        filename: str = 'gps_data.csv',
        convert_timestamps: bool = True,
        include_analytics: bool = True
    ) -> pd.DataFrame:
        """
        Export comprehensive GPS data to CSV with analytics.
        
        Args:
            filename: Output CSV filename
            convert_timestamps: Whether to convert timestamps to datetime
            include_analytics: Whether to include calculated analytics columns
            
        Returns:
            DataFrame with GPS data and analytics
        """
        try:
            logger.info(f"Exporting GPS data to {filename}...")
            
            total_data = []
            start_time = int(time.time())
            
            # Check for existing data
            csv_path = Path(filename)
            if csv_path.is_file():
                try:
                    existing_df = pd.read_csv(csv_path)
                    if 'time' in existing_df.columns and len(existing_df) > 0:
                        if isinstance(existing_df['time'].iloc[0], str):
                            existing_df['time'] = pd.to_datetime(existing_df['time']).apply(
                                lambda dt: int(dt.timestamp())
                            )
                        end_time = int(existing_df['time'].iloc[-1])
                        logger.info(f"Found existing data, updating from {datetime.fromtimestamp(end_time)}")
                    else:
                        end_time = self._get_pet_creation_date()
                except Exception as e:
                    logger.warning(f"Could not read existing CSV: {e}")
                    existing_df = pd.DataFrame()
                    end_time = self._get_pet_creation_date()
            else:
                existing_df = pd.DataFrame()
                end_time = self._get_pet_creation_date()
            
            # Get new GPS data
            raw_segments = self._get_raw_gps_data(start_time, end_time)
            for segment in raw_segments:
                total_data.extend(segment)
            
            # Create DataFrame
            new_df = pd.DataFrame(total_data)
            combined_df = pd.concat([new_df, existing_df]).fillna(0).reset_index(drop=True)
            
            # Clean and sort data
            if 'time' in combined_df.columns:
                combined_df = (
                    combined_df
                    .sort_values(by=['time'])
                    .drop_duplicates(subset=['time'])
                    .reset_index(drop=True)
                )
                
                # Add analytics columns if requested
                if include_analytics:
                    combined_df = self._add_analytics_columns(combined_df)
            
            # Convert timestamps if requested
            if convert_timestamps and 'time' in combined_df.columns:
                combined_df['datetime'] = pd.to_datetime(combined_df['time'], unit='s')
            
            # Export to CSV
            combined_df.to_csv(filename, index=False)
            logger.info(f'GPS data exported: {len(combined_df)} records to {filename}')
            
            self._trigger_callback('data_exported', {
                'filename': filename,
                'record_count': len(combined_df)
            })
            
            return combined_df
            
        except Exception as e:
            logger.error(f"Failed to export GPS data: {e}")
            self._stats['errors_encountered'] += 1
            raise APIError(f"Failed to export GPS data: {e}")
    
    def _add_analytics_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add analytics columns to GPS data DataFrame."""
        try:
            if 'latlong' not in df.columns or len(df) < 2:
                return df
            
            # Calculate distance between consecutive points
            distances = []
            speeds_calculated = []
            
            for i in range(len(df)):
                if i == 0:
                    distances.append(0.0)
                    speeds_calculated.append(0.0)
                else:
                    prev_lat, prev_lon = df.iloc[i-1]['latlong']
                    curr_lat, curr_lon = df.iloc[i]['latlong']
                    
                    # Create temporary GPS locations for distance calculation
                    prev_loc = GPSLocation(
                        latitude=prev_lat, longitude=prev_lon,
                        timestamp=df.iloc[i-1]['time'], uncertainty=0.0
                    )
                    curr_loc = GPSLocation(
                        latitude=curr_lat, longitude=curr_lon,
                        timestamp=df.iloc[i]['time'], uncertainty=0.0
                    )
                    
                    distance = prev_loc.distance_to(curr_loc)
                    distances.append(distance)
                    
                    # Calculate speed if time difference exists
                    time_diff = df.iloc[i]['time'] - df.iloc[i-1]['time']
                    if time_diff > 0:
                        speed_ms = distance / time_diff  # m/s
                        speed_kmh = speed_ms * 3.6      # km/h
                        speeds_calculated.append(speed_kmh)
                    else:
                        speeds_calculated.append(0.0)
            
            # Add analytics columns
            df['distance_meters'] = distances
            df['calculated_speed_kmh'] = speeds_calculated
            df['cumulative_distance'] = df['distance_meters'].cumsum()
            
            return df
            
        except Exception as e:
            logger.warning(f"Failed to add analytics columns: {e}")
            return df
    
    def send_command(self, command: CommandType, state: CommandState) -> None:
        """
        Send command to tracker with comprehensive error handling.
        
        Args:
            command: Command type to send
            state: Command state (on/off)
            
        Raises:
            APIError: If command fails
        """
        try:
            logger.info(f"Sending command: {command.value} {state.value}")
            
            if command == CommandType.BATTERY_SAVER:
                # Battery saver uses different endpoint with POST
                data = {'battery_save_mode': state == CommandState.ON}
                url = f'{self.config.api_base_url}/tracker/{self.tracker_id}/battery_save_mode'
                self.http_client.post(url, data)
            else:
                # Other commands use GET request (matching old tractive.py behavior)
                url = f'{self.config.api_base_url}/tracker/{self.tracker_id}/command/{command.value}/{state.value}'
                self.http_client.get(url)
            
            self._stats['requests_made'] += 1
            logger.info(f"Command {command.value} {state.value} sent successfully")
            
            self._trigger_callback('command_sent', {
                'command': command.value,
                'state': state.value
            })
            
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            self._stats['errors_encountered'] += 1
            raise APIError(f"Failed to send command: {e}")
    
    def get_pet_data(self, use_cache: bool = True) -> PetData:
        """
        Get comprehensive pet information.
        
        Args:
            use_cache: Whether to use cached response if available
            
        Returns:
            PetData object with pet information
            
        Raises:
            APIError: If pet data cannot be retrieved
        """
        try:
            cache_key = "pet_data"
            
            if use_cache:
                cached_result = self._get_cached_response(cache_key)
                if cached_result:
                    return PetData.from_api_data(cached_result['pet_data'], cached_result['breed_data'])
            
            # Get pet ID
            trackable_url = f'{self.config.api_base_url}/user/{self._user_id}/trackable_objects'
            trackable_objects = self.http_client.get(trackable_url)
            self._stats['requests_made'] += 1
            
            if not trackable_objects:
                raise APIError("No trackable objects found")
            
            pet_id = trackable_objects[0]['_id']
            
            # Get pet data
            pet_url = f'{self.config.api_base_url}/trackable_object/{pet_id}'
            pet_data = self.http_client.get(pet_url)
            self._stats['requests_made'] += 1
            
            # Get breed information via public share (temporary)
            breed_data = self._get_breed_data_via_share()
            
            # Cache the response
            self._set_cached_response(cache_key, {
                'pet_data': pet_data,
                'breed_data': breed_data
            })
            
            return PetData.from_api_data(pet_data, breed_data)
            
        except Exception as e:
            logger.error(f"Failed to get pet data: {e}")
            self._stats['errors_encountered'] += 1
            raise APIError(f"Failed to get pet data: {e}")
    
    def _get_pet_creation_date(self) -> int:
        """Get pet creation date for data export."""
        try:
            pet_data = self.get_pet_data()
            return pet_data.created_at
        except Exception:
            # Fallback to current time minus 1 year
            return int(time.time()) - (365 * 24 * 3600)
    
    def _get_breed_data_via_share(self) -> Dict[str, Any]:
        """Get breed data via temporary public share."""
        try:
            # Check if public share exists
            share_id = self._get_existing_share_id()
            created_temp_share = False
            
            if not share_id:
                # Create temporary share
                share_id = self._create_share('pet_data')
                created_temp_share = True
            
            # Get public share info and extract breed data
            share_link, _, _ = self._get_share_info(share_id)
            link_id = share_link.split('/')[-1]
            
            breed_url = f'{self.config.api_base_url}/public_share/{link_id}/info'
            breed_data = self.http_client.get(breed_url)
            self._stats['requests_made'] += 1
            
            # Clean up temporary share
            if created_temp_share:
                self._deactivate_share(share_id)
            
            return breed_data
            
        except Exception as e:
            logger.warning(f"Could not get breed data: {e}")
            return {'breed_names': ['Unknown']}
    
    def _get_existing_share_id(self) -> Optional[str]:
        """Check if public share exists and return ID."""
        try:
            url = f'{self.config.api_base_url}/tracker/{self.tracker_id}/public_shares'
            shares = self.http_client.get(url)
            self._stats['requests_made'] += 1
            return shares[0]['_id'] if shares else None
        except Exception:
            return None
    
    def _create_share(self, message: str) -> str:
        """Create public share and return ID."""
        data = {'tracker_id': self.tracker_id, 'message': message}
        url = f'{self.config.api_base_url}/public_share'
        response = self.http_client.post(url, data)
        self._stats['requests_made'] += 1
        return response['_id']
    
    def _get_share_info(self, share_id: str) -> Tuple[str, str, int]:
        """Get public share information."""
        url = f'{self.config.api_base_url}/public_share/{share_id}'
        response = self.http_client.get(url)
        self._stats['requests_made'] += 1
        return (
            response['share_link'],
            response['message'],
            response['created_at']
        )
    
    def _deactivate_share(self, share_id: str) -> None:
        """Deactivate public share."""
        url = f'{self.config.api_base_url}/public_share/{share_id}/deactivate'
        self.http_client.put(url)
        self._stats['requests_made'] += 1
    
    def create_public_share(self, message: str = "Pet location sharing") -> ShareInfo:
        """
        Create a public share link for the tracker.
        
        Args:
            message: Message to display with the share
            
        Returns:
            ShareInfo with share details
        """
        try:
            share_id = self._create_share(message)
            share_link, share_message, created_at = self._get_share_info(share_id)
            
            share_info = ShareInfo(
                share_id=share_id,
                share_link=share_link,
                message=share_message,
                created_at=created_at
            )
            
            self._trigger_callback('share_created', share_info.to_dict())
            return share_info
            
        except Exception as e:
            logger.error(f"Failed to create public share: {e}")
            self._stats['errors_encountered'] += 1
            raise APIError(f"Failed to create public share: {e}")
    
    def get_distance_from_home(self, location: Optional[GPSLocation] = None) -> float:
        """
        Calculate distance from home coordinates.
        
        Args:
            location: GPS location to calculate from (uses current if None)
            
        Returns:
            Distance in meters
        """
        if location is None:
            location = self.get_gps_location()
        
        home_location = GPSLocation(
            latitude=self.home_coordinates[0],
            longitude=self.home_coordinates[1],
            timestamp=int(time.time()),
            uncertainty=0.0
        )
        
        return location.distance_to(home_location)
    
    def is_pet_at_home(self, threshold_meters: int = 50) -> bool:
        """
        Check if pet is currently at home within threshold.
        
        Args:
            threshold_meters: Distance threshold in meters
            
        Returns:
            True if pet is within threshold of home
        """
        try:
            distance = self.get_distance_from_home()
            is_home = distance <= threshold_meters
            
            if is_home:
                self._trigger_callback('pet_at_home', {
                    'distance_meters': distance,
                    'threshold_meters': threshold_meters
                })
            
            return is_home
            
        except Exception as e:
            logger.error(f"Failed to check home status: {e}")
            return False
    
    def monitor_location(
        self, 
        callback: Callable[[GPSLocation], None],
        interval_seconds: int = 60,
        max_iterations: Optional[int] = None
    ) -> None:
        """
        Monitor GPS location with periodic updates.
        
        Args:
            callback: Function to call with each location update
            interval_seconds: Time between location checks
            max_iterations: Maximum number of iterations (None for infinite)
        """
        iteration = 0
        
        try:
            logger.info(f"Starting location monitoring (interval: {interval_seconds}s)")
            
            while max_iterations is None or iteration < max_iterations:
                try:
                    location = self.get_gps_location()
                    callback(location)
                    
                    if interval_seconds > 0:
                        time.sleep(interval_seconds)
                    
                    iteration += 1
                    
                except KeyboardInterrupt:
                    logger.info("Location monitoring stopped by user")
                    break
                except Exception as e:
                    logger.error(f"Location monitoring error: {e}")
                    time.sleep(interval_seconds)  # Wait before retrying
                    
        except Exception as e:
            logger.error(f"Location monitoring failed: {e}")
            raise
    
    def refresh_authentication(self) -> None:
        """Force refresh of authentication token."""
        try:
            logger.info("Refreshing authentication...")
            
            # Clear current token
            self.http_client.clear_auth_token()
            self._access_token = None
            
            # Get credentials and re-authenticate
            email, password, _ = self.config_manager.get_credentials()
            self._authenticate(email, password)
            
            logger.info("Authentication refreshed successfully")
            
        except Exception as e:
            logger.error(f"Failed to refresh authentication: {e}")
            raise AuthenticationError(f"Failed to refresh authentication: {e}")
    
    def clear_cache(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()
        logger.info("Response cache cleared")
    
    def close(self) -> None:
        """Close the client and cleanup resources."""
        try:
            # Log final statistics
            stats = self.stats
            logger.info(f"Closing Tractive client - Session stats: {stats}")
            
            # Trigger cleanup callback
            self._trigger_callback('client_closing', stats)
            
            # Close HTTP client
            self.http_client.close()
            
            # Clear cache
            self.clear_cache()
            
        except Exception as e:
            logger.error(f"Error during client cleanup: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AsyncTractiveClient:
    """
    Asynchronous Tractive API client with high-performance capabilities.
    
    This client provides the same functionality as TractiveClient but with
    async/await support for non-blocking operations and improved performance
    in concurrent scenarios.
    """
    
    def __init__(
        self, 
        config_path: Optional[Path] = None,
        callback_handlers: Optional[Dict[str, Callable]] = None
    ):
        """Initialize async Tractive client."""
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        self.http_client = AsyncHTTPClient(self.config)
        self.callback_handlers = callback_handlers or {}
        
        # Client state (same as sync client)
        self._access_token: Optional[str] = None
        self._user_id: Optional[str] = None
        self._tracker_id: Optional[str] = None
        self._home_coordinates: Optional[Tuple[float, float]] = None
        
        # Statistics
        self._stats = {
            'requests_made': 0,
            'cache_hits': 0,
            'errors_encountered': 0,
            'session_start': time.time()
        }
    
    async def initialize(self) -> None:
        """Async initialization method."""
        try:
            logger.info("Initializing async Tractive client...")
            
            # Get credentials
            email, password, home_coords = self.config_manager.get_credentials()
            self._home_coordinates = home_coords
            
            # Authenticate
            await self._authenticate(email, password)
            
            # Get tracker information
            self._tracker_id = await self._get_tracker_id()
            
            logger.info(f"Async Tractive client initialized (Tracker: {self._tracker_id})")
            
        except Exception as e:
            logger.error(f"Failed to initialize async Tractive client: {e}")
            self._stats['errors_encountered'] += 1
            raise
    
    async def _authenticate(self, email: str, password: str) -> None:
        """Async authentication method."""
        try:
            # Try cached token first
            cached_token = self.config_manager.get_access_token()
            if cached_token:
                self._access_token = cached_token
                self.http_client.set_auth_token(cached_token)
                self._user_id = self.config.default_user_id
                
                # Validate token
                try:
                    await self._get_user_trackers()
                    logger.info("Using cached access token (async)")
                    return
                except (AuthenticationError, APIError):
                    logger.info("Cached token invalid, authenticating with credentials (async)")
            
            # Authenticate with credentials
            auth_data = {
                'platform_email': email,
                'platform_token': password,
                'grant_type': 'tractive'
            }
            
            response = await self.http_client.post(f'{self.config.api_base_url}/auth/token', auth_data)
            self._stats['requests_made'] += 1
            
            self._access_token = response['access_token']
            self._user_id = response['user_id']
            
            # Set token and cache it
            self.http_client.set_auth_token(self._access_token)
            self.config_manager.save_access_token(self._access_token)
            
            logger.info("Async authentication successful")
            
        except Exception as e:
            logger.error(f"Async authentication failed: {e}")
            self._stats['errors_encountered'] += 1
            raise AuthenticationError(f"Async authentication failed: {e}")
    
    async def _get_tracker_id(self) -> str:
        """Get tracker ID asynchronously."""
        try:
            trackers = await self._get_user_trackers()
            if not trackers:
                raise TrackerNotFoundError("No trackers found for user")
            
            tracker_id = trackers[0]['_id']
            logger.info(f"Using tracker ID (async): {tracker_id}")
            return tracker_id
            
        except Exception as e:
            logger.error(f"Failed to get tracker ID (async): {e}")
            self._stats['errors_encountered'] += 1
            raise TrackerNotFoundError(f"Failed to get tracker ID: {e}")
    
    async def _get_user_trackers(self) -> List[Dict[str, Any]]:
        """Get user trackers asynchronously."""
        url = f'{self.config.api_base_url}/user/{self._user_id}/trackers'
        response = await self.http_client.get(url)
        self._stats['requests_made'] += 1
        return response
    
    async def get_gps_location(self) -> GPSLocation:
        """Get GPS location asynchronously."""
        try:
            url = f'{self.config.api_base_url}/device_pos_report/{self._tracker_id}'
            gps_data = await self.http_client.get(url)
            self._stats['requests_made'] += 1
            
            return GPSLocation.from_api_data(gps_data)
            
        except Exception as e:
            logger.error(f"Failed to get GPS location (async): {e}")
            self._stats['errors_encountered'] += 1
            raise GPSDataError(f"Failed to get GPS location: {e}")
    
    @property
    def tracker_id(self) -> str:
        """Get current tracker ID."""
        if self._tracker_id is None:
            raise TrackerNotFoundError("No tracker ID available")
        return self._tracker_id
    
    async def close(self) -> None:
        """Close the async client."""
        try:
            stats = {
                **self._stats,
                'session_runtime_seconds': time.time() - self._stats['session_start']
            }
            logger.info(f"Closing async Tractive client - Session stats: {stats}")
            
            await self.http_client.close()
            
        except Exception as e:
            logger.error(f"Error during async client cleanup: {e}")
    
    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
