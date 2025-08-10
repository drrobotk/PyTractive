"""
Modern command-line interface for PyTractive.

This module provides a user-friendly CLI for interacting with Tractive GPS trackers.
"""

import sys
import time
import logging
from pathlib import Path
from typing import Optional
import webbrowser
from datetime import datetime
import functools

try:
    import click
    import folium
    from geopy.distance import geodesic
    from geopy.geocoders import Nominatim
    from PIL import Image
    import requests
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Please install with: pip install click folium geopy pillow requests")
    sys.exit(1)

from .client import TractiveClient
from .models import CommandType, CommandState
from .exceptions import TractiveError
from .utils import format_time_ago, setup_logging


logger = logging.getLogger(__name__)


def handle_exceptions(func):
    """Decorator to handle exceptions in CLI commands."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TractiveError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)
        except Exception as e:
            logger.exception("Unexpected error")
            click.echo(f"Unexpected error: {e}", err=True)
            sys.exit(1)
    return wrapper


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config', '-c', type=click.Path(), help='Path to config file')
@click.pass_context
def cli(ctx, verbose: bool, config: Optional[str]):
    """PyTractive - Modern Tractive GPS Tracker Interface."""
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logging(log_level)
    
    # Initialize client
    config_path = Path(config) if config else None
    ctx.ensure_object(dict)
    ctx.obj['client'] = TractiveClient(config_path)


@cli.command()
@click.pass_context
@handle_exceptions
def status(ctx):
    """Show tracker and device status."""
    client: TractiveClient = ctx.obj['client']
    
    # Get device status
    device_status = client.get_device_status()
    
    click.echo("=" * 80)
    click.echo(f"Tracker ID: {client.tracker_id}")
    click.echo(f"Last network connection: {device_status.datetime} ({format_time_ago(device_status.timestamp)})")
    click.echo(f"Hardware status: {device_status.hardware_status}")
    click.echo(f"Temperature state: {device_status.temperature_state.value if device_status.temperature_state else None}")
    click.echo(f"Battery level: {device_status.battery_level}%")
    click.echo(f"Battery saver mode: {device_status.battery_save_mode}")
    click.echo(f"GPS state: {device_status.state.value if device_status.state else None}")
    
    if device_status.is_low_battery:
        click.echo(click.style("⚠️  Low battery warning!", fg='red', bold=True))
    
    click.echo("=" * 80)


@cli.command()
@click.option('--interactive', '-i', is_flag=True, help='Open interactive map')
@click.pass_context
@handle_exceptions  
def location(ctx, interactive: bool):
    """Get current GPS location."""
    client: TractiveClient = ctx.obj['client']
    
    # Get GPS location
    gps_location = client.get_gps_location()
    device_status = client.get_device_status(partial=True)
    
    # Get address using geocoding
    try:
        geolocator = Nominatim(user_agent='PyTractive')
        location_info = geolocator.reverse(gps_location.coordinates)
        address = location_info.address if location_info else "Address not found"
    except Exception as e:
        logger.warning(f"Geocoding failed: {e}")
        address = "Address lookup failed"
    
    # Calculate distance from home
    distance_home = int(geodesic(client.home_coordinates, gps_location.coordinates).m)
    
    # Display information
    click.echo(f"Last GPS connection: {gps_location.datetime} ({format_time_ago(gps_location.timestamp)})")
    click.echo(f"GPS uncertainty: {gps_location.uncertainty}%")
    click.echo(f"GPS coordinates: {gps_location.coordinates}")
    click.echo(f"Address: {address}")
    click.echo(f"Distance from Home: {distance_home}m")
    click.echo(f"Altitude: {gps_location.altitude}m")
    click.echo(f"Speed: {gps_location.speed} km/h")
    click.echo(f"Course: {gps_location.course}°")
    
    if distance_home < 50:
        click.echo(click.style("🏠 Pet is near home!", fg='green', bold=True))
    
    # Create interactive map if requested
    if interactive:
        _create_interactive_map(client, gps_location, device_status, distance_home)


def _create_interactive_map(client, gps_location, device_status, distance_home):
    """Create and open interactive map."""
    try:
        # Calculate map center and zoom
        pet_coords = gps_location.coordinates
        home_coords = client.home_coordinates
        
        center_lat = (pet_coords[0] + home_coords[0]) / 2
        center_lon = (pet_coords[1] + home_coords[1]) / 2
        
        if distance_home < 100:
            zoom = 20
        elif distance_home < 200:
            zoom = 18
        else:
            zoom = 16
        
        # Create map
        map_obj = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom,
            control_scale=True
        )
        
        # Add pet marker
        pet_info = (
            f"Battery: {device_status.battery_level}% | "
            f"Distance: {distance_home}m | "
            f"Last GPS: {format_time_ago(gps_location.timestamp)}"
        )
        folium.Marker(
            pet_coords,
            popup=folium.Popup(pet_info, min_width=420, max_width=420),
            icon=folium.Icon(color='red', icon='paw', prefix='fa')
        ).add_to(map_obj)
        
        # Add home marker
        folium.Marker(
            home_coords,
            popup='Home',
            icon=folium.Icon(color='green', icon='home')
        ).add_to(map_obj)
        
        # Add line between pet and home
        folium.PolyLine(
            [pet_coords, home_coords],
            color="darkred",
            weight=3,
            opacity=0.8,
            popup=f'{distance_home}m'
        ).add_to(map_obj)
        
        # Save and open map
        map_file = Path('pet_location_map.html')
        map_obj.save(str(map_file))
        
        click.echo(f"Opening interactive map: {map_file}")
        webbrowser.open(f'file://{map_file.absolute()}')
        
    except Exception as e:
        logger.error(f"Failed to create map: {e}")
        click.echo(f"Failed to create interactive map: {e}", err=True)


@cli.command()
@click.argument('command', type=click.Choice(['battery_saver', 'live_tracking', 'led_control', 'buzzer_control']))
@click.argument('state', type=click.Choice(['on', 'off']))
@click.pass_context
@handle_exceptions
def control(ctx, command: str, state: str):
    """Control tracker features."""
    client: TractiveClient = ctx.obj['client']
    
    cmd_type = CommandType(command)
    cmd_state = CommandState(state)
    
    click.echo(f"Sending command: {command} {state}")
    client.send_command(cmd_type, cmd_state)
    click.echo(click.style("✓ Command sent successfully", fg='green'))


@cli.command()
@click.option('--interactive', '-i', is_flag=True, help='Show pet image')
@click.pass_context
@handle_exceptions
def pet(ctx, interactive: bool):
    """Show pet information."""
    client: TractiveClient = ctx.obj['client']
    
    pet_data = client.get_pet_data()
    
    click.echo("Pet Details:")
    click.echo(f"Name: {pet_data.name}")
    click.echo(f"Type: {pet_data.pet_type}")
    click.echo(f"Breed: {pet_data.breed}")
    click.echo(f"Gender: {pet_data.gender}")
    click.echo(f"Birthday: {pet_data.birthday_datetime}")
    click.echo(f"Neutered: {pet_data.neutered}")
    click.echo(f"Chip ID: {pet_data.chip_id}")
    click.echo(f"Profile created: {pet_data.created_datetime}")
    click.echo(f"Profile updated: {pet_data.updated_datetime}")
    click.echo(f"Picture URL: {pet_data.profile_picture_url}")
    
    if interactive and pet_data.profile_picture_id:
        try:
            # Download and display pet image
            response = requests.get(pet_data.profile_picture_url, stream=True)
            response.raise_for_status()
            
            img = Image.open(response.raw)
            # Resize image for display
            basewidth = 600
            wpercent = (basewidth / float(img.size[0]))
            hsize = int((float(img.size[1]) * float(wpercent)))
            img = img.resize((basewidth, hsize), Image.Resampling.LANCZOS)
            img.show()
            
        except Exception as e:
            logger.error(f"Failed to display pet image: {e}")
            click.echo(f"Failed to display pet image: {e}", err=True)


@cli.command()
@click.option('--filename', '-f', default='gps_data.csv', help='Output filename')
@click.option('--convert-timestamps', is_flag=True, help='Convert timestamps to datetime')
@click.option('--analytics', is_flag=True, default=True, help='Include analytics columns')
@click.pass_context
@handle_exceptions
def export(ctx, filename: str, convert_timestamps: bool, analytics: bool):
    """Export GPS data to CSV file with analytics."""
    client: TractiveClient = ctx.obj['client']
    
    click.echo("📊 Exporting GPS data...")
    
    try:
        # Export GPS data using the modern client
        df = client.export_gps_data(
            filename=filename, 
            convert_timestamps=convert_timestamps,
            include_analytics=analytics
        )
        
        click.echo(f"✓ Exported {len(df)} GPS records to {filename}")
        
        if analytics:
            click.echo("📈 Analytics columns included: distance, speed, cumulative distance")
        
    except Exception as e:
        click.echo(f"Export failed: {e}", err=True)
        raise


@cli.command()
@click.option('--hours', '-h', default=24, help='Hours of history to retrieve')
@click.option('--analytics', is_flag=True, default=True, help='Include analytics')
@click.pass_context
@handle_exceptions
def history(ctx, hours: int, analytics: bool):
    """Show location history with analytics."""
    client: TractiveClient = ctx.obj['client']
    
    click.echo(f"📍 Retrieving {hours} hours of location history...")
    
    try:
        history_data = client.get_location_history(hours, include_analytics=analytics)
        
        click.echo("=" * 80)
        click.echo(f"Location History ({hours} hours)")
        click.echo("=" * 80)
        click.echo(f"Total GPS points: {history_data.location_count}")
        click.echo(f"Time span: {history_data.time_span_hours:.1f} hours")
        
        if analytics:
            click.echo(f"Total distance: {history_data.total_distance:.0f} meters")
            click.echo(f"Max speed: {history_data.max_speed:.1f} km/h")
            click.echo(f"Average speed: {history_data.average_speed:.1f} km/h")
            
            # Show start and end locations
            click.echo(f"\n📍 Start: {history_data.start_location.coordinates} at {history_data.start_location.datetime}")
            click.echo(f"📍 End: {history_data.end_location.coordinates} at {history_data.end_location.datetime}")
        
        click.echo("=" * 80)
        
    except Exception as e:
        click.echo(f"Failed to get location history: {e}", err=True)


@cli.command()
@click.pass_context
@handle_exceptions
def stats(ctx):
    """Show client session statistics."""
    client: TractiveClient = ctx.obj['client']
    
    stats = client.stats
    
    click.echo("=" * 80)
    click.echo("PyTractive Session Statistics")
    click.echo("=" * 80)
    click.echo(f"Session runtime: {stats['session_runtime_seconds']:.1f} seconds")
    click.echo(f"API requests made: {stats['requests_made']}")
    click.echo(f"Cache hits: {stats['cache_hits']}")
    click.echo(f"Cache hit rate: {stats['cache_hit_rate']*100:.1f}%")
    click.echo(f"Errors encountered: {stats['errors_encountered']}")
    click.echo(f"Requests per minute: {(stats['requests_made'] / stats['session_runtime_seconds'] * 60):.1f}")
    click.echo("=" * 80)


@cli.command()
@click.option('--detailed', '-d', is_flag=True, help='Show detailed battery analysis')
@click.pass_context
@handle_exceptions
def battery(ctx, detailed: bool):
    """Show detailed battery information and health."""
    client: TractiveClient = ctx.obj['client']
    
    device_status = client.get_device_status()
    
    click.echo("=" * 80)
    click.echo("🔋 Battery Status & Health")
    click.echo("=" * 80)
    click.echo(f"Current level: {device_status.battery_level}%")
    click.echo(f"Battery state: {device_status.battery_state.value}")
    click.echo(f"Battery saver mode: {'ON' if device_status.battery_save_mode else 'OFF'}")
    click.echo(f"Temperature state: {device_status.temperature_state.value}")
    
    # Battery level visualization
    battery_bar = "█" * (device_status.battery_level // 5) + "░" * (20 - device_status.battery_level // 5)
    color = 'red' if device_status.is_low_battery else 'yellow' if device_status.battery_level < 50 else 'green'
    click.echo(f"Visual: [{click.style(battery_bar, fg=color)}] {device_status.battery_level}%")
    
    if device_status.is_low_battery:
        click.echo(click.style("⚠️  LOW BATTERY WARNING!", fg='red', bold=True))
    elif device_status.is_critical_battery:
        click.echo(click.style("🚨 CRITICAL BATTERY ALERT!", fg='red', bold=True))
    
    if detailed:
        click.echo(f"\nLast update: {device_status.datetime} ({format_time_ago(device_status.timestamp)})")
        click.echo(f"Time since update: {device_status.time_since_last_update} seconds")
        click.echo(f"Needs attention: {'YES' if device_status.needs_attention else 'NO'}")
        click.echo(f"Hardware status: {device_status.hardware_status}")
    
    click.echo("=" * 80)


@cli.command()
@click.option('--message', '-m', default='Pet location sharing', help='Share message')
@click.option('--list', '-l', 'list_shares', is_flag=True, help='List existing shares')
@click.pass_context
@handle_exceptions
def share(ctx, message: str, list_shares: bool):
    """Create and manage public location shares."""
    client: TractiveClient = ctx.obj['client']
    
    if list_shares:
        # This would require additional API implementation
        click.echo("📋 Public shares management coming soon...")
        return
    
    click.echo("🔗 Creating public share...")
    try:
        share_info = client.create_public_share(message)
        
        click.echo("=" * 80)
        click.echo("✓ Public Share Created")
        click.echo("=" * 80)
        click.echo(f"Share ID: {share_info.share_id}")
        click.echo(f"Share Link: {share_info.share_link}")
        click.echo(f"Message: {share_info.message}")
        click.echo(f"Created: {share_info.created_datetime}")
        click.echo(f"Age: {share_info.age_hours:.1f} hours")
        click.echo("=" * 80)
        
    except Exception as e:
        click.echo(f"Failed to create share: {e}", err=True)


@cli.command()
@click.option('--threshold', '-t', default=50, help='Home threshold in meters')
@click.pass_context
@handle_exceptions
def home_status(ctx, threshold: int):
    """Check if pet is currently at home."""
    client: TractiveClient = ctx.obj['client']
    
    click.echo(f"🏠 Checking home status (threshold: {threshold}m)...")
    
    try:
        location = client.get_gps_location()
        distance = client.get_distance_from_home(location)
        is_home = client.is_pet_at_home(threshold)
        
        click.echo("=" * 80)
        click.echo("🏠 Home Status")
        click.echo("=" * 80)
        click.echo(f"Current location: {location.coordinates}")
        click.echo(f"Home coordinates: {client.home_coordinates}")
        click.echo(f"Distance from home: {distance:.0f} meters")
        click.echo(f"Threshold: {threshold} meters")
        
        if is_home:
            click.echo(click.style("✅ Pet is AT HOME!", fg='green', bold=True))
        else:
            click.echo(click.style(f"❌ Pet is AWAY from home ({distance:.0f}m)", fg='red', bold=True))
        
        click.echo("=" * 80)
        
    except Exception as e:
        click.echo(f"Failed to check home status: {e}", err=True)


@cli.command()
@click.pass_context
@handle_exceptions
def info(ctx):
    """Show comprehensive tracker and pet information."""
    client: TractiveClient = ctx.obj['client']
    
    click.echo("📱 Getting tracker and pet information...")
    
    try:
        # Get all information
        tracker_info = client.tracker_info
        pet_data = client.get_pet_data()
        device_status = client.get_device_status()
        location = client.get_gps_location()
        
        click.echo("=" * 80)
        click.echo("📱 Tracker Information")
        click.echo("=" * 80)
        click.echo(f"Tracker ID: {tracker_info.tracker_id}")
        click.echo(f"Model: {tracker_info.model_number}")
        click.echo(f"Hardware: {tracker_info.hardware_version}")
        click.echo(f"Firmware: {tracker_info.firmware_version}")
        click.echo(f"Online: {'YES' if device_status.is_online else 'NO'}")
        
        click.echo("\n🐕 Pet Information")
        click.echo("=" * 80)
        click.echo(f"Name: {pet_data.name}")
        click.echo(f"Type: {pet_data.pet_type}")
        click.echo(f"Breed: {pet_data.breed}")
        click.echo(f"Gender: {pet_data.gender}")
        click.echo(f"Age: {pet_data.age_description}")
        click.echo(f"Neutered: {'YES' if pet_data.neutered else 'NO'}")
        if pet_data.weight:
            click.echo(f"Weight: {pet_data.weight} kg")
        
        click.echo("\n📍 Current Status")
        click.echo("=" * 80)
        click.echo(f"Location: {location.coordinates}")
        click.echo(f"GPS accuracy: {location.accuracy_level}")
        click.echo(f"Battery: {device_status.battery_level}% ({device_status.battery_state.value})")
        click.echo(f"Last update: {format_time_ago(location.timestamp)}")
        
        distance_home = client.get_distance_from_home(location)
        if distance_home < 50:
            click.echo(click.style(f"🏠 At home ({distance_home:.0f}m)", fg='green'))
        else:
            click.echo(f"📍 Away from home ({distance_home:.0f}m)")
        
        click.echo("=" * 80)
        
    except Exception as e:
        click.echo(f"Failed to get information: {e}", err=True)


@cli.command()
@click.option('--interactive', '-i', is_flag=True, help='Open interactive map')
@click.pass_context
@handle_exceptions
def all(ctx, interactive: bool):
    """Show comprehensive status report with all tracker and pet information."""
    client: TractiveClient = ctx.obj['client']
    
    click.echo("🎯" + "=" * 79)
    click.echo("               PYTRACTIVE COMPREHENSIVE STATUS REPORT")
    click.echo("🎯" + "=" * 79)
    
    try:
        # Get all data
        tracker_info = client.tracker_info
        pet_data = client.get_pet_data()
        device_status = client.get_device_status()
        location = client.get_gps_location()
        distance_home = client.get_distance_from_home(location)
        is_home = distance_home <= 50
        
        # Get address using geocoding
        try:
            geolocator = Nominatim(user_agent='PyTractive')
            location_info = geolocator.reverse(location.coordinates)
            address = location_info.address if location_info else "Address not found"
        except Exception as e:
            logger.warning(f"Geocoding failed: {e}")
            address = "Address lookup failed"
        
        # 1. DEVICE & TRACKER INFO
        click.echo()
        click.echo("📱 DEVICE & TRACKER INFORMATION")
        click.echo("-" * 80)
        click.echo(f"Tracker ID: {tracker_info.tracker_id}")
        click.echo(f"Model: {tracker_info.model_number}")
        click.echo(f"Hardware Version: {tracker_info.hardware_version}")
        click.echo(f"Firmware Version: {tracker_info.firmware_version}")
        click.echo(f"Online Status: {'🟢 ONLINE' if device_status.is_online else '🔴 OFFLINE'}")
        click.echo(f"Last Network Connection: {device_status.datetime} ({format_time_ago(device_status.timestamp)})")
        click.echo(f"Hardware Status: {device_status.hardware_status}")
        click.echo(f"GPS State: {device_status.state.value if device_status.state else None}")
        
        # 2. BATTERY STATUS
        click.echo()
        click.echo("🔋 BATTERY STATUS & HEALTH")
        click.echo("-" * 80)
        battery_bar = "█" * (device_status.battery_level // 5) + "░" * (20 - device_status.battery_level // 5)
        color = 'red' if device_status.is_low_battery else 'yellow' if device_status.battery_level < 50 else 'green'
        click.echo(f"Battery Level: {device_status.battery_level}% [{click.style(battery_bar, fg=color)}]")
        click.echo(f"Battery State: {device_status.battery_state.value.upper()}")
        click.echo(f"Battery Saver Mode: {'🟢 ON' if device_status.battery_save_mode else '🔴 OFF'}")
        click.echo(f"Temperature State: {device_status.temperature_state.value if device_status.temperature_state else None}")
        
        if device_status.is_low_battery:
            click.echo(click.style("⚠️  LOW BATTERY WARNING!", fg='red', bold=True))
        elif device_status.is_critical_battery:
            click.echo(click.style("🚨 CRITICAL BATTERY ALERT!", fg='red', bold=True))
        
        # 3. GPS LOCATION & TRACKING
        click.echo()
        click.echo("📍 GPS LOCATION & TRACKING")
        click.echo("-" * 80)
        click.echo(f"Current Coordinates: {location.coordinates}")
        click.echo(f"Address: {address}")
        click.echo(f"Last GPS Update: {location.datetime} ({format_time_ago(location.timestamp)})")
        click.echo(f"GPS Accuracy: {location.accuracy_level} (uncertainty: {location.uncertainty}%)")
        click.echo(f"Altitude: {location.altitude}m")
        click.echo(f"Speed: {location.speed} km/h")
        click.echo(f"Course/Direction: {location.course}°")
        click.echo(f"Is Moving: {'🏃 YES' if location.is_moving else '🛑 NO'}")
        
        # 4. HOME STATUS & GEOFENCING
        click.echo()
        click.echo("🏠 HOME STATUS & GEOFENCING")
        click.echo("-" * 80)
        click.echo(f"Home Coordinates: {client.home_coordinates}")
        click.echo(f"Distance from Home: {distance_home:.0f} meters")
        click.echo(f"Home Threshold: 50 meters")
        
        if is_home:
            click.echo(click.style("✅ PET IS AT HOME!", fg='green', bold=True))
        else:
            click.echo(click.style(f"❌ PET IS AWAY FROM HOME ({distance_home:.0f}m)", fg='red', bold=True))
        
        # 5. PET INFORMATION
        click.echo()
        click.echo("🐕 PET INFORMATION")
        click.echo("-" * 80)
        click.echo(f"Name: {pet_data.name}")
        click.echo(f"Type: {pet_data.pet_type}")
        click.echo(f"Breed: {pet_data.breed}")
        click.echo(f"Gender: {pet_data.gender}")
        click.echo(f"Age: {pet_data.age_description}")
        click.echo(f"Neutered: {'YES' if pet_data.neutered else 'NO'}")
        if pet_data.weight:
            click.echo(f"Weight: {pet_data.weight} kg")
        click.echo(f"Chip ID: {pet_data.chip_id}")
        click.echo(f"Profile Created: {pet_data.created_datetime}")
        
        # 6. ACTIVITY SUMMARY
        click.echo()
        click.echo("📊 ACTIVITY SUMMARY")
        click.echo("-" * 80)
        
        # Calculate time since last updates
        gps_age_minutes = (time.time() - location.timestamp) / 60
        network_age_minutes = (time.time() - device_status.timestamp) / 60
        
        click.echo(f"GPS Data Freshness: {gps_age_minutes:.0f} minutes old")
        click.echo(f"Network Data Freshness: {network_age_minutes:.0f} minutes old")
        
        # Status indicators
        status_indicators = []
        if device_status.is_low_battery:
            status_indicators.append("⚠️  Low Battery")
        if not device_status.is_online:
            status_indicators.append("🔴 Offline")
        if distance_home > 100:
            status_indicators.append(f"📍 Away from Home ({distance_home:.0f}m)")
        if location.is_moving:
            status_indicators.append("🏃 Pet is Moving")
        if gps_age_minutes > 30:
            status_indicators.append("📡 GPS Data Stale")
        
        if status_indicators:
            click.echo("Active Alerts: " + " | ".join(status_indicators))
        else:
            click.echo(click.style("✅ All Systems Normal - No Alerts", fg='green', bold=True))
        
        # 7. SESSION STATISTICS
        stats = client.stats
        click.echo()
        click.echo("📈 SESSION STATISTICS")
        click.echo("-" * 80)
        click.echo(f"Session Runtime: {stats['session_runtime_seconds']:.1f} seconds")
        click.echo(f"API Requests Made: {stats['requests_made']}")
        click.echo(f"Cache Hit Rate: {stats['cache_hit_rate']*100:.1f}%")
        click.echo(f"Errors Encountered: {stats['errors_encountered']}")
        
        click.echo()
        click.echo("🎯" + "=" * 79)
        click.echo(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo("🎯" + "=" * 79)
        
        # Create interactive map if requested
        if interactive:
            click.echo()
            click.echo("🗺️  Opening interactive map...")
            _create_interactive_map(client, location, device_status, distance_home)
        
    except Exception as e:
        click.echo(f"Failed to generate comprehensive report: {e}", err=True)


@cli.command()
@click.argument('mac_address')
@click.option('--command', '-c', type=click.Choice(['battery', 'light', 'sound']), help='Bluetooth command to execute')
@click.option('--state', '-s', type=click.Choice(['on', 'off']), help='State for light/sound commands')
@click.pass_context
@handle_exceptions
def bluetooth(ctx, mac_address: str, command: Optional[str], state: Optional[str]):
    """Direct Bluetooth BLE communication with tracker (Linux only)."""
    try:
        import platform
        if not platform.system().lower() == 'linux':
            click.echo("❌ Bluetooth functionality is only available on Linux", err=True)
            return
            
        # Import the bluetooth module
        from .bluetooth_linux import connect_to_device, read_battery_level, handle_commands
        import pexpect
        
        click.echo(f"🔵 Connecting to Bluetooth device: {mac_address}")
        
        # Run gatttool interactively
        gatt = pexpect.spawn(f'gatttool -b {mac_address} -t random -I')
        
        # Connect to device
        connect_to_device(gatt, mac_address)
        
        if command == 'battery' or command is None:
            read_battery_level(gatt)
        
        if command in ['light', 'sound'] and state:
            # Handle light/sound commands
            handle = 'c1670003-2c5d-42fd-be9b-1f2dd6681818'  # Default handle
            if command == 'light':
                if state == 'on':
                    cmd = '0b00080280000000000000004b'
                else:
                    cmd = '0b000802010000000000000001'
            elif command == 'sound':
                if state == 'on':
                    cmd = '0b0019022001040102010101e0'
                else:
                    cmd = '0b001902010000000000000001'
            
            gatt.sendline(f'char-write-req {handle} {cmd}')
            click.echo(f"✓ {command.title()} {state} command sent via Bluetooth")
        
        # Disconnect
        gatt.sendline('disconnect')
        gatt.sendline('exit')
        
    except ImportError:
        click.echo("❌ Bluetooth dependencies not available. Install: pip install pexpect colorama", err=True)
    except Exception as e:
        click.echo(f"❌ Bluetooth operation failed: {e}", err=True)


@cli.command()
@click.pass_context
@handle_exceptions  
def gui(ctx):
    """Launch the Tkinter GUI interface."""
    try:
        click.echo("🖥️  Launching PyTractive Simple GUI...")
        from .gui_simple import launch_simple_gui
        launch_simple_gui()
    except ImportError:
        click.echo("❌ GUI dependencies not available. Install tkinter.", err=True)
    except Exception as e:
        click.echo(f"❌ Failed to launch GUI: {e}", err=True)


@cli.command()
@click.pass_context
@handle_exceptions  
def gui_advanced(ctx):
    """Launch the advanced Tkinter GUI interface (experimental)."""
    try:
        click.echo("🖥️  Launching PyTractive Advanced GUI...")
        from .gui import launch_gui
        launch_gui()
    except ImportError:
        click.echo("❌ GUI dependencies not available. Install tkinter.", err=True)
    except Exception as e:
        click.echo(f"❌ Failed to launch advanced GUI: {e}", err=True)
        click.echo("💡 Try 'gui' or 'web-gui' commands for alternative interfaces")


@cli.command()
@click.option('--port', '-p', default=8080, help='Port for web server')
@click.pass_context
@handle_exceptions  
def web_gui(ctx, port: int):
    """Launch the web-based GUI interface."""
    try:
        click.echo("🌐 Launching PyTractive Web Interface...")
        from .web_gui import launch_web_gui
        client = ctx.obj['client']
        launch_web_gui(port, client)
    except Exception as e:
        click.echo(f"❌ Failed to launch web GUI: {e}", err=True)


@cli.command()
@click.argument('distance_threshold', type=int)
@click.option('--ifttt-key', help='IFTTT webhook key for notifications')
@click.pass_context
@handle_exceptions
def trigger(ctx, distance_threshold: int, ifttt_key: Optional[str]):
    """Monitor location and trigger IFTTT notifications when pet gets close to home."""
    client: TractiveClient = ctx.obj['client']
    
    if not ifttt_key:
        try:
            from .user_env import user_environ
            ifttt_key = user_environ('IFTTT_KEY')
        except:
            click.echo("❌ IFTTT key required. Use --ifttt-key or set IFTTT_KEY environment variable", err=True)
            return
    
    click.echo(f"🔔 Starting location trigger (threshold: {distance_threshold}m)")
    click.echo("📱 You will receive notifications when pet gets closer to home")
    click.echo("Press Ctrl+C to stop monitoring")
    
    try:
        # Import IFTTT functionality  
        from .tractive import IFTTT_trigger
        
        location = client.get_gps_location()
        distance_home = int(client.get_distance_from_home(location))
        last_distance = distance_home
        
        click.echo(f"📍 Starting distance: {distance_home}m from home")
        
        while distance_home >= distance_threshold:
            try:
                # Get current location and battery
                location = client.get_gps_location()
                device_status = client.get_device_status(partial=True)
                
                # Battery saver check
                if device_status.battery_level < 30:
                    client.send_command(CommandType.BATTERY_SAVER, CommandState.ON)
                    click.echo(f"🔋 Low battery! Enabled battery saver ({device_status.battery_level}%)")
                
                # Calculate distance
                distance_home = int(client.get_distance_from_home(location))
                
                # Check if getting closer
                if distance_home < last_distance:
                    click.echo(f"📍 Getting closer... ({distance_home}m from home)")
                    last_distance = distance_home
                    
                    # Send IFTTT notification
                    IFTTT_trigger(action='billy_notification', key=ifttt_key)
                    click.echo("📨 IFTTT notification sent")
                
                # Wait before next check
                time.sleep(10)
                
            except KeyboardInterrupt:
                click.echo("\n👋 Trigger monitoring stopped by user")
                return
            except Exception as e:
                click.echo(f"⚠️  Error during monitoring: {e}")
                time.sleep(5)
        
        # Pet reached home!
        click.echo(f"🏠 Pet reached home! Final distance: {distance_home}m")
        IFTTT_trigger(action='billy_call', key=ifttt_key)
        click.echo("📞 IFTTT call trigger sent")
        
    except ImportError:
        click.echo("❌ IFTTT functionality not available in current installation", err=True)
    except KeyboardInterrupt:
        click.echo("\n👋 Trigger monitoring stopped by user")


@cli.command() 
@click.pass_context
def demo(ctx):
    """Run PyTractive in demonstration mode with sample outputs."""
    click.echo("🎯 PyTractive CLI Demonstration")
    click.echo("=" * 80)
    
    # Demonstrate different command outputs
    click.echo("📋 Available Commands:")
    commands = [
        ("all", "Show comprehensive status report with everything"),
        ("status", "Show tracker and device status"),
        ("location", "Get current GPS location (use -i for map)"),
        ("control", "Control tracker features (battery_saver, live_tracking, etc.)"),
        ("pet", "Show pet information (use -i to view photo)"),
        ("battery", "Show detailed battery status (use -d for details)"),
        ("history", "Show location history with analytics"),
        ("export", "Export GPS data to CSV with analytics"),
        ("monitor", "Monitor pet location in real-time"),
        ("live_location", "Get live GPS location"),
        ("share", "Create public location share"),
        ("home_status", "Check if pet is at home"),
        ("info", "Show comprehensive tracker/pet info"),
        ("stats", "Show session statistics"),
        ("bluetooth", "Direct Bluetooth BLE communication (Linux only)"),
        ("gui", "Launch Tkinter GUI interface"),
        ("trigger", "IFTTT location trigger notifications"),
        ("demo", "This demonstration mode")
    ]
    
    for cmd, desc in commands:
        click.echo(f"  {click.style(cmd, fg='cyan', bold=True):<15} - {desc}")
    
    click.echo("\n📖 Example Usage:")
    examples = [
        "python pytractive_cli.py status",
        "python pytractive_cli.py location -i",
        "python pytractive_cli.py control live_tracking on",
        "python pytractive_cli.py bluetooth AA:BB:CC:DD:EE:FF --command battery",
        "python pytractive_cli.py gui",
        "python pytractive_cli.py trigger 100 --ifttt-key YOUR_KEY",
        "python pytractive_cli.py monitor 100",
        "python pytractive_cli.py export -f my_data.csv",
        "python pytractive_cli.py battery -d",
        "python pytractive_cli.py history --hours 12"
    ]
    
    for example in examples:
        click.echo(f"  {click.style(example, fg='yellow')}")
    
    click.echo("\n⚙️  Configuration:")
    click.echo("  Set environment variables:")
    click.echo("    TRACTIVE_EMAIL=your.email@example.com")
    click.echo("    TRACTIVE_PASSWORD=your_password")
    click.echo("    TRACTIVE_HOME_LAT=40.7128")
    click.echo("    TRACTIVE_HOME_LON=-74.0060")
    click.echo("    IFTTT_KEY=your_ifttt_webhook_key")
    
    click.echo("\n🚀 Features:")
    features = [
        "Real-time GPS tracking with fallback mechanisms",
        "Interactive maps with Folium integration", 
        "Battery monitoring with health alerts",
        "Location history with distance/speed analytics",
        "CSV data export with comprehensive analytics",
        "Remote device control (LED, buzzer, live tracking)",
        "Direct Bluetooth BLE communication (Linux)",
        "Tkinter GUI interface",
        "IFTTT webhook notifications and triggers",
        "Public location sharing",
        "Home geofencing and monitoring",
        "Response caching for performance",
        "Comprehensive error handling"
    ]
    
    for feature in features:
        click.echo(f"  ✅ {feature}")
    
    click.echo("\n🔄 Compatibility:")
    click.echo("  You can still use the original interface:")
    click.echo("    python3 -m PyTractive.main --led on")
    click.echo("    python3 -m PyTractive.main --gps -I")
    click.echo("    python3 -m PyTractive.main --export")
    
    click.echo("=" * 80)
    click.echo("🎯 Try running: python pytractive_cli.py --help")


@cli.command()
@click.argument('threshold', type=int)
@click.pass_context
@handle_exceptions
def monitor(ctx, threshold: int):
    """Monitor pet distance and send notifications when close to home."""
    client: TractiveClient = ctx.obj['client']
    
    click.echo(f"🔍 Monitoring pet location (threshold: {threshold}m)")
    click.echo("Press Ctrl+C to stop monitoring")
    
    try:
        last_distance = float('inf')
        
        while True:
            try:
                # Get current location and status
                location = client.get_gps_location()
                device_status = client.get_device_status(partial=True)
                
                # Calculate distance from home
                distance = int(geodesic(client.home_coordinates, location.coordinates).m)
                
                # Check battery level
                if device_status.is_low_battery:
                    click.echo(click.style(f"⚠️  Low battery: {device_status.battery_level}%", fg='red'))
                
                # Check if getting closer
                if distance < last_distance:
                    click.echo(f"📍 Getting closer... ({distance}m from home)")
                    last_distance = distance
                
                # Check if within threshold
                if distance <= threshold:
                    click.echo(click.style(f"🏠 Pet is home! ({distance}m)", fg='green', bold=True))
                    break
                
                # Wait before next check
                time.sleep(10)
                
            except KeyboardInterrupt:
                click.echo("\n👋 Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                click.echo(f"Error during monitoring: {e}", err=True)
                time.sleep(5)  # Wait a bit before retrying
                
    except KeyboardInterrupt:
        click.echo("\n👋 Monitoring stopped by user")


@cli.command()
@click.pass_context
@handle_exceptions
def live_location(ctx):
    """Get live location by temporarily enabling live tracking."""
    client: TractiveClient = ctx.obj['client']
    
    click.echo("📡 Getting live location...")
    
    # Store current timestamps
    initial_gps = client.get_gps_location()
    initial_status = client.get_device_status(partial=True)
    
    # Enable live tracking
    client.send_command(CommandType.LIVE_TRACKING, CommandState.ON)
    click.echo("Live tracking enabled, waiting for network connection...")
    
    try:
        # Wait for network update
        current_status = initial_status
        while current_status.timestamp <= initial_status.timestamp:
            time.sleep(2)
            current_status = client.get_device_status(partial=True)
        
        click.echo("✓ Network connection established!")
        click.echo("Waiting for GPS update...")
        
        # Wait for GPS update
        current_gps = initial_gps
        while current_gps.timestamp <= initial_gps.timestamp:
            time.sleep(2)
            current_gps = client.get_gps_location()
        
        click.echo("✓ Live GPS location received!")
        
        # Display updated location
        ctx.invoke(location, interactive=False)
        
    finally:
        # Always disable live tracking
        time.sleep(6)  # Give some time for GPS to update
        client.send_command(CommandType.LIVE_TRACKING, CommandState.OFF)
        click.echo("Live tracking disabled")


if __name__ == '__main__':
    cli()
