# PyTractive - Modern Tractive GPS Tracker Library

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, comprehensive Python library for interacting with Tractive GPS pet trackers. This library provides both a programmatic API and a user-friendly command-line interface for monitoring and controlling your pet's GPS tracker.

## 🌟 Features

- **Modern Python API** with full type hints and async support
- **Comprehensive CLI** with interactive maps and real-time monitoring
- **Secure credential management** with encryption and cross-platform support
- **Real-time GPS tracking** with fallback methods for reliability
- **Device control** (LED, buzzer, live tracking, battery saver)
- **Data export** to CSV with pandas integration
- **Interactive maps** using Folium
- **Pet information** management and display
- **Public sharing** link management
- **IFTTT integration** for automation
- **Cross-platform** support (Windows, macOS, Linux)

## 🚀 Quick Start

### Installation

```bash
pip install PyTractive
```

Or install from source:

```bash
git clone https://github.com/drrobotk/PyTractive.git
cd PyTractive
pip install -e .
```

### Command Line Usage

The easiest way to get started is with the CLI:

```bash
# Show tracker status
pytractive status

# Get current GPS location with interactive map
pytractive location --interactive

# Control tracker features
pytractive control led_control on
pytractive control buzzer_control on
pytractive control battery_saver on

# Show pet information with photo
pytractive pet --interactive

# Export GPS data to CSV
pytractive export --filename my_pet_data.csv

# Monitor pet and get notified when close to home
pytractive monitor 100  # 100 meter threshold

# Get live location (temporarily enables live tracking)
pytractive live-location
```

### Programmatic Usage

```python
from PyTractive import TractiveClient
from PyTractive.models import CommandType, CommandState

# Initialize client (will prompt for credentials on first run)
with TractiveClient() as client:
    # Get device status
    status = client.get_device_status()
    print(f"Battery: {status.battery_level}%")
    
    # Get GPS location
    location = client.get_gps_location()
    print(f"Pet is at: {location.coordinates}")
    
    # Control device
    client.send_command(CommandType.LED_CONTROL, CommandState.ON)
    
    # Get pet information
    pet = client.get_pet_data()
    print(f"Pet name: {pet.name}")
    
    # Export GPS data
    df = client.export_gps_data("gps_data.csv")
    print(f"Exported {len(df)} GPS records")
```

## 🔧 Configuration

### Environment Variables

Set these environment variables for automatic authentication:

```bash
export TRACTIVE_EMAIL="your-email@example.com"
export TRACTIVE_PASSWORD="your-password"
export TRACTIVE_HOME_LAT="40.7128"
export TRACTIVE_HOME_LON="-74.0060"
```

### Configuration File

Create `pytractive_config.json` for custom settings:

```json
{
  "api_base_url": "https://graph.tractive.com/3",
  "request_timeout": 30,
  "retry_attempts": 3,
  "max_gps_fallback_hours": 24
}
```

### Credential Storage

PyTractive securely stores your credentials using:
- **Encrypted storage** on your local machine
- **Environment variables** for CI/CD and containers
- **Legacy config file** support (`login.conf`)

## 📊 Data Models

The library uses strongly-typed data models:

```python
@dataclass
class GPSLocation:
    latitude: float
    longitude: float
    timestamp: int
    uncertainty: float
    altitude: float = 0.0
    speed: float = 0.0
    course: float = 0.0

@dataclass  
class DeviceStatus:
    battery_level: int
    hardware_status: str
    timestamp: int
    temperature_state: str = "NA"
    state: DeviceState = DeviceState.UNKNOWN
    battery_save_mode: bool = False

@dataclass
class PetData:
    name: str
    pet_type: str
    gender: str
    breed: str
    # ... and more
```

## 🔒 Security

- **Encrypted credential storage** using `cryptography` library
- **Secure session management** with automatic token refresh
- **Cross-platform secure storage** (Windows Registry, Unix permissions)
- **No hardcoded credentials** in code

## 🗺️ Interactive Features

- **Real-time maps** showing pet location and home
- **Distance calculations** from home location
- **Address geocoding** using Nominatim
- **Pet photo display** with automatic resizing
- **Progress bars** for long-running operations

## 🔄 API Features

- **Automatic retries** with exponential backoff
- **Rate limiting** to respect API limits  
- **Comprehensive error handling** with custom exceptions
- **Session management** with connection pooling
- **Timeout handling** for reliability

## 🛠️ Development

### Setup Development Environment

```bash
git clone https://github.com/drrobotk/PyTractive.git
cd PyTractive
pip install -e ".[dev]"
```

### Run Examples

```bash
python examples.py
```

### CLI Help

```bash
pytractive --help
```

## 📋 Requirements

- **Python 3.8+**
- **requests** - HTTP client
- **cryptography** - Secure credential storage
- **pandas** - Data export and analysis
- **click** - CLI framework (optional)
- **folium** - Interactive maps (optional)
- **geopy** - Geocoding and distance calculations (optional)
- **pillow** - Image processing (optional)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Tractive** for providing the GPS tracker hardware and API
- **Original PyTractive** project for inspiration
- **Contributors** who help improve this library

## 📞 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/drrobotk/PyTractive/issues)
- **Documentation**: [Full API documentation](https://github.com/drrobotk/PyTractive/blob/main/README.md)

---

## What is Tractive GPS?

![tractive_logo](https://camo.githubusercontent.com/6dbfd1a54584066a2b629f438f1a9a83738a62d8810c190f415134e5ca80e928/68747470733a2f2f7777772e636f75706f6e736b6973732e636f6d2f77702d636f6e74656e742f75706c6f6164732f323031392f30342f54726163746976652d4c6f676f2d323030783230302e706e67)

Tractive is a GPS tracking device designed for pets. It allows pet owners to monitor their pet's location in real-time, set up safe zones, track activity levels, and receive notifications when their pet leaves designated areas. The device is lightweight, waterproof, and provides long battery life for continuous tracking.

Tractive GPS Activity Monitor allows you to track your pet wherever it goes by showing the live location in the free Tractive GPS app on your smartphone or in your web browser, with location updates every 2-3 seconds in live mode. 

<img src="https://github.com/drrobotk/PyTractive/assets/51001263/21e6d9a6-2b45-4838-9203-1cb45d8a3540" alt="tractive_tracker" width="300"/>

The cat tracker records the daily activity of your kitty and shows you how active, playful or calm they are, and how much time they are sleeping, as well as being able to set activity goals for them. 

The app also allows you to view your cat's location history to see how much they are moving each day as well as finding out where their adventures take them, see the usual places they visit and where they spend most of their time with the heat map. 

The tracker collar is waterproof and lightweight at only 30g, making it perfectly designed for adventurous cats. Tractive charges a subscription fee that covers the cost for all mobile charges and provides you with unlimited location tracking.
