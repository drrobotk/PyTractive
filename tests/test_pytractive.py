"""
Test suite for PyTractive library.

This module contains comprehensive tests for the PyTractive library,
demonstrating proper testing practices and ensuring code reliability.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import time
from pathlib import Path

# Import our modules
from PyTractive.client import TractiveClient
from PyTractive.models import GPSLocation, DeviceStatus, CommandType, CommandState
from PyTractive.exceptions import TractiveError, AuthenticationError, APIError
from PyTractive.config import TractiveConfig, ConfigManager
from PyTractive.security import CredentialManager


class TestTractiveConfig(unittest.TestCase):
    """Test configuration management."""
    
    def setUp(self):
        self.config = TractiveConfig()
    
    def test_default_config(self):
        """Test default configuration values."""
        self.assertEqual(self.config.api_base_url, "https://graph.tractive.com/3")
        self.assertEqual(self.config.request_timeout, 30)
        self.assertEqual(self.config.retry_attempts, 3)
    
    def test_config_serialization(self):
        """Test config can be serialized to/from JSON."""
        # Create temporary config file
        temp_config = Path("test_config.json")
        
        try:
            # Save config
            self.config.save_to_file(temp_config)
            self.assertTrue(temp_config.exists())
            
            # Load config
            loaded_config = TractiveConfig.load_from_file(temp_config)
            self.assertEqual(loaded_config.api_base_url, self.config.api_base_url)
            self.assertEqual(loaded_config.request_timeout, self.config.request_timeout)
            
        finally:
            # Cleanup
            if temp_config.exists():
                temp_config.unlink()


class TestDataModels(unittest.TestCase):
    """Test data models."""
    
    def test_gps_location_creation(self):
        """Test GPS location model creation."""
        gps_data = {
            "latlong": [40.7128, -74.0060],
            "time": 1640995200,
            "pos_uncertainty": 5.0,
            "altitude": 10.0,
            "speed": 15.0,
            "course": 90.0
        }
        
        location = GPSLocation.from_api_data(gps_data)
        
        self.assertEqual(location.latitude, 40.7128)
        self.assertEqual(location.longitude, -74.0060)
        self.assertEqual(location.timestamp, 1640995200)
        self.assertEqual(location.uncertainty, 5.0)
        self.assertEqual(location.coordinates, (40.7128, -74.0060))
    
    def test_device_status_creation(self):
        """Test device status model creation."""
        tracker_data = {
            "state": "active",
            "battery_save_mode": False
        }
        
        hw_data = {
            "battery_level": 85,
            "hw_status": "operational",
            "time": 1640995200,
            "temperature_state": "normal"
        }
        
        status = DeviceStatus.from_api_data(tracker_data, hw_data)
        
        self.assertEqual(status.battery_level, 85)
        self.assertEqual(status.hardware_status, "operational")
        self.assertFalse(status.is_low_battery)
        self.assertFalse(status.battery_save_mode)
    
    def test_low_battery_detection(self):
        """Test low battery detection."""
        tracker_data = {"state": "active", "battery_save_mode": False}
        hw_data = {"battery_level": 15, "hw_status": "operational", "time": 1640995200}
        
        status = DeviceStatus.from_api_data(tracker_data, hw_data)
        self.assertTrue(status.is_low_battery)


class TestCredentialManager(unittest.TestCase):
    """Test credential management."""
    
    def setUp(self):
        self.cred_manager = CredentialManager("TestApp")
    
    @patch('PyTractive.security.os.environ.get')
    def test_env_var_credentials(self, mock_env_get):
        """Test getting credentials from environment variables."""
        mock_env_get.side_effect = lambda key: {
            'TESTAPP_EMAIL': 'test@example.com',
            'TESTAPP_PASSWORD': 'password123',
            'TESTAPP_HOME_LAT': '40.7128',
            'TESTAPP_HOME_LON': '-74.0060'
        }.get(key)
        
        email, password, coords = self.cred_manager.get_credentials()
        
        self.assertEqual(email, 'test@example.com')
        self.assertEqual(password, 'password123')
        self.assertEqual(coords, (40.7128, -74.0060))
    
    @patch('PyTractive.security.Path.exists')
    @patch('PyTractive.security.Path.read_text')
    def test_legacy_config_reading(self, mock_read_text, mock_exists):
        """Test reading legacy config file."""
        mock_exists.return_value = True
        mock_read_text.return_value = """email test@example.com
password password123
lat 40.7128
long -74.0060"""
        
        # Mock environment variables to return None
        with patch('PyTractive.security.os.environ.get', return_value=None):
            with patch.object(self.cred_manager, '_get_stored_credentials', 
                            side_effect=Exception("No stored creds")):
                email, password, coords = self.cred_manager.get_credentials()
        
        self.assertEqual(email, 'test@example.com')
        self.assertEqual(password, 'password123')
        self.assertEqual(coords, (40.7128, -74.0060))


class TestHTTPClient(unittest.TestCase):
    """Test HTTP client functionality."""
    
    def setUp(self):
        from PyTractive.http_client import HTTPClient
        self.config = TractiveConfig()
        self.client = HTTPClient(self.config)
    
    @patch('requests.Session.request')
    def test_successful_request(self, mock_request):
        """Test successful HTTP request."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response
        
        result = self.client.get("https://api.example.com/test")
        
        self.assertEqual(result, {"status": "success"})
        mock_request.assert_called_once()
    
    @patch('requests.Session.request')
    def test_authentication_error(self, mock_request):
        """Test authentication error handling."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.reason = "Unauthorized"
        mock_request.return_value = mock_response
        
        with self.assertRaises(AuthenticationError):
            self.client.get("https://api.example.com/test")
    
    @patch('requests.Session.request')
    def test_api_error(self, mock_request):
        """Test API error handling."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.reason = "Internal Server Error"
        mock_response.text = "Server error"
        mock_request.return_value = mock_response
        
        with self.assertRaises(APIError) as context:
            self.client.get("https://api.example.com/test")
        
        self.assertEqual(context.exception.status_code, 500)


