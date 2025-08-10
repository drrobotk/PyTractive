"""
Data models for PyTractive using dataclasses for better type safety and structure.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Any, Dict, Union
from enum import Enum
import json


class DeviceState(Enum):
    """Device state enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    OPERATIONAL = "OPERATIONAL"  # Keep uppercase to match API response
    UNKNOWN = "unknown"
    
    @classmethod
    def from_string(cls, value: str) -> "DeviceState":
        """Create DeviceState from string with fallback to UNKNOWN."""
        try:
            if value is None:
                return cls.UNKNOWN
            # Try exact match first (for OPERATIONAL), then lowercase
            try:
                return cls(value)
            except ValueError:
                return cls(value.lower())
        except (ValueError, AttributeError):
            return cls.UNKNOWN


class CommandType(Enum):
    """Available device commands."""
    BATTERY_SAVER = "battery_saver"
    LIVE_TRACKING = "live_tracking"
    LED_CONTROL = "led_control"
    BUZZER_CONTROL = "buzzer_control"
    
    @classmethod
    def from_string(cls, value: str) -> "CommandType":
        """Create CommandType from string."""
        return cls(value.lower())


class CommandState(Enum):
    """Command states."""
    ON = "on"
    OFF = "off"
    
    @classmethod
    def from_string(cls, value: str) -> "CommandState":
        """Create CommandState from string."""
        return cls(value.lower())
    
    @classmethod
    def from_bool(cls, value: bool) -> "CommandState":
        """Create CommandState from boolean."""
        return cls.ON if value else cls.OFF
    
    def to_bool(self) -> bool:
        """Convert CommandState to boolean."""
        return self == self.ON


class TemperatureState(Enum):
    """Temperature state enumeration."""
    NORMAL = "normal"
    HOT = "hot"
    COLD = "cold"
    UNKNOWN = "unknown"
    
    @classmethod
    def from_string(cls, value: str) -> "TemperatureState":
        """Create TemperatureState from string with fallback to UNKNOWN."""
        try:
            if value is None:
                return cls.UNKNOWN
            return cls(value.lower())
        except (ValueError, AttributeError):
            return cls.UNKNOWN


class BatteryState(Enum):
    """Battery state enumeration."""
    EXCELLENT = "excellent"  # 80-100%
    GOOD = "good"           # 60-79%
    FAIR = "fair"           # 40-59%
    LOW = "low"             # 20-39%
    CRITICAL = "critical"   # 0-19%
    
    @classmethod
    def from_level(cls, level: int) -> "BatteryState":
        """Create BatteryState from battery level."""
        if level >= 80:
            return cls.EXCELLENT
        elif level >= 60:
            return cls.GOOD
        elif level >= 40:
            return cls.FAIR
        elif level >= 20:
            return cls.LOW
        else:
            return cls.CRITICAL


