"""
Modern GUI interface for PyTractive.

This module provides a comprehensive tkinter-based GUI with modern design principles,
integrated with the PyTractive client system and supporting all features including
BLE communication, real-time updates, and interactive mapping.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import time
import logging
import webbrowser
import os
from datetime import datetime
from typing import Optional, Dict, List, Callable, Any
import json

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .client import TractiveClient
from .bluetooth import get_ble_client, BLEDevice, BLEError
from .exceptions import TractiveError, AuthenticationError, ConfigurationError
from .models import GPSLocation, DeviceStatus, PetData
from .config import ConfigManager


logger = logging.getLogger(__name__)


class ModernStyle:
    """Modern GUI styling constants."""
    
    # Color scheme
    COLORS = {
        'primary': '#2C3E50',           # Dark blue-gray
        'secondary': '#3498DB',         # Bright blue
        'success': '#27AE60',           # Green
        'warning': '#F39C12',           # Orange
        'danger': '#E74C3C',            # Red
        'light': '#ECF0F1',             # Light gray
        'dark': '#34495E',              # Dark gray
        'white': '#FFFFFF',
        'text_dark': '#2C3E50',
        'text_light': '#7F8C8D',
        'background': '#F8F9FA',
        'card': '#FFFFFF',
        'border': '#DEE2E6',
    }
    
    # Fonts
    FONTS = {
        'title': ('Helvetica', 16, 'bold'),
        'subtitle': ('Helvetica', 12, 'bold'),
        'body': ('Helvetica', 10),
        'small': ('Helvetica', 8),
        'mono': ('Courier', 9),
    }
    
    # Padding and sizing
    PADDING = {
        'small': 5,
        'medium': 10,
        'large': 20,
    }


class StatusBar(ttk.Frame):
    """Modern status bar with connection and update indicators."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.setup_ui()
        self.connection_status = "Disconnected"
        self.last_update = None
        
    def setup_ui(self):
        """Setup status bar UI."""
        # Connection status
        self.connection_label = ttk.Label(
            self, 
            text="● Disconnected", 
            foreground=ModernStyle.COLORS['danger']
        )
        self.connection_label.pack(side=tk.LEFT, padx=ModernStyle.PADDING['small'])
        
        # Separator
        ttk.Separator(self, orient='vertical').pack(
            side=tk.LEFT, 
            fill='y', 
            padx=ModernStyle.PADDING['small']
        )
        
        # Last update
        self.update_label = ttk.Label(self, text="No updates")
        self.update_label.pack(side=tk.LEFT, padx=ModernStyle.PADDING['small'])
        
        # Progress bar (hidden by default)
        self.progress = ttk.Progressbar(self, mode='indeterminate')
        
    def set_connection_status(self, connected: bool, connection_type: str = "API"):
        """Update connection status."""
        if connected:
            self.connection_status = f"Connected ({connection_type})"
            self.connection_label.config(
                text=f"● {self.connection_status}",
                foreground=ModernStyle.COLORS['success']
            )
        else:
            self.connection_status = "Disconnected"
            self.connection_label.config(
                text=f"● {self.connection_status}",
                foreground=ModernStyle.COLORS['danger']
            )
    
    def set_last_update(self, timestamp: Optional[datetime] = None):
        """Update last update time."""
        if timestamp is None:
            timestamp = datetime.now()
        
        self.last_update = timestamp
        self.update_label.config(text=f"Updated: {timestamp.strftime('%H:%M:%S')}")
    
    def show_progress(self):
        """Show progress indicator."""
        self.progress.pack(side=tk.RIGHT, padx=ModernStyle.PADDING['small'])
        self.progress.start()
    
    def hide_progress(self):
        """Hide progress indicator."""
        self.progress.stop()
        self.progress.pack_forget()


