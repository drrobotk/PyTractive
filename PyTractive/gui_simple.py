"""
Simple GUI interface for PyTractive.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
from typing import Optional

from .client import TractiveClient
from .exceptions import TractiveError


logger = logging.getLogger(__name__)


class SimpleTractiveGUI:
    """Simple PyTractive GUI application."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PyTractive - Simple Interface")
        self.root.geometry("600x400")
        
        self.client: Optional[TractiveClient] = None
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title = ttk.Label(main_frame, text="PyTractive GPS Tracker", font=('Arial', 16, 'bold'))
        title.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Status display
        self.status_text = tk.Text(main_frame, height=15, width=70)
        self.status_text.grid(row=1, column=0, columnspan=2, pady=(0, 10))
        
        # Scrollbar for text
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.status_text.yview)
        scrollbar.grid(row=1, column=2, sticky=(tk.N, tk.S))
        self.status_text.configure(yscrollcommand=scrollbar.set)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(button_frame, text="Connect", command=self.connect).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Get Status", command=self.get_status).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Get Location", command=self.get_location).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="LED On", command=self.led_on).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Clear", command=self.clear_text).pack(side=tk.LEFT, padx=(0, 5))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Initial message
        self.log("PyTractive Simple GUI Started")
        self.log("Click 'Connect' to initialize the client")
    
    def log(self, message: str):
        """Add a message to the status display."""
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_text(self):
        """Clear the text display."""
        self.status_text.delete(1.0, tk.END)
    
    def connect(self):
        """Connect to Tractive API."""
        def connect_worker():
            try:
                self.log("Connecting to Tractive API...")
                self.client = TractiveClient()
                self.log("✓ Connected successfully!")
                self.log(f"Tracker ID: {self.client.tracker_id}")
            except Exception as e:
                self.log(f"✗ Connection failed: {e}")
        
        threading.Thread(target=connect_worker, daemon=True).start()
    
    def get_status(self):
        """Get device status."""
        if not self.client:
            self.log("✗ Please connect first")
            return
            
        def status_worker():
            try:
                self.log("Getting device status...")
                status = self.client.get_device_status()
                self.log(f"Battery: {status.battery_level}%")
                self.log(f"GPS State: {status.state.value if status.state else 'Unknown'}")
                self.log(f"Last Update: {status.datetime}")
                self.log("✓ Status retrieved")
            except Exception as e:
                self.log(f"✗ Status failed: {e}")
        
        threading.Thread(target=status_worker, daemon=True).start()
    
    def get_location(self):
        """Get GPS location."""
        if not self.client:
            self.log("✗ Please connect first")
            return
            
        def location_worker():
            try:
                self.log("Getting GPS location...")
                location = self.client.get_gps_location()
                self.log(f"Coordinates: {location.coordinates}")
                
                # Handle accuracy - check if accuracy attribute exists
                if hasattr(location, 'accuracy') and location.accuracy is not None:
                    self.log(f"Accuracy: {location.accuracy}m")
                elif hasattr(location, 'uncertainty') and location.uncertainty is not None:
                    accuracy = f"{location.uncertainty}% uncertainty"
                    self.log(f"GPS Accuracy: {accuracy}")
                else:
                    self.log("Accuracy: Not available")
                
                self.log(f"Last GPS: {location.datetime}")
                self.log(f"Altitude: {location.altitude}m")
                self.log(f"Speed: {location.speed} km/h")
                
                # Calculate distance from home if possible
                try:
                    distance = self.client.get_distance_from_home(location)
                    self.log(f"Distance from home: {distance:.0f}m")
                    if distance <= 50:
                        self.log("🏠 Pet is at home!")
                    else:
                        self.log(f"📍 Pet is away from home")
                except Exception:
                    pass
                
                self.log("✓ Location retrieved")
            except Exception as e:
                self.log(f"✗ Location failed: {e}")
        
        threading.Thread(target=location_worker, daemon=True).start()
    
    def led_on(self):
        """Turn on LED."""
        if not self.client:
            self.log("✗ Please connect first")
            return
            
        def led_worker():
            try:
                self.log("Turning on LED...")
                from .models import CommandType, CommandState
                self.client.send_command(CommandType.LED_CONTROL, CommandState.ON)
                self.log("✓ LED command sent")
            except Exception as e:
                self.log(f"✗ LED command failed: {e}")
        
        threading.Thread(target=led_worker, daemon=True).start()
    
    def run(self):
        """Run the GUI."""
        try:
            self.root.mainloop()
        except Exception as e:
            logger.error(f"GUI error: {e}")
            messagebox.showerror("Error", f"GUI error: {e}")


def launch_simple_gui():
    """Launch the simple GUI."""
    try:
        app = SimpleTractiveGUI()
        app.run()
    except Exception as e:
        print(f"Failed to launch simple GUI: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    launch_simple_gui()