@dataclass(frozen=True)
class GPSLocation:
    """GPS location data with comprehensive geospatial information."""
    latitude: float
    longitude: float
    timestamp: int
    uncertainty: float
    altitude: float = 0.0
    speed: float = 0.0
    course: float = 0.0
    
    def __post_init__(self):
        """Validate GPS coordinates."""
        if not (-90 <= self.latitude <= 90):
            raise ValueError(f"Invalid latitude: {self.latitude}")
        if not (-180 <= self.longitude <= 180):
            raise ValueError(f"Invalid longitude: {self.longitude}")
        if self.uncertainty < 0:
            raise ValueError(f"Invalid uncertainty: {self.uncertainty}")
    
    @property
    def coordinates(self) -> Tuple[float, float]:
        """Return coordinates as (lat, lon) tuple."""
        return (self.latitude, self.longitude)
    
    @property
    def datetime(self) -> datetime:
        """Return timestamp as datetime object in local timezone."""
        return datetime.fromtimestamp(self.timestamp)
    
    @property
    def datetime_utc(self) -> datetime:
        """Return timestamp as UTC datetime object."""
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc)
    
    @property
    def is_moving(self) -> bool:
        """Check if the device is moving (speed > 1 km/h)."""
        return self.speed > 1.0
    
    @property
    def accuracy_level(self) -> str:
        """Return human-readable accuracy level."""
        if self.uncertainty <= 5:
            return "Excellent"
        elif self.uncertainty <= 15:
            return "Good"
        elif self.uncertainty <= 50:
            return "Fair"
        else:
            return "Poor"
    
    def distance_to(self, other: "GPSLocation") -> float:
        """
        Calculate distance to another GPS location in meters.
        Uses Haversine formula for accurate distance calculation.
        """
        import math
        
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in meters
        return 6371000 * c
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'timestamp': self.timestamp,
            'uncertainty': self.uncertainty,
            'altitude': self.altitude,
            'speed': self.speed,
            'course': self.course
        }
    
    @classmethod
    def from_api_data(cls, data: Dict[str, Any]) -> "GPSLocation":
        """Create GPSLocation from API response data with validation."""
        latlong = data.get("latlong", [0.0, 0.0])
        
        if not latlong or len(latlong) < 2:
            raise ValueError("Invalid GPS data: missing or invalid coordinates")
        
        return cls(
            latitude=float(latlong[0]),
            longitude=float(latlong[1]),
            timestamp=int(data.get("time", 0)),
            uncertainty=float(data.get("pos_uncertainty", 0.0)),
            altitude=float(data.get("altitude", data.get("alt", 0.0))),
            speed=float(data.get("speed", 0.0)),
            course=float(data.get("course", 0.0))
        )


@dataclass(frozen=True)
class DeviceStatus:
    """Comprehensive device status information with enhanced monitoring capabilities."""
    battery_level: int
    hardware_status: str
    timestamp: int
    temperature_state: TemperatureState = TemperatureState.UNKNOWN
    state: DeviceState = DeviceState.UNKNOWN
    battery_save_mode: bool = False
    
    def __post_init__(self):
        """Validate device status data."""
        if not (0 <= self.battery_level <= 100):
            raise ValueError(f"Invalid battery level: {self.battery_level}")
        if self.timestamp < 0:
            raise ValueError(f"Invalid timestamp: {self.timestamp}")
    
    @property
    def datetime(self) -> datetime:
        """Return timestamp as datetime object in local timezone."""
        return datetime.fromtimestamp(self.timestamp)
    
    @property
    def datetime_utc(self) -> datetime:
        """Return timestamp as UTC datetime object."""
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc)
    
    @property
    def is_low_battery(self) -> bool:
        """Check if battery is low (below 20%)."""
        return self.battery_level < 20
    
    @property
    def is_critical_battery(self) -> bool:
        """Check if battery is critically low (below 10%)."""
        return self.battery_level < 10
    
    @property
    def battery_state(self) -> BatteryState:
        """Get battery health state."""
        return BatteryState.from_level(self.battery_level)
    
    @property
    def is_online(self) -> bool:
        """Check if device is currently online/active."""
        return self.state == DeviceState.OPERATIONAL
    
    @property
    def time_since_last_update(self) -> int:
        """Time in seconds since last status update."""
        import time
        return int(time.time()) - self.timestamp
    
    @property
    def needs_attention(self) -> bool:
        """Check if device status requires user attention."""
        return (
            self.is_low_battery or 
            self.temperature_state in [TemperatureState.HOT, TemperatureState.COLD] or
            self.state != DeviceState.ACTIVE or
            (self.hardware_status and self.hardware_status.lower() in ['error', 'fault', 'warning'])
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'battery_level': self.battery_level,
            'battery_state': self.battery_state.value,
            'hardware_status': self.hardware_status,
            'timestamp': self.timestamp,
            'temperature_state': self.temperature_state.value,
            'state': self.state.value,
            'battery_save_mode': self.battery_save_mode,
            'is_online': self.is_online,
            'needs_attention': self.needs_attention
        }
    
    @classmethod
    def from_api_data(cls, tracker_data: Dict[str, Any], hw_data: Dict[str, Any]) -> "DeviceStatus":
        """Create DeviceStatus from API response data with enhanced validation."""
        battery_level = int(hw_data.get("battery_level", 0))
        temp_state_str = hw_data.get("temperature_state", "unknown")
        device_state_str = tracker_data.get("state", "unknown")
        
        return cls(
            battery_level=battery_level,
            hardware_status=hw_data.get("hw_status", "unknown"),
            timestamp=int(hw_data.get("time", 0)),
            temperature_state=TemperatureState.from_string(temp_state_str),
            state=DeviceState.from_string(device_state_str),
            battery_save_mode=bool(tracker_data.get("battery_save_mode", False))
        )