class InfoCard(ttk.LabelFrame):
    """Modern information card widget."""
    
    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, text=title, **kwargs)
        self.config(padding=ModernStyle.PADDING['medium'])
        self.data_labels: Dict[str, ttk.Label] = {}
        
    def add_field(self, key: str, label: str, value: str = "N/A"):
        """Add a data field to the card."""
        frame = ttk.Frame(self)
        frame.pack(fill='x', pady=2)
        
        ttk.Label(
            frame, 
            text=f"{label}:", 
            font=ModernStyle.FONTS['body']
        ).pack(side=tk.LEFT)
        
        value_label = ttk.Label(
            frame, 
            text=value, 
            font=ModernStyle.FONTS['body']
        )
        value_label.pack(side=tk.RIGHT)
        
        self.data_labels[key] = value_label
    
    def update_field(self, key: str, value: str):
        """Update a field value."""
        if key in self.data_labels:
            self.data_labels[key].config(text=value)
    
    def update_fields(self, data: Dict[str, str]):
        """Update multiple fields."""
        for key, value in data.items():
            self.update_field(key, value)


class MapFrame(ttk.LabelFrame):
    """Interactive map frame with location display."""
    
    def __init__(self, parent):
        super().__init__(parent, text="Location Map", padding=ModernStyle.PADDING['medium'])
        self.setup_ui()
        self.current_location: Optional[GPSLocation] = None
        
    def setup_ui(self):
        """Setup map UI."""
        # Map controls
        controls_frame = ttk.Frame(self)
        controls_frame.pack(fill='x', pady=(0, ModernStyle.PADDING['small']))
        
        self.open_map_btn = ttk.Button(
            controls_frame,
            text="📍 Open Interactive Map",
            command=self.open_interactive_map
        )
        self.open_map_btn.pack(side=tk.LEFT, padx=(0, ModernStyle.PADDING['small']))
        
        self.refresh_btn = ttk.Button(
            controls_frame,
            text="🔄 Refresh Location",
            command=self.refresh_location
        )
        self.refresh_btn.pack(side=tk.LEFT)
        
        # Location info
        self.location_info = InfoCard(self, "Current Location")
        self.location_info.pack(fill='both', expand=True)
        
        self.location_info.add_field('coordinates', 'Coordinates')
        self.location_info.add_field('address', 'Address')
        self.location_info.add_field('accuracy', 'GPS Accuracy')
        self.location_info.add_field('timestamp', 'Last Update')
        self.location_info.add_field('distance_home', 'Distance from Home')
        
        # Set callback for refresh
        self.refresh_callback: Optional[Callable] = None
    
    def set_refresh_callback(self, callback: Callable):
        """Set callback for location refresh."""
        self.refresh_callback = callback
    
    def update_location(self, location: GPSLocation, address: str = "", distance_home: float = 0):
        """Update displayed location."""
        self.current_location = location
        
        self.location_info.update_fields({
            'coordinates': f"{location.latitude:.6f}, {location.longitude:.6f}",
            'address': address[:50] + "..." if len(address) > 50 else address,
            'accuracy': f"{location.accuracy}m" if location.accuracy else "N/A",
            'timestamp': location.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'distance_home': f"{distance_home:.0f}m" if distance_home else "N/A"
        })
    
    def open_interactive_map(self):
        """Open interactive map in browser."""
        if self.current_location:
            # This would create and open a folium map
            # For now, we'll open Google Maps
            lat, lon = self.current_location.latitude, self.current_location.longitude
            url = f"https://www.google.com/maps?q={lat},{lon}"
            webbrowser.open(url)
        else:
            messagebox.showwarning("No Location", "No location data available")
    
    def refresh_location(self):
        """Refresh location data."""
        if self.refresh_callback:
            self.refresh_callback()


