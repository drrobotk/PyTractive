"""
Web-based GUI interface for PyTractive using a simple HTTP server.
"""

import http.server
import socketserver
import webbrowser
import threading
import json
import logging
from urllib.parse import parse_qs, urlparse
from typing import Optional
import time

from .client import TractiveClient
from .models import CommandType, CommandState
from .exceptions import TractiveError


logger = logging.getLogger(__name__)


class PyTractiveWebHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler for PyTractive web interface."""
    
    def __init__(self, *args, client=None, **kwargs):
        self.client = client
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/':
            self.send_html_interface()
        elif parsed_path.path == '/api/status':
            self.send_json_response(self.get_status())
        elif parsed_path.path == '/api/location':
            self.send_json_response(self.get_location())
        elif parsed_path.path == '/api/pet':
            self.send_json_response(self.get_pet_info())
        elif parsed_path.path == '/api/stats':
            self.send_json_response(self.get_stats())
        elif parsed_path.path == '/api/battery':
            self.send_json_response(self.get_battery())
        elif parsed_path.path == '/api/home_status':
            self.send_json_response(self.get_home_status())
        elif parsed_path.path == '/api/live_location':
            self.send_json_response(self.get_live_location())
        elif parsed_path.path == '/api/history':
            hours = int(parse_qs(parsed_path.query).get('hours', ['24'])[0])
            self.send_json_response(self.get_history(hours))
        elif parsed_path.path == '/api/export':
            self.send_csv_export()
        elif parsed_path.path == '/api/map':
            self.send_map_html()
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/command':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            self.send_json_response(self.send_command(data))
        else:
            self.send_error(404)
    
    def send_html_interface(self):
        """Send the HTML interface."""
        html = self.get_html_interface()
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def send_json_response(self, data):
        """Send JSON response."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def get_status(self):
        """Get device status."""
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
            
            status = self.client.get_device_status()
            return {
                'success': True,
                'battery_level': status.battery_level,
                'battery_state': status.battery_state.value,
                'gps_state': status.state.value if status.state else 'Unknown',
                'last_update': status.datetime.isoformat(),
                'online': status.is_online
            }
        except Exception as e:
            logger.error(f"Status error: {e}")
            return {'error': str(e)}
    
    def get_location(self):
        """Get GPS location."""
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
                
            location = self.client.get_gps_location()
            distance_home = self.client.get_distance_from_home(location)
            
            return {
                'success': True,
                'coordinates': location.coordinates,
                'accuracy': f"{location.uncertainty}% uncertainty" if location.uncertainty else "N/A",
                'last_update': location.datetime.isoformat(),
                'altitude': location.altitude,
                'speed': location.speed,
                'distance_from_home': round(distance_home),
                'at_home': distance_home <= 50
            }
        except Exception as e:
            logger.error(f"Location error: {e}")
            return {'error': str(e)}
    
    def get_pet_info(self):
        """Get pet information."""
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
                
            pet = self.client.get_pet_data()
            return {
                'success': True,
                'name': pet.name,
                'type': pet.pet_type,
                'breed': pet.breed,
                'gender': pet.gender,
                'age': pet.age_description,
                'neutered': pet.neutered,
                'chip_id': pet.chip_id,
                'picture_url': pet.profile_picture_url
            }
        except Exception as e:
            logger.error(f"Pet info error: {e}")
            return {'error': str(e)}
    
    def get_stats(self):
        """Get session statistics."""
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
                
            stats = self.client.stats
            return {
                'success': True,
                'session_runtime': f"{stats['session_runtime_seconds']:.1f}s",
                'requests_made': stats['requests_made'],
                'cache_hit_rate': f"{stats['cache_hit_rate']*100:.1f}%",
                'errors': stats['errors_encountered']
            }
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {'error': str(e)}
    
    def send_command(self, data):
        """Send command to tracker."""
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
                
            command = CommandType(data['command'])
            state = CommandState(data['state'])
            
            self.client.send_command(command, state)
            return {'success': True, 'message': f'{command.value} {state.value} sent'}
        except Exception as e:
            logger.error(f"Command error: {e}")
            return {'error': str(e)}
    
    def get_battery(self):
        """Get battery status."""
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
            
            status = self.client.get_device_status()
            return {
                'success': True,
                'battery_level': status.battery_level,
                'battery_state': status.battery_state.value,
                'battery_saver': status.battery_save_mode,
                'temperature_state': status.temperature_state.value,
                'last_update': status.datetime.isoformat()
            }
        except Exception as e:
            logger.error(f"Battery error: {e}")
            return {'error': str(e)}
    
    def get_home_status(self):
        """Get home status."""
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
            
            location = self.client.get_gps_location()
            distance = self.client.get_distance_from_home(location)
            is_home = distance <= 50
            
            return {
                'success': True,
                'is_home': is_home,
                'distance': round(distance),
                'coordinates': location.coordinates
            }
        except Exception as e:
            logger.error(f"Home status error: {e}")
            return {'error': str(e)}
    
    def get_live_location(self):
        """Get live location by enabling live tracking temporarily."""
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
            
            # Enable live tracking temporarily
            self.client.send_command(CommandType.LIVE_TRACKING, CommandState.ON)
            time.sleep(3)  # Wait for GPS update
            
            # Get updated location
            location = self.client.get_gps_location()
            
            # Disable live tracking
            self.client.send_command(CommandType.LIVE_TRACKING, CommandState.OFF)
            
            return {
                'success': True,
                'coordinates': location.coordinates,
                'last_update': location.datetime.isoformat(),
                'message': 'Live location updated'
            }
        except Exception as e:
            logger.error(f"Live location error: {e}")
            return {'error': str(e)}
    
    def get_history(self, hours):
        """Get location history."""
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
            
            history = self.client.get_location_history(hours, include_analytics=True)
            
            # Handle empty location history
            if history.location_count == 0:
                return {
                    'success': True,
                    'location_count': 0,
                    'total_distance': 0,
                    'max_speed': 0,
                    'average_speed': 0,
                    'time_span_hours': 0,
                    'message': f'No location history found for the past {hours} hours',
                    'empty_history': True
                }
            
            return {
                'success': True,
                'location_count': history.location_count,
                'total_distance': round(history.total_distance),
                'max_speed': round(history.max_speed, 1),
                'average_speed': round(history.average_speed, 1),
                'time_span_hours': round(history.time_span_hours, 1),
                'start_location': {
                    'coordinates': history.start_location.coordinates,
                    'datetime': history.start_location.datetime.isoformat()
                },
                'end_location': {
                    'coordinates': history.end_location.coordinates,
                    'datetime': history.end_location.datetime.isoformat()
                },
                'empty_history': False
            }
        except Exception as e:
            logger.error(f"History error: {e}")
            return {'error': str(e)}
    
    def send_csv_export(self):
        """Send CSV file for download."""
        try:
            if not self.client:
                self.send_error(500, "Client not initialized")
                return
            
            # Export GPS data to DataFrame
            df = self.client.export_gps_data("temp_export.csv", include_analytics=True)
            
            # Generate CSV content
            csv_content = df.to_csv(index=False)
            
            # Send CSV file
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv')
            self.send_header('Content-Disposition', 'attachment; filename="pytractive_export.csv"')
            self.end_headers()
            self.wfile.write(csv_content.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Export error: {e}")
            self.send_error(500, f"Export failed: {e}")
    
    def send_map_html(self):
        """Generate and send interactive map HTML."""
        try:
            if not self.client:
                self.send_error(500, "Client not initialized")
                return
            
            # Get current location and status
            location = self.client.get_gps_location()
            status = self.client.get_device_status()
            distance_home = self.client.get_distance_from_home(location)
            home_coords = self.client.home_coordinates
            
            # Calculate time ago
            import datetime
            now = datetime.datetime.now()
            location_time = location.datetime
            time_diff = now - location_time
            
            if time_diff.total_seconds() < 60:
                time_ago = f"{int(time_diff.total_seconds())} seconds ago"
            elif time_diff.total_seconds() < 3600:
                time_ago = f"{int(time_diff.total_seconds() / 60)} minutes ago"
            else:
                time_ago = f"{int(time_diff.total_seconds() / 3600)} hours ago"
            
            # Generate map HTML
            map_html = self._generate_map_html(
                pet_coords=location.coordinates,
                home_coords=home_coords,
                battery_level=status.battery_level,
                distance=distance_home,
                time_ago=time_ago
            )
            
            # Send HTML response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(map_html.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Map generation error: {e}")
            self.send_error(500, f"Map generation failed: {e}")
    
    def _generate_map_html(self, pet_coords, home_coords, battery_level, distance, time_ago):
        """Generate interactive map HTML with pet and home locations."""
        pet_lat, pet_lon = pet_coords
        home_lat, home_lon = home_coords
        
        # Calculate center point between pet and home
        center_lat = (pet_lat + home_lat) / 2
        center_lon = (pet_lon + home_lon) / 2
        
        # Determine zoom level based on distance
        if distance < 100:
            zoom_level = 18
        elif distance < 500:
            zoom_level = 16
        elif distance < 2000:
            zoom_level = 14
        else:
            zoom_level = 12
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>PyTractive Pet Location Map</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/Leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.css"/>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.2.0/css/all.min.css"/>
    
    <style>
        html, body {{ width: 100%; height: 100%; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        #map {{ position: absolute; top: 0; bottom: 0; right: 0; left: 0; }}
        .map-controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.9);
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }}
        .control-button {{
            display: block;
            margin: 5px 0;
            padding: 8px 12px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        .control-button:hover {{ background: #0056b3; }}
        .info-panel {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            min-width: 200px;
        }}
        .info-panel h3 {{ margin: 0 0 10px 0; color: #333; }}
        .info-panel div {{ margin: 5px 0; font-size: 14px; }}
        .battery-bar {{
            width: 100%;
            height: 20px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            margin: 5px 0;
        }}
        .battery-fill {{
            height: 100%;
            background: {('linear-gradient(90deg, #28a745, #20c997)' if battery_level > 50 else 'linear-gradient(90deg, #ffc107, #fd7e14)' if battery_level > 20 else 'linear-gradient(90deg, #dc3545, #c82333)')};
            width: {battery_level}%;
            transition: width 0.3s ease;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="map-controls">
        <button class="control-button" onclick="goHome()">🏠 Home</button>
        <button class="control-button" onclick="goPet()">🐕 Pet</button>
        <button class="control-button" onclick="fitBounds()">🔍 Fit All</button>
        <button class="control-button" onclick="window.close()">❌ Close</button>
    </div>
    
    <div class="info-panel">
        <h3>📍 Pet Location Info</h3>
        <div><strong>🔋 Battery:</strong> {battery_level}%</div>
        <div class="battery-bar"><div class="battery-fill"></div></div>
        <div><strong>🏠 Distance from Home:</strong> {distance:.1f}m</div>
        <div><strong>📅 Last Update:</strong> {time_ago}</div>
        <div><strong>📍 Coordinates:</strong><br>{pet_lat:.6f}, {pet_lon:.6f}</div>
    </div>

    <!-- Leaflet JS -->
    <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Leaflet.awesome-markers/2.0.2/leaflet.awesome-markers.js"></script>

    <script>
        // Initialize map
        var map = L.map('map').setView([{center_lat}, {center_lon}], {zoom_level});
        
        // Add tile layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        }}).addTo(map);
        
        // Add scale control
        L.control.scale().addTo(map);
        
        // Pet location marker (red paw)
        var petIcon = L.AwesomeMarkers.icon({{
            icon: 'paw',
            markerColor: 'red',
            prefix: 'fa',
            iconColor: 'white'
        }});
        
        var petMarker = L.marker([{pet_lat}, {pet_lon}], {{icon: petIcon}}).addTo(map);
        petMarker.bindPopup(`
            <div style="text-align: center; padding: 5px;">
                <h4>🐕 Pet Location</h4>
                <p><strong>Battery:</strong> {battery_level}%</p>
                <p><strong>Last seen:</strong> {time_ago}</p>
                <p><strong>Coordinates:</strong><br>{pet_lat:.6f}, {pet_lon:.6f}</p>
            </div>
        `);
        
        // Home location marker (green house)
        var homeIcon = L.AwesomeMarkers.icon({{
            icon: 'home',
            markerColor: 'green',
            prefix: 'fa',
            iconColor: 'white'
        }});
        
        var homeMarker = L.marker([{home_lat}, {home_lon}], {{icon: homeIcon}}).addTo(map);
        homeMarker.bindPopup(`
            <div style="text-align: center; padding: 5px;">
                <h4>🏠 Home</h4>
                <p><strong>Coordinates:</strong><br>{home_lat:.6f}, {home_lon:.6f}</p>
            </div>
        `);
        
        // Connection line
        var connectionLine = L.polyline([
            [{pet_lat}, {pet_lon}],
            [{home_lat}, {home_lon}]
        ], {{
            color: 'darkred',
            weight: 3,
            opacity: 0.8,
            dashArray: '10, 5'
        }}).addTo(map);
        
        connectionLine.bindPopup(`
            <div style="text-align: center; padding: 5px;">
                <h4>📏 Distance</h4>
                <p><strong>{distance:.1f} meters</strong></p>
                <p>from home</p>
            </div>
        `);
        
        // Control functions
        function goHome() {{
            map.setView([{home_lat}, {home_lon}], 18);
            homeMarker.openPopup();
        }}
        
        function goPet() {{
            map.setView([{pet_lat}, {pet_lon}], 18);
            petMarker.openPopup();
        }}
        
        function fitBounds() {{
            var group = new L.featureGroup([petMarker, homeMarker]);
            map.fitBounds(group.getBounds().pad(0.1));
        }}
        
        // Auto-refresh every 30 seconds
        setInterval(function() {{
            location.reload();
        }}, 30000);
        
        // Show pet popup on load
        setTimeout(function() {{
            petMarker.openPopup();
        }}, 1000);
    </script>
</body>
</html>"""
    
    def create_share(self, data):
        """Create a public share link."""
        try:
            if not self.client:
                return {'error': 'Client not initialized'}
            
            message = data.get('message', 'Pet location sharing')
            
            # For now, return a mock share since the actual API endpoint might not be available
            # In a real implementation, you'd call self.client.create_public_share(message)
            
            import uuid
            import time
            
            share_id = str(uuid.uuid4())[:8]
            share_link = f"https://tractive.com/share/{share_id}"
            
            return {
                'success': True,
                'share_id': share_id,
                'share_link': share_link,
                'message': message,
                'created_at': int(time.time()),
                'note': 'This is a demo share - in production this would create a real Tractive share link'
            }
        except Exception as e:
            logger.error(f"Share creation error: {e}")
            return {'error': str(e)}
    
    def get_html_interface(self):
        """Generate HTML interface."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>PyTractive Web Interface</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.5rem; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .header p { font-size: 1.2rem; opacity: 0.9; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
        .card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); transition: transform 0.2s; }
        .card:hover { transform: translateY(-4px); }
        .card h3 { margin: 0 0 20px 0; color: #333; font-size: 1.4rem; display: flex; align-items: center; gap: 10px; }
        .button { background: linear-gradient(45deg, #007bff, #0056b3); color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; margin: 6px; font-weight: 500; transition: all 0.2s; font-size: 14px; }
        .button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,123,255,0.4); }
        .button.danger { background: linear-gradient(45deg, #dc3545, #c82333); }
        .button.danger:hover { box-shadow: 0 4px 12px rgba(220,53,69,0.4); }
        .button.success { background: linear-gradient(45deg, #28a745, #1e7e34); }
        .button.success:hover { box-shadow: 0 4px 12px rgba(40,167,69,0.4); }
        .button.warning { background: linear-gradient(45deg, #ffc107, #e0a800); }
        .button.warning:hover { box-shadow: 0 4px 12px rgba(255,193,7,0.4); }
        .button:disabled { background: #6c757d; cursor: not-allowed; transform: none; }
        .status { padding: 15px; border-radius: 8px; margin: 15px 0; font-weight: 500; }
        .success { background: #d4edda; color: #155724; border-left: 4px solid #28a745; }
        .error { background: #f8d7da; color: #721c24; border-left: 4px solid #dc3545; }
        .info { background: #d1ecf1; color: #0c5460; border-left: 4px solid #17a2b8; }
        .data-display { background: #f8f9fa; padding: 20px; border-radius: 8px; font-family: 'SF Mono', Monaco, monospace; font-size: 14px; line-height: 1.6; border: 1px solid #e9ecef; }
        .loading { color: #666; font-style: italic; text-align: center; padding: 40px; }
        .pet-image { max-width: 200px; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin: 15px 0; }
        .control-group { display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0; }
        .battery-bar { font-family: monospace; font-size: 16px; margin: 10px 0; }
        .coordinates { background: #e9ecef; padding: 10px; border-radius: 6px; font-family: monospace; margin: 10px 0; }
        .alert { padding: 15px; border-radius: 8px; margin: 15px 0; font-weight: 500; }
        .alert.warning { background: #fff3cd; color: #856404; border-left: 4px solid #ffc107; }
        .alert.danger { background: #f8d7da; color: #721c24; border-left: 4px solid #dc3545; }
        .full-width { grid-column: 1 / -1; }
        .two-column { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 768px) { .two-column { grid-template-columns: 1fr; } .control-group { justify-content: center; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐕 PyTractive Control Center</h1>
            <p>Advanced GPS Tracker Management</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>📊 Device Status</h3>
                <button class="button" onclick="getStatus()">🔄 Refresh Status</button>
                <button class="button success" onclick="getLiveLocation()">📡 Live GPS</button>
                <div id="status-display" class="data-display">Click "Refresh Status" to load device information</div>
            </div>
            
            <div class="card">
                <h3>📍 GPS Location</h3>
                <button class="button" onclick="getLocation()">📍 Get Location</button>
                <button class="button" onclick="getHomeStatus()">🏠 Home Status</button>
                <button class="button success" onclick="openMap()">🗺️ View Map</button>
                <div id="location-display" class="data-display">Click "Get Location" to load GPS information</div>
            </div>
            
            <div class="card">
                <h3>🐕 Pet Information</h3>
                <button class="button" onclick="getPetInfo()">🐾 Load Pet Info</button>
                <div id="pet-display" class="data-display">Click "Load Pet Info" to view pet details</div>
            </div>
            
            <div class="card">
                <h3>🎮 Device Control</h3>
                <div class="control-group">
                    <button class="button warning" onclick="sendCommand('led_control', 'on')">💡 LED On</button>
                    <button class="button" onclick="sendCommand('led_control', 'off')">💡 LED Off</button>
                </div>
                <div class="control-group">
                    <button class="button warning" onclick="sendCommand('buzzer_control', 'on')">🔊 Buzzer On</button>
                    <button class="button" onclick="sendCommand('buzzer_control', 'off')">🔇 Buzzer Off</button>
                </div>
                <div class="control-group">
                    <button class="button success" onclick="sendCommand('live_tracking', 'on')">🎯 Live On</button>
                    <button class="button" onclick="sendCommand('live_tracking', 'off')">⏹️ Live Off</button>
                </div>
                <div class="control-group">
                    <button class="button success" onclick="sendCommand('battery_saver', 'on')">🔋 Save On</button>
                    <button class="button" onclick="sendCommand('battery_saver', 'off')">🔋 Save Off</button>
                </div>
                <div id="command-status" class="status" style="display:none;"></div>
            </div>
            
            <div class="card">
                <h3>📈 Analytics & History</h3>
                <button class="button" onclick="getStats()">📊 Session Stats</button>
                <button class="button" onclick="getHistory()">📍 Location History</button>
                <button class="button" onclick="getBattery()">🔋 Battery Health</button>
                <div id="stats-display" class="data-display">Click buttons above to view analytics</div>
            </div>
            
            <div class="card">
                <h3>🔗 Sharing & Export</h3>
                <button class="button" onclick="createShare()">🔗 Create Share</button>
                <button class="button" onclick="exportData()">📥 Export Data</button>
                <div id="share-display" class="data-display">Share and export functionality</div>
            </div>
        </div>
    </div>

    <script>
        let autoRefresh = null;
        
        function showStatus(message, type = 'info') {
            const status = document.getElementById('command-status');
            status.className = `status ${type}`;
            status.textContent = message;
            status.style.display = 'block';
            setTimeout(() => status.style.display = 'none', 4000);
        }
        
        function showLoading(elementId) {
            document.getElementById(elementId).innerHTML = '<div class="loading">⏳ Loading...</div>';
        }
        
        async function getStatus() {
            showLoading('status-display');
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('status-display').innerHTML = `<div class="alert danger">❌ Error: ${data.error}</div>`;
                } else {
                    const batteryBar = '█'.repeat(Math.floor(data.battery_level / 5)) + '░'.repeat(20 - Math.floor(data.battery_level / 5));
                    const batteryColor = data.battery_level > 50 ? '#28a745' : data.battery_level > 20 ? '#ffc107' : '#dc3545';
                    
                    let alerts = '';
                    if (data.battery_level < 30) alerts += '<div class="alert warning">⚠️ Low battery warning!</div>';
                    if (!data.online) alerts += '<div class="alert danger">🔴 Device is offline</div>';
                    
                    document.getElementById('status-display').innerHTML = `
                        ${alerts}
                        <div class="two-column">
                            <div>
                                <strong>🔋 Battery:</strong> ${data.battery_level}% (${data.battery_state})<br>
                                <div class="battery-bar" style="color: ${batteryColor}">[${batteryBar}]</div>
                                <strong>📡 GPS State:</strong> ${data.gps_state}<br>
                                <strong>🌐 Online:</strong> ${data.online ? '🟢 Yes' : '🔴 No'}
                            </div>
                            <div>
                                <strong>📅 Last Update:</strong><br>
                                ${new Date(data.last_update).toLocaleString()}<br>
                                <strong>🏷️ Tracker ID:</strong> ${data.tracker_id || 'N/A'}
                            </div>
                        </div>
                    `;
                }
            } catch (error) {
                document.getElementById('status-display').innerHTML = `<div class="alert danger">🚫 Network error: ${error.message}</div>`;
            }
        }
        
        async function getLocation() {
            showLoading('location-display');
            try {
                const response = await fetch('/api/location');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('location-display').innerHTML = `<div class="alert danger">❌ Error: ${data.error}</div>`;
                } else {
                    const homeStatus = data.at_home ? 
                        '<div class="alert success">🏠 Pet is at home!</div>' : 
                        '<div class="alert warning">📍 Pet is away from home</div>';
                    
                    document.getElementById('location-display').innerHTML = `
                        ${homeStatus}
                        <div class="coordinates">
                            📍 ${data.coordinates[0].toFixed(6)}, ${data.coordinates[1].toFixed(6)}
                        </div>
                        <div class="two-column">
                            <div>
                                <strong>🎯 Accuracy:</strong> ${data.accuracy}<br>
                                <strong>⛰️ Altitude:</strong> ${data.altitude}m<br>
                                <strong>🏃 Speed:</strong> ${data.speed} km/h
                            </div>
                            <div>
                                <strong>🏠 Distance Home:</strong> ${data.distance_from_home}m<br>
                                <strong>📅 Last Update:</strong><br>
                                ${new Date(data.last_update).toLocaleString()}
                            </div>
                        </div>
                    `;
                }
            } catch (error) {
                document.getElementById('location-display').innerHTML = `<div class="alert danger">🚫 Network error: ${error.message}</div>`;
            }
        }
        
        async function getPetInfo() {
            showLoading('pet-display');
            try {
                const response = await fetch('/api/pet');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('pet-display').innerHTML = `<div class="alert danger">❌ Error: ${data.error}</div>`;
                } else {
                    let imageHtml = '';
                    if (data.picture_url) {
                        imageHtml = `<img src="${data.picture_url}" alt="${data.name}" class="pet-image" onerror="this.style.display='none'">`;
                    }
                    
                    document.getElementById('pet-display').innerHTML = `
                        <div style="text-align: center;">${imageHtml}</div>
                        <div class="two-column">
                            <div>
                                <strong>🐕 Name:</strong> ${data.name}<br>
                                <strong>🔖 Type:</strong> ${data.type}<br>
                                <strong>🧬 Breed:</strong> ${data.breed}
                            </div>
                            <div>
                                <strong>⚧ Gender:</strong> ${data.gender}<br>
                                <strong>🎂 Age:</strong> ${data.age}<br>
                                <strong>✂️ Neutered:</strong> ${data.neutered ? 'Yes' : 'No'}
                            </div>
                        </div>
                        ${data.chip_id ? `<div style="margin-top: 15px;"><strong>🔢 Chip ID:</strong> ${data.chip_id}</div>` : ''}
                    `;
                }
            } catch (error) {
                document.getElementById('pet-display').innerHTML = `<div class="alert danger">🚫 Network error: ${error.message}</div>`;
            }
        }
        
        async function getStats() {
            showLoading('stats-display');
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('stats-display').innerHTML = `<div class="alert danger">❌ Error: ${data.error}</div>`;
                } else {
                    document.getElementById('stats-display').innerHTML = `
                        <div class="two-column">
                            <div>
                                <strong>⏱️ Session Runtime:</strong> ${data.session_runtime}<br>
                                <strong>📊 API Requests:</strong> ${data.requests_made}<br>
                            </div>
                            <div>
                                <strong>⚡ Cache Hit Rate:</strong> ${data.cache_hit_rate}<br>
                                <strong>❌ Errors:</strong> ${data.errors}
                            </div>
                        </div>
                    `;
                }
            } catch (error) {
                document.getElementById('stats-display').innerHTML = `<div class="alert danger">🚫 Network error: ${error.message}</div>`;
            }
        }
        
        async function sendCommand(command, state) {
            try {
                showStatus(`Sending ${command} ${state}...`, 'info');
                
                const response = await fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command, state })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`❌ Command failed: ${data.error}`, 'error');
                } else {
                    showStatus(`✅ ${data.message}`, 'success');
                }
            } catch (error) {
                showStatus(`🚫 Network error: ${error.message}`, 'error');
            }
        }
        
        async function getHomeStatus() {
            try {
                const response = await fetch('/api/home_status');
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`❌ ${data.error}`, 'error');
                } else {
                    const message = data.is_home ? 
                        `🏠 Pet is at home (${data.distance}m away)` : 
                        `📍 Pet is away from home (${data.distance}m away)`;
                    showStatus(message, data.is_home ? 'success' : 'info');
                }
            } catch (error) {
                showStatus(`🚫 Network error: ${error.message}`, 'error');
            }
        }
        
        async function getLiveLocation() {
            try {
                showStatus('🎯 Getting live location...', 'info');
                const response = await fetch('/api/live_location');
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`❌ ${data.error}`, 'error');
                } else {
                    showStatus('✅ Live location updated!', 'success');
                    getLocation(); // Refresh location display
                }
            } catch (error) {
                showStatus(`🚫 Network error: ${error.message}`, 'error');
            }
        }
        
        async function getBattery() {
            showLoading('stats-display');
            try {
                const response = await fetch('/api/battery');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('stats-display').innerHTML = `<div class="alert danger">❌ Error: ${data.error}</div>`;
                } else {
                    let healthAlert = '';
                    if (data.battery_level < 20) healthAlert = '<div class="alert danger">🚨 Critical battery level!</div>';
                    else if (data.battery_level < 30) healthAlert = '<div class="alert warning">⚠️ Low battery warning!</div>';
                    
                    document.getElementById('stats-display').innerHTML = `
                        ${healthAlert}
                        <div class="two-column">
                            <div>
                                <strong>🔋 Level:</strong> ${data.battery_level}%<br>
                                <strong>⚡ State:</strong> ${data.battery_state}<br>
                                <strong>💾 Saver Mode:</strong> ${data.battery_saver ? 'On' : 'Off'}
                            </div>
                            <div>
                                <strong>🌡️ Temperature:</strong> ${data.temperature_state}<br>
                                <strong>📅 Last Update:</strong><br>
                                ${new Date(data.last_update).toLocaleString()}
                            </div>
                        </div>
                    `;
                }
            } catch (error) {
                document.getElementById('stats-display').innerHTML = `<div class="alert danger">🚫 Network error: ${error.message}</div>`;
            }
        }
        
        function toggleAutoRefresh() {
            if (autoRefresh) {
                clearInterval(autoRefresh);
                autoRefresh = null;
                showStatus('Auto refresh disabled', 'info');
            } else {
                autoRefresh = setInterval(() => {
                    getStatus();
                    getLocation();
                }, 30000); // Refresh every 30 seconds
                showStatus('Auto refresh enabled (30s)', 'success');
            }
        }
        
        function openMap() {
            // Open the map in a new window
            const mapWindow = window.open('/api/map', 'PetLocationMap', 'width=1000,height=700,scrollbars=yes,resizable=yes');
            if (mapWindow) {
                showStatus('🗺️ Map opened in new window', 'success');
            } else {
                showStatus('❌ Could not open map - check popup blocker', 'error');
            }
        }
        
        async function getHistory() {
            showLoading('stats-display');
            try {
                const response = await fetch('/api/history?hours=24');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('stats-display').innerHTML = `<div class="alert danger">❌ Error: ${data.error}</div>`;
                } else if (data.empty_history) {
                    document.getElementById('stats-display').innerHTML = `
                        <div class="alert info">📍 Location History (24 hours)</div>
                        <div class="alert warning">
                            📭 ${data.message || 'No location history found for the selected time period.'}
                        </div>
                        <div style="text-align: center; padding: 20px; color: #666;">
                            <p>This could mean:</p>
                            <ul style="text-align: left; display: inline-block;">
                                <li>🔋 The tracker was in power saving mode</li>
                                <li>📡 No GPS signal was available</li>
                                <li>🏠 The pet hasn't moved much recently</li>
                                <li>⏰ Try checking a different time period</li>
                            </ul>
                        </div>
                    `;
                } else {
                    document.getElementById('stats-display').innerHTML = `
                        <div class="alert info">📍 Location History (24 hours)</div>
                        <div class="two-column">
                            <div>
                                <strong>📊 GPS Points:</strong> ${data.location_count}<br>
                                <strong>📏 Total Distance:</strong> ${data.total_distance}m<br>
                                <strong>⏱️ Time Span:</strong> ${data.time_span_hours}h
                            </div>
                            <div>
                                <strong>🚀 Max Speed:</strong> ${data.max_speed} km/h<br>
                                <strong>📈 Avg Speed:</strong> ${data.average_speed} km/h<br>
                            </div>
                        </div>
                        <div style="margin-top: 15px;">
                            <strong>📍 Start:</strong> ${data.start_location.coordinates[0].toFixed(4)}, ${data.start_location.coordinates[1].toFixed(4)}<br>
                            <strong>🏁 End:</strong> ${data.end_location.coordinates[0].toFixed(4)}, ${data.end_location.coordinates[1].toFixed(4)}
                        </div>
                    `;
                }
            } catch (error) {
                document.getElementById('stats-display').innerHTML = `<div class="alert danger">🚫 Network error: ${error.message}</div>`;
            }
        }
        
        async function createShare() {
            showLoading('share-display');
            try {
                const message = prompt('Enter a message for the share (optional):', 'Check out my pet\\'s location!') || 'Pet location sharing';
                
                const response = await fetch('/api/share', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('share-display').innerHTML = `<div class="alert danger">❌ Error: ${data.error}</div>`;
                } else {
                    document.getElementById('share-display').innerHTML = `
                        <div class="alert success">🔗 Share Created Successfully!</div>
                        <div>
                            <strong>Share ID:</strong> ${data.share_id}<br>
                            <strong>Message:</strong> ${data.message}<br>
                            <strong>Share Link:</strong> <a href="${data.share_link}" target="_blank">${data.share_link}</a><br>
                            <strong>Created:</strong> ${new Date(data.created_at * 1000).toLocaleString()}
                        </div>
                        ${data.note ? `<div class="alert info" style="margin-top: 10px;">${data.note}</div>` : ''}
                    `;
                }
            } catch (error) {
                document.getElementById('share-display').innerHTML = `<div class="alert danger">🚫 Network error: ${error.message}</div>`;
            }
        }
        
        async function exportData() {
            showLoading('share-display');
            try {
                showStatus('📥 Preparing export...', 'info');
                
                // Create a link to download the CSV
                const link = document.createElement('a');
                link.href = '/api/export';
                link.download = 'pytractive_export.csv';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                document.getElementById('share-display').innerHTML = `
                    <div class="alert success">📥 Export Started!</div>
                    <div>
                        Your GPS data export should download automatically as <strong>pytractive_export.csv</strong>.
                        <br><br>
                        The CSV file includes:
                        <ul>
                            <li>📍 GPS coordinates and timestamps</li>
                            <li>📊 Speed and distance analytics</li>
                            <li>🎯 Accuracy and altitude data</li>
                            <li>📈 Cumulative distance calculations</li>
                        </ul>
                    </div>
                `;
                
                showStatus('✅ Export download started!', 'success');
                
            } catch (error) {
                document.getElementById('share-display').innerHTML = `<div class="alert danger">🚫 Export failed: ${error.message}</div>`;
                showStatus(`❌ Export failed: ${error.message}`, 'error');
            }
        }
        
        // Auto-load status on page load
        window.onload = function() {
            getStatus();
            getPetInfo();
        };
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 'r': e.preventDefault(); getStatus(); break;
                    case 'l': e.preventDefault(); getLocation(); break;
                    case 'p': e.preventDefault(); getPetInfo(); break;
                }
            }
        });
    </script>
</body>
</html>
"""


def create_web_handler(client):
    """Create a web handler with the client."""
    def handler(*args, **kwargs):
        PyTractiveWebHandler(*args, client=client, **kwargs)
    return handler


def launch_web_gui(port=8080):
    """Launch the web-based GUI."""
    try:
        print("🌐 Starting PyTractive Web Interface...")
        
        # Initialize client
        client = TractiveClient()
        print(f"✓ Connected to tracker: {client.tracker_id}")
        
        # Create handler with client
        handler = create_web_handler(client)
        
        # Start HTTP server
        with socketserver.TCPServer(("", port), handler) as httpd:
            server_url = f"http://localhost:{port}"
            print(f"🌐 Web interface available at: {server_url}")
            print("🚀 Opening in browser...")
            
            # Open browser
            def open_browser():
                time.sleep(1)  # Give server time to start
                webbrowser.open(server_url)
            
            threading.Thread(target=open_browser, daemon=True).start()
            
            print("📱 Press Ctrl+C to stop the server")
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n👋 Web interface stopped by user")
    except Exception as e:
        print(f"❌ Failed to start web interface: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    launch_web_gui()