@dataclass(frozen=True)
class PetData:
    """Enhanced pet information data with comprehensive details and validation."""
    name: str
    pet_type: str
    gender: str
    neutered: bool
    created_at: int
    updated_at: int
    chip_id: str
    birthday: int
    profile_picture_id: str
    breed: str
    weight: Optional[float] = None
    
    def __post_init__(self):
        """Validate pet data."""
        if not self.name.strip():
            raise ValueError("Pet name cannot be empty")
        if self.created_at < 0:
            raise ValueError(f"Invalid creation timestamp: {self.created_at}")
        if self.birthday < 0:
            raise ValueError(f"Invalid birthday timestamp: {self.birthday}")
        if self.weight is not None and self.weight <= 0:
            raise ValueError(f"Invalid weight: {self.weight}")
    
    @property
    def created_datetime(self) -> datetime:
        """Return creation timestamp as datetime object."""
        return datetime.fromtimestamp(self.created_at)
    
    @property
    def updated_datetime(self) -> datetime:
        """Return update timestamp as datetime object."""
        return datetime.fromtimestamp(self.updated_at)
    
    @property
    def birthday_datetime(self) -> datetime:
        """Return birthday timestamp as datetime object."""
        return datetime.fromtimestamp(self.birthday)
    
    @property
    def age_years(self) -> float:
        """Calculate pet's age in years."""
        import time
        current_time = time.time()
        age_seconds = current_time - self.birthday
        return age_seconds / (365.25 * 24 * 3600)  # Account for leap years
    
    @property
    def age_description(self) -> str:
        """Return human-readable age description."""
        age = self.age_years
        if age < 1:
            months = int(age * 12)
            return f"{months} month{'s' if months != 1 else ''} old"
        else:
            years = int(age)
            return f"{years} year{'s' if years != 1 else ''} old"
    
    @property
    def profile_picture_url(self) -> str:
        """Return URL for profile picture."""
        if not self.profile_picture_id:
            return ""
        return f"https://graph.tractive.com/3/media/resource/{self.profile_picture_id}.96_96_1.jpg"
    
    @property
    def profile_picture_url_large(self) -> str:
        """Return URL for large profile picture."""
        if not self.profile_picture_id:
            return ""
        return f"https://graph.tractive.com/3/media/resource/{self.profile_picture_id}.256_256_1.jpg"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'pet_type': self.pet_type,
            'gender': self.gender,
            'neutered': self.neutered,
            'breed': self.breed,
            'age_years': self.age_years,
            'age_description': self.age_description,
            'chip_id': self.chip_id,
            'weight': self.weight,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'birthday': self.birthday,
            'profile_picture_url': self.profile_picture_url
        }
    
    @classmethod
    def from_api_data(cls, pet_data: Dict[str, Any], breed_data: Dict[str, Any]) -> "PetData":
        """Create PetData from API response data with enhanced validation."""
        details = pet_data.get("details", {})
        
        return cls(
            name=details.get("name", "").strip(),
            pet_type=details.get("pet_type", "").strip(),
            gender=details.get("gender", "").strip(),
            neutered=bool(details.get("neutered", False)),
            created_at=int(pet_data.get("created_at", 0)),
            updated_at=int(pet_data.get("updated_at", pet_data.get("created_at", 0))),
            chip_id=details.get("chip_id", "").strip(),
            birthday=int(details.get("birthday", 0)),
            profile_picture_id=details.get("profile_picture_id", "").strip(),
            breed=breed_data.get("breed_names", ["Unknown"])[0] if breed_data.get("breed_names") else "Unknown",
            weight=float(details["weight"]) if details.get("weight") else None
        )