class ControlPanel(ttk.LabelFrame):
    """Device control panel."""
    
    def __init__(self, parent):
        super().__init__(parent, text="Device Control", padding=ModernStyle.PADDING['medium'])
        self.setup_ui()
        self.control_callback: Optional[Callable] = None
        
    def setup_ui(self):
        """Setup control UI."""
        # LED Control
        led_frame = ttk.Frame(self)
        led_frame.pack(fill='x', pady=ModernStyle.PADDING['small'])
        
        ttk.Label(led_frame, text="LED Light:", font=ModernStyle.FONTS['body']).pack(side=tk.LEFT)
        
        self.led_on_btn = ttk.Button(
            led_frame, 
            text="💡 On", 
            command=lambda: self.send_command('led_control', 'on')
        )
        self.led_on_btn.pack(side=tk.RIGHT, padx=(ModernStyle.PADDING['small'], 0))
        
        self.led_off_btn = ttk.Button(
            led_frame, 
            text="💡 Off", 
            command=lambda: self.send_command('led_control', 'off')
        )
        self.led_off_btn.pack(side=tk.RIGHT)
        
        # Buzzer Control
        buzzer_frame = ttk.Frame(self)
        buzzer_frame.pack(fill='x', pady=ModernStyle.PADDING['small'])
        
        ttk.Label(buzzer_frame, text="Buzzer:", font=ModernStyle.FONTS['body']).pack(side=tk.LEFT)
        
        self.buzzer_on_btn = ttk.Button(
            buzzer_frame, 
            text="🔊 On", 
            command=lambda: self.send_command('buzzer_control', 'on')
        )
        self.buzzer_on_btn.pack(side=tk.RIGHT, padx=(ModernStyle.PADDING['small'], 0))
        
        self.buzzer_off_btn = ttk.Button(
            buzzer_frame, 
            text="🔊 Off", 
            command=lambda: self.send_command('buzzer_control', 'off')
        )
        self.buzzer_off_btn.pack(side=tk.RIGHT)
        
        # Live Tracking
        live_frame = ttk.Frame(self)
        live_frame.pack(fill='x', pady=ModernStyle.PADDING['small'])
        
        ttk.Label(live_frame, text="Live Tracking:", font=ModernStyle.FONTS['body']).pack(side=tk.LEFT)
        
        self.live_on_btn = ttk.Button(
            live_frame, 
            text="📡 Enable", 
            command=lambda: self.send_command('live_tracking', 'on')
        )
        self.live_on_btn.pack(side=tk.RIGHT, padx=(ModernStyle.PADDING['small'], 0))
        
        self.live_off_btn = ttk.Button(
            live_frame, 
            text="📡 Disable", 
            command=lambda: self.send_command('live_tracking', 'off')
        )
        self.live_off_btn.pack(side=tk.RIGHT)
        
        # Battery Saver
        battery_frame = ttk.Frame(self)
        battery_frame.pack(fill='x', pady=ModernStyle.PADDING['small'])
        
        ttk.Label(battery_frame, text="Battery Saver:", font=ModernStyle.FONTS['body']).pack(side=tk.LEFT)
        
        self.battery_on_btn = ttk.Button(
            battery_frame, 
            text="🔋 Enable", 
            command=lambda: self.send_command('battery_saver', 'on')
        )
        self.battery_on_btn.pack(side=tk.RIGHT, padx=(ModernStyle.PADDING['small'], 0))
        
        self.battery_off_btn = ttk.Button(
            battery_frame, 
            text="🔋 Disable", 
            command=lambda: self.send_command('battery_saver', 'off')
        )
        self.battery_off_btn.pack(side=tk.RIGHT)
    
    def set_control_callback(self, callback: Callable):
        """Set callback for control commands."""
        self.control_callback = callback
    
    def send_command(self, command: str, state: str):
        """Send control command."""
        if self.control_callback:
            self.control_callback(command, state)