class TestTractiveClient(unittest.TestCase):
    """Test main Tractive client."""
    
    def setUp(self):
        # Mock the config manager and its dependencies
        with patch('PyTractive.client.ConfigManager') as mock_config_manager:
            mock_config = TractiveConfig()
            mock_config_manager.return_value.config = mock_config
            mock_config_manager.return_value.get_credentials.return_value = (
                "test@example.com", "password123", (40.7128, -74.0060)
            )
            mock_config_manager.return_value.get_access_token.return_value = "mock_token"
            
            with patch('PyTractive.client.HTTPClient') as mock_http_client:
                mock_http_client.return_value.get.return_value = [{"_id": "tracker123"}]
                
                self.client = TractiveClient()
                self.mock_http_client = mock_http_client.return_value
    
    def test_client_initialization(self):
        """Test client initializes correctly."""
        self.assertEqual(self.client.home_coordinates, (40.7128, -74.0060))
        self.assertEqual(self.client.tracker_id, "tracker123")
    
    def test_get_device_status(self):
        """Test getting device status."""
        # Mock API responses
        hw_response = {
            "battery_level": 75,
            "hw_status": "operational",
            "time": 1640995200,
            "temperature_state": "normal"
        }
        
        tracker_response = {
            "state": "active",
            "battery_save_mode": False
        }
        
        self.mock_http_client.get.side_effect = [hw_response, tracker_response]
        
        status = self.client.get_device_status()
        
        self.assertEqual(status.battery_level, 75)
        self.assertEqual(status.hardware_status, "operational")
        self.assertFalse(status.battery_save_mode)
    
    def test_get_gps_location(self):
        """Test getting GPS location."""
        gps_response = {
            "latlong": [40.7128, -74.0060],
            "time": 1640995200,
            "pos_uncertainty": 3.0,
            "altitude": 15.0,
            "speed": 5.0,
            "course": 180.0
        }
        
        self.mock_http_client.get.return_value = gps_response
        
        location = self.client.get_gps_location()
        
        self.assertEqual(location.coordinates, (40.7128, -74.0060))
        self.assertEqual(location.timestamp, 1640995200)
        self.assertEqual(location.uncertainty, 3.0)
    
    def test_send_command(self):
        """Test sending commands to tracker."""
        # Test LED control
        self.client.send_command(CommandType.LED_CONTROL, CommandState.ON)
        self.mock_http_client.post.assert_called()
        
        # Test battery saver (uses different endpoint)
        self.client.send_command(CommandType.BATTERY_SAVER, CommandState.ON)
        # Should be called twice now (LED + battery saver)
        self.assertEqual(self.mock_http_client.post.call_count, 2)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""
    
    def test_time_formatting(self):
        """Test time ago formatting."""
        from PyTractive.utils import format_time_ago
        
        current_time = int(time.time())
        
        # Test seconds
        result = format_time_ago(current_time - 30)
        self.assertEqual(result, "30 seconds ago")
        
        # Test minutes
        result = format_time_ago(current_time - 120)
        self.assertEqual(result, "2 minutes ago")
        
        # Test hours
        result = format_time_ago(current_time - 7200)
        self.assertEqual(result, "2 hours ago")
        
        # Test days
        result = format_time_ago(current_time - 172800)
        self.assertEqual(result, "2 days ago")
    
    def test_coordinate_validation(self):
        """Test coordinate validation."""
        from PyTractive.utils import validate_coordinates
        
        # Valid coordinates
        self.assertTrue(validate_coordinates(40.7128, -74.0060))
        self.assertTrue(validate_coordinates(0, 0))
        self.assertTrue(validate_coordinates(90, 180))
        self.assertTrue(validate_coordinates(-90, -180))
        
        # Invalid coordinates
        self.assertFalse(validate_coordinates(91, 0))  # Latitude too high
        self.assertFalse(validate_coordinates(-91, 0))  # Latitude too low
        self.assertFalse(validate_coordinates(0, 181))  # Longitude too high
        self.assertFalse(validate_coordinates(0, -181))  # Longitude too low


class TestExceptionHandling(unittest.TestCase):
    """Test custom exception handling."""
    
    def test_tractive_error_creation(self):
        """Test custom exception creation."""
        error = TractiveError("Test message", "TEST_CODE")
        self.assertEqual(error.message, "Test message")
        self.assertEqual(error.error_code, "TEST_CODE")
    
    def test_api_error_with_response_data(self):
        """Test API error with response data."""
        response_data = {"error": "Invalid request"}
        error = APIError("API failed", status_code=400, response_data=response_data)
        
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.response_data, response_data)
        self.assertEqual(error.error_code, "API_ERROR")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