@dataclass(frozen=True)
class ShareInfo:
    """Public share information with enhanced functionality."""
    share_id: str
    share_link: str
    message: str
    created_at: int
    active: bool = True
    
    def __post_init__(self):
        """Validate share info."""
        if not self.share_id.strip():
            raise ValueError("Share ID cannot be empty")
        if not self.share_link.strip():
            raise ValueError("Share link cannot be empty")
        if self.created_at < 0:
            raise ValueError(f"Invalid creation timestamp: {self.created_at}")
    
    @property
    def created_datetime(self) -> datetime:
        """Return creation timestamp as datetime object."""
        return datetime.fromtimestamp(self.created_at)
    
    @property
    def age_hours(self) -> float:
        """Return age of share in hours."""
        import time
        return (time.time() - self.created_at) / 3600
    
    @property
    def is_recent(self) -> bool:
        """Check if share was created recently (within 24 hours)."""
        return self.age_hours < 24
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'share_id': self.share_id,
            'share_link': self.share_link,
            'message': self.message,
            'created_at': self.created_at,
            'active': self.active,
            'age_hours': self.age_hours,
            'is_recent': self.is_recent
        }


@dataclass
class TractiveCredentials:
    """Enhanced user credentials for Tractive API with validation."""
    email: str
    password: str
    home_coordinates: Tuple[float, float]
    access_token: Optional[str] = None
    user_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate credentials."""
        if not self.email or '@' not in self.email:
            raise ValueError("Invalid email address")
        if not self.password or len(self.password) < 1:
            raise ValueError("Password cannot be empty")
        
        # Validate home coordinates
        lat, lon = self.home_coordinates
        if not (-90 <= lat <= 90):
            raise ValueError(f"Invalid home latitude: {lat}")
        if not (-180 <= lon <= 180):
            raise ValueError(f"Invalid home longitude: {lon}")
    
    @property
    def is_authenticated(self) -> bool:
        """Check if credentials include valid authentication tokens."""
        return bool(self.access_token and self.user_id)
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.
        
        Args:
            include_sensitive: Whether to include sensitive data like password and tokens
        """
        data = {
            'email': self.email,
            'home_coordinates': self.home_coordinates,
            'is_authenticated': self.is_authenticated
        }
        
        if include_sensitive:
            data.update({
                'password': self.password,
                'access_token': self.access_token,
                'user_id': self.user_id
            })
        
        return data


@dataclass(frozen=True)
class TrackerInfo:
    """Information about a Tractive device/tracker."""
    tracker_id: str
    model_number: str
    hardware_version: str
    firmware_version: str
    
    def __post_init__(self):
        """Validate tracker info."""
        if not self.tracker_id.strip():
            raise ValueError("Tracker ID cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'tracker_id': self.tracker_id,
            'model_number': self.model_number,
            'hardware_version': self.hardware_version,
            'firmware_version': self.firmware_version
        }


@dataclass(frozen=True)
class LocationHistory:
    """Historical GPS location data with analytics."""
    locations: List[GPSLocation]
    total_distance: float
    max_speed: float
    average_speed: float
    time_span_hours: float
    
    def __post_init__(self):
        """Validate location history data."""
        if not self.locations:
            raise ValueError("Location history cannot be empty")
        if self.total_distance < 0:
            raise ValueError(f"Invalid total distance: {self.total_distance}")
        if self.max_speed < 0:
            raise ValueError(f"Invalid max speed: {self.max_speed}")
    
    @property
    def start_location(self) -> GPSLocation:
        """Get the first location in the history."""
        return self.locations[0]
    
    @property
    def end_location(self) -> GPSLocation:
        """Get the last location in the history."""
        return self.locations[-1]
    
    @property
    def location_count(self) -> int:
        """Get the number of GPS points."""
        return len(self.locations)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'location_count': self.location_count,
            'total_distance': self.total_distance,
            'max_speed': self.max_speed,
            'average_speed': self.average_speed,
            'time_span_hours': self.time_span_hours,
            'start_location': self.start_location.to_dict(),
            'end_location': self.end_location.to_dict()
        }