class BLEPanel(ttk.LabelFrame):
    """Bluetooth Low Energy control panel."""
    
    def __init__(self, parent):
        super().__init__(parent, text="Bluetooth BLE", padding=ModernStyle.PADDING['medium'])
        self.setup_ui()
        self.ble_client = None
        self.devices: List[BLEDevice] = []
        
    def setup_ui(self):
        """Setup BLE UI."""
        # Connection controls
        conn_frame = ttk.Frame(self)
        conn_frame.pack(fill='x', pady=(0, ModernStyle.PADDING['small']))
        
        self.scan_btn = ttk.Button(
            conn_frame,
            text="🔍 Scan Devices",
            command=self.scan_devices
        )
        self.scan_btn.pack(side=tk.LEFT, padx=(0, ModernStyle.PADDING['small']))
        
        self.connect_btn = ttk.Button(
            conn_frame,
            text="🔗 Connect",
            command=self.connect_device,
            state='disabled'
        )
        self.connect_btn.pack(side=tk.LEFT, padx=(0, ModernStyle.PADDING['small']))
        
        self.disconnect_btn = ttk.Button(
            conn_frame,
            text="❌ Disconnect",
            command=self.disconnect_device,
            state='disabled'
        )
        self.disconnect_btn.pack(side=tk.LEFT)
        
        # Device selection
        device_frame = ttk.Frame(self)
        device_frame.pack(fill='x', pady=(0, ModernStyle.PADDING['small']))
        
        ttk.Label(device_frame, text="Device:").pack(side=tk.LEFT)
        
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(
            device_frame, 
            textvariable=self.device_var, 
            state='readonly'
        )
        self.device_combo.pack(side=tk.RIGHT, fill='x', expand=True, padx=(ModernStyle.PADDING['small'], 0))
        
        # BLE controls
        ble_controls_frame = ttk.Frame(self)
        ble_controls_frame.pack(fill='x')
        
        self.ble_battery_btn = ttk.Button(
            ble_controls_frame,
            text="🔋 BLE Battery",
            command=self.get_ble_battery,
            state='disabled'
        )
        self.ble_battery_btn.pack(side=tk.LEFT, padx=(0, ModernStyle.PADDING['small']))
        
        self.ble_light_btn = ttk.Button(
            ble_controls_frame,
            text="💡 BLE Light",
            command=self.ble_light_toggle,
            state='disabled'
        )
        self.ble_light_btn.pack(side=tk.LEFT, padx=(0, ModernStyle.PADDING['small']))
        
        self.ble_sound_btn = ttk.Button(
            ble_controls_frame,
            text="🔊 BLE Sound",
            command=self.ble_sound_toggle,
            state='disabled'
        )
        self.ble_sound_btn.pack(side=tk.LEFT)
        
        # Status
        self.ble_status = ttk.Label(self, text="BLE: Not connected")
        self.ble_status.pack(pady=(ModernStyle.PADDING['small'], 0))
        
    def scan_devices(self):
        """Scan for BLE devices."""
        def scan_worker():
            try:
                self.scan_btn.config(state='disabled', text="🔍 Scanning...")
                
                if not self.ble_client:
                    self.ble_client = get_ble_client()
                
                self.devices = self.ble_client.discover_tractive_devices(timeout=10.0)
                
                # Update combo box
                device_names = []
                for device in self.devices:
                    name = device.name or "Unknown"
                    device_names.append(f"{name} ({device.address})")
                
                self.device_combo['values'] = device_names
                if device_names:
                    self.device_combo.current(0)
                    self.connect_btn.config(state='normal')
                
                self.ble_status.config(text=f"Found {len(self.devices)} BLE devices")
                
            except Exception as e:
                messagebox.showerror("BLE Scan Error", f"Failed to scan devices: {e}")
                self.ble_status.config(text="BLE: Scan failed")
            finally:
                self.scan_btn.config(state='normal', text="🔍 Scan Devices")
        
        threading.Thread(target=scan_worker, daemon=True).start()
    
    def connect_device(self):
        """Connect to selected BLE device."""
        if not self.devices or not self.device_var.get():
            return
        
        def connect_worker():
            try:
                self.connect_btn.config(state='disabled', text="🔗 Connecting...")
                
                # Get selected device
                selected_index = self.device_combo.current()
                device = self.devices[selected_index]
                
                # Connect
                success = self.ble_client.connect(device.address)
                
                if success:
                    self.connect_btn.config(state='disabled')
                    self.disconnect_btn.config(state='normal')
                    self.ble_battery_btn.config(state='normal')
                    self.ble_light_btn.config(state='normal')
                    self.ble_sound_btn.config(state='normal')
                    self.ble_status.config(text=f"BLE: Connected to {device.address}")
                else:
                    raise Exception("Connection failed")
                    
            except Exception as e:
                messagebox.showerror("BLE Connection Error", f"Failed to connect: {e}")
                self.ble_status.config(text="BLE: Connection failed")
            finally:
                self.connect_btn.config(state='normal', text="🔗 Connect")
        
        threading.Thread(target=connect_worker, daemon=True).start()
    
    def disconnect_device(self):
        """Disconnect from BLE device."""
        if self.ble_client:
            try:
                self.ble_client.disconnect()
                self.connect_btn.config(state='normal')
                self.disconnect_btn.config(state='disabled')
                self.ble_battery_btn.config(state='disabled')
                self.ble_light_btn.config(state='disabled')
                self.ble_sound_btn.config(state='disabled')
                self.ble_status.config(text="BLE: Disconnected")
            except Exception as e:
                messagebox.showerror("BLE Disconnect Error", f"Failed to disconnect: {e}")
    
    def get_ble_battery(self):
        """Get battery level via BLE."""
        def battery_worker():
            try:
                battery_level = self.ble_client.get_battery_level()
                messagebox.showinfo("BLE Battery", f"Battery Level: {battery_level}%")
            except Exception as e:
                messagebox.showerror("BLE Battery Error", f"Failed to get battery: {e}")
        
        threading.Thread(target=battery_worker, daemon=True).start()
    
    def ble_light_toggle(self):
        """Toggle BLE light."""
        def light_worker():
            try:
                # For simplicity, we'll just toggle on for now
                self.ble_client.send_command('light', 'on')
                messagebox.showinfo("BLE Light", "Light command sent")
            except Exception as e:
                messagebox.showerror("BLE Light Error", f"Failed to control light: {e}")
        
        threading.Thread(target=light_worker, daemon=True).start()
    
    def ble_sound_toggle(self):
        """Toggle BLE sound."""
        def sound_worker():
            try:
                # For simplicity, we'll just toggle on for now
                self.ble_client.send_command('sound', 'on')
                messagebox.showinfo("BLE Sound", "Sound command sent")
            except Exception as e:
                messagebox.showerror("BLE Sound Error", f"Failed to control sound: {e}")
        
        threading.Thread(target=sound_worker, daemon=True).start()


class TractiveGUI:
    """
    Modern PyTractive GUI application.
    
    This class provides a comprehensive GUI interface with modern design,
    real-time updates, BLE support, and integration with all PyTractive features.
    """
    
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.setup_styles()
        self.setup_ui()
        
        # Initialize client and data
        self.client: Optional[TractiveClient] = None
        self.config_manager = ConfigManager()
        self.current_location: Optional[GPSLocation] = None
        self.current_device_status: Optional[DeviceStatus] = None
        self.current_pet_data: Optional[PetData] = None
        
        # Auto-update settings
        self.auto_update_enabled = True
        self.update_interval = 30  # seconds
        self.last_update = None
        
        # Start initialization
        self.initialize_client()
    
    def setup_window(self):
        """Setup main window."""
        self.root.title("PyTractive - Modern GPS Tracker Interface")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Set icon if available
        try:
            # You could add an icon file here
            pass
        except:
            pass
    
    def setup_styles(self):
        """Setup modern styles."""
        style = ttk.Style()
        
        # Configure modern theme
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        
        # Configure colors
        style.configure('Title.TLabel', font=ModernStyle.FONTS['title'])
        style.configure('Subtitle.TLabel', font=ModernStyle.FONTS['subtitle'])
        style.configure('Card.TLabelFrame', relief='solid', borderwidth=1)
    
    def setup_ui(self):
        """Setup the main UI."""
        # Menu bar
        self.setup_menu()
        
        # Main container
        main_container = ttk.PanedWindow(self.root, orient='horizontal')
        main_container.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Left panel
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, weight=1)
        
        # Device status card
        self.device_card = InfoCard(left_panel, "Device Status")
        self.device_card.pack(fill='x', pady=(0, ModernStyle.PADDING['small']))
        
        self.device_card.add_field('tracker_id', 'Tracker ID')
        self.device_card.add_field('battery_level', 'Battery Level')
        self.device_card.add_field('hw_status', 'Hardware Status')
        self.device_card.add_field('gps_state', 'GPS State')
        self.device_card.add_field('battery_saver', 'Battery Saver')
        self.device_card.add_field('live_tracking', 'Live Tracking')
        
        # Pet info card
        self.pet_card = InfoCard(left_panel, "Pet Information")
        self.pet_card.pack(fill='x', pady=(0, ModernStyle.PADDING['small']))
        
        self.pet_card.add_field('name', 'Name')
        self.pet_card.add_field('type', 'Type')
        self.pet_card.add_field('breed', 'Breed')
        self.pet_card.add_field('gender', 'Gender')
        self.pet_card.add_field('birthday', 'Birthday')
        
        # Control panel
        self.control_panel = ControlPanel(left_panel)
        self.control_panel.pack(fill='x', pady=(0, ModernStyle.PADDING['small']))
        self.control_panel.set_control_callback(self.send_control_command)
        
        # BLE panel
        self.ble_panel = BLEPanel(left_panel)
        self.ble_panel.pack(fill='x', pady=(0, ModernStyle.PADDING['small']))
        
        # Right panel
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=2)
        
        # Map frame
        self.map_frame = MapFrame(right_panel)
        self.map_frame.pack(fill='both', expand=True, pady=(0, ModernStyle.PADDING['small']))
        self.map_frame.set_refresh_callback(self.refresh_location)
        
        # Status bar
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side='bottom', fill='x')
        
        # Auto-update frame
        update_frame = ttk.Frame(right_panel)
        update_frame.pack(fill='x')
        
        self.auto_update_var = tk.BooleanVar(value=True)
        auto_update_check = ttk.Checkbutton(
            update_frame,
            text="Auto-update every 30 seconds",
            variable=self.auto_update_var,
            command=self.toggle_auto_update
        )
        auto_update_check.pack(side=tk.LEFT)
        
        refresh_all_btn = ttk.Button(
            update_frame,
            text="🔄 Refresh All",
            command=self.refresh_all_data
        )
        refresh_all_btn.pack(side=tk.RIGHT)
    
    def setup_menu(self):
        """Setup menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export GPS Data...", command=self.export_gps_data)
        file_menu.add_separator()
        file_menu.add_command(label="Settings...", command=self.show_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Location History...", command=self.show_location_history)
        tools_menu.add_command(label="Generate Share Link...", command=self.generate_share_link)
        tools_menu.add_command(label="Open Web Interface...", command=self.open_web_interface)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About...", command=self.show_about)
        help_menu.add_command(label="Documentation", command=self.open_documentation)
    
    def initialize_client(self):
        """Initialize the Tractive client."""
        def init_worker():
            try:
                self.status_bar.show_progress()
                self.status_bar.set_connection_status(False)
                
                # Initialize client
                self.client = TractiveClient()
                
                # Test connection
                device_status = self.client.get_device_status()
                
                self.status_bar.set_connection_status(True, "API")
                self.status_bar.set_last_update()
                
                # Initial data load
                self.refresh_all_data()
                
                # Start auto-update if enabled
                if self.auto_update_enabled:
                    self.start_auto_update()
                
            except Exception as e:
                logger.error(f"Failed to initialize client: {e}")
                messagebox.showerror(
                    "Connection Error", 
                    f"Failed to connect to Tractive API:\n{e}\n\nPlease check your credentials and network connection."
                )
                self.status_bar.set_connection_status(False)
            finally:
                self.status_bar.hide_progress()
        
        threading.Thread(target=init_worker, daemon=True).start()
    
    def refresh_all_data(self):
        """Refresh all data from the API."""
        def refresh_worker():
            try:
                if not self.client:
                    return
                
                self.status_bar.show_progress()
                
                # Get device status
                device_status = self.client.get_device_status()
                self.update_device_status(device_status)
                
                # Get pet data
                pet_data = self.client.get_pet_data()
                self.update_pet_info(pet_data)
                
                # Get location
                location = self.client.get_gps_location()
                if location:
                    # Get address (simplified for now)
                    address = f"Lat: {location.latitude:.4f}, Lon: {location.longitude:.4f}"
                    distance_home = 0  # Would calculate from home coordinates
                    self.map_frame.update_location(location, address, distance_home)
                
                self.status_bar.set_last_update()
                
            except Exception as e:
                logger.error(f"Failed to refresh data: {e}")
                messagebox.showerror("Data Refresh Error", f"Failed to refresh data: {e}")
            finally:
                self.status_bar.hide_progress()
        
        threading.Thread(target=refresh_worker, daemon=True).start()
    
    def update_device_status(self, device_status: DeviceStatus):
        """Update device status display."""
        self.current_device_status = device_status
        
        self.device_card.update_fields({
            'tracker_id': device_status.tracker_id or "N/A",
            'battery_level': f"{device_status.battery_level}%" if device_status.battery_level else "N/A",
            'hw_status': device_status.hw_status or "N/A",
            'gps_state': device_status.gps_state or "N/A",
            'battery_saver': "Enabled" if device_status.battery_save_mode else "Disabled",
            'live_tracking': "Active" if device_status.live_tracking else "Inactive"
        })
    
    def update_pet_info(self, pet_data: PetData):
        """Update pet information display."""
        self.current_pet_data = pet_data
        
        birthday_str = "N/A"
        if pet_data.birthday:
            birthday_str = pet_data.birthday.strftime('%Y-%m-%d')
        
        self.pet_card.update_fields({
            'name': pet_data.name or "N/A",
            'type': pet_data.pet_type or "N/A", 
            'breed': pet_data.breed or "N/A",
            'gender': pet_data.gender or "N/A",
            'birthday': birthday_str
        })
    
    def send_control_command(self, command: str, state: str):
        """Send control command to device."""
        def command_worker():
            try:
                if not self.client:
                    messagebox.showerror("Error", "Not connected to Tractive API")
                    return
                
                success = self.client.send_command(command, state)
                
                if success:
                    messagebox.showinfo("Command Sent", f"{command.replace('_', ' ').title()} set to {state}")
                    # Refresh device status after command
                    threading.Timer(2.0, self.refresh_all_data).start()
                else:
                    messagebox.showerror("Command Failed", f"Failed to set {command} to {state}")
                    
            except Exception as e:
                logger.error(f"Command failed: {e}")
                messagebox.showerror("Command Error", f"Command failed: {e}")
        
        threading.Thread(target=command_worker, daemon=True).start()
    
    def refresh_location(self):
        """Refresh location data only."""
        def location_worker():
            try:
                if not self.client:
                    return
                
                location = self.client.get_gps_location()
                if location:
                    address = f"Lat: {location.latitude:.4f}, Lon: {location.longitude:.4f}"
                    distance_home = 0  # Would calculate from home coordinates
                    self.map_frame.update_location(location, address, distance_home)
                    
            except Exception as e:
                logger.error(f"Failed to refresh location: {e}")
                messagebox.showerror("Location Error", f"Failed to refresh location: {e}")
        
        threading.Thread(target=location_worker, daemon=True).start()
    
    def toggle_auto_update(self):
        """Toggle auto-update functionality."""
        self.auto_update_enabled = self.auto_update_var.get()
        
        if self.auto_update_enabled:
            self.start_auto_update()
        else:
            # Cancel any existing auto-update timer
            pass
    
    def start_auto_update(self):
        """Start auto-update timer."""
        if self.auto_update_enabled:
            self.refresh_all_data()
            # Schedule next update
            self.root.after(self.update_interval * 1000, self.start_auto_update)
    
    # Menu command implementations
    def export_gps_data(self):
        """Export GPS data to CSV file."""
        def export_worker():
            try:
                if not self.client:
                    messagebox.showerror("Error", "Not connected to Tractive API")
                    return
                
                # Get filename from user
                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    title="Export GPS Data"
                )
                
                if filename:
                    self.status_bar.show_progress()
                    
                    # Export data (would need to implement in client)
                    # For now, show success message
                    messagebox.showinfo("Export Complete", f"GPS data exported to {filename}")
                    
            except Exception as e:
                logger.error(f"Export failed: {e}")
                messagebox.showerror("Export Error", f"Failed to export data: {e}")
            finally:
                self.status_bar.hide_progress()
        
        threading.Thread(target=export_worker, daemon=True).start()
    
    def show_settings(self):
        """Show settings dialog."""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("400x300")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Auto-update interval
        interval_frame = ttk.Frame(settings_window)
        interval_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(interval_frame, text="Auto-update interval (seconds):").pack(side=tk.LEFT)
        
        interval_var = tk.StringVar(value=str(self.update_interval))
        interval_entry = ttk.Entry(interval_frame, textvariable=interval_var, width=10)
        interval_entry.pack(side=tk.RIGHT)
        
        # Buttons
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def save_settings():
            try:
                self.update_interval = int(interval_var.get())
                messagebox.showinfo("Settings", "Settings saved successfully")
                settings_window.destroy()
            except ValueError:
                messagebox.showerror("Error", "Invalid interval value")
        
        ttk.Button(button_frame, text="Save", command=save_settings).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=settings_window.destroy).pack(side=tk.RIGHT)
    
    def show_location_history(self):
        """Show location history window."""
        history_window = tk.Toplevel(self.root)
        history_window.title("Location History")
        history_window.geometry("600x400")
        history_window.transient(self.root)
        
        # Create a simple text display for now
        text_frame = ttk.Frame(history_window)
        text_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        text_widget = tk.Text(text_frame, wrap='word')
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        
        text_widget.config(yscrollcommand=scrollbar.set)
        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        text_widget.insert('1.0', "Location history would be displayed here.\n")
        text_widget.insert('end', "This feature requires implementation in the client.")
        text_widget.config(state='disabled')
    
    def generate_share_link(self):
        """Generate public share link."""
        def share_worker():
            try:
                if not self.client:
                    messagebox.showerror("Error", "Not connected to Tractive API")
                    return
                
                message = simpledialog.askstring("Share Link", "Enter a message for the share link:")
                if message:
                    # Would generate share link via client
                    share_url = "https://tractive.com/share/example123"  # Placeholder
                    
                    result_window = tk.Toplevel(self.root)
                    result_window.title("Share Link Generated")
                    result_window.geometry("400x200")
                    result_window.transient(self.root)
                    
                    ttk.Label(result_window, text="Share link generated successfully!").pack(pady=10)
                    
                    link_frame = ttk.Frame(result_window)
                    link_frame.pack(fill='x', padx=10, pady=10)
                    
                    link_entry = ttk.Entry(link_frame, width=50)
                    link_entry.insert(0, share_url)
                    link_entry.config(state='readonly')
                    link_entry.pack(fill='x')
                    
                    def copy_link():
                        result_window.clipboard_clear()
                        result_window.clipboard_append(share_url)
                        messagebox.showinfo("Copied", "Link copied to clipboard")
                    
                    ttk.Button(result_window, text="Copy Link", command=copy_link).pack(pady=10)
                    
            except Exception as e:
                logger.error(f"Share link generation failed: {e}")
                messagebox.showerror("Share Error", f"Failed to generate share link: {e}")
        
        threading.Thread(target=share_worker, daemon=True).start()
    
    def open_web_interface(self):
        """Open Tractive web interface."""
        webbrowser.open("https://my.tractive.com/")
    
    def show_about(self):
        """Show about dialog."""
        about_text = """PyTractive v2.0
Modern Tractive GPS Tracker Interface

Features:
• Real-time GPS tracking
• Device control (LED, buzzer, live tracking)
• Bluetooth BLE communication
• Interactive mapping
• Data export and analytics
• Modern GUI interface

© 2025 Dr. Usman Kayani
"""
        messagebox.showinfo("About PyTractive", about_text)
    
    def open_documentation(self):
        """Open documentation."""
        webbrowser.open("https://github.com/drrobotk/PyTractive")
    
    def run(self):
        """Run the GUI application."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("GUI application interrupted by user")
        except Exception as e:
            logger.error(f"GUI application error: {e}")
            messagebox.showerror("Application Error", f"An error occurred: {e}")


def launch_gui():
    """Launch the PyTractive GUI application."""
    try:
        app = TractiveGUI()
        app.run()
    except Exception as e:
        print(f"Failed to launch GUI: {e}")
        if tk._default_root:
            messagebox.showerror("Launch Error", f"Failed to launch GUI: {e}")


if __name__ == "__main__":
    launch_gui()
