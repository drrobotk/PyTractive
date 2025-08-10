"""
Modern Bluetooth Low Energy (BLE) functionality for PyTractive.

This module provides comprehensive BLE support for direct communication with Tractive GPS trackers,
with cross-platform support and integration with the modern PyTractive client system.
"""

import asyncio
import logging
import platform
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List, Callable, Any
import sys

from .exceptions import TractiveError, ConfigurationError
from .models import DeviceStatus, CommandType, CommandState


logger = logging.getLogger(__name__)


class BLEError(TractiveError):
    """BLE-specific error."""
    pass


class BLEConnectionState(Enum):
    """BLE connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class BLEDevice:
    """Represents a BLE device."""
    address: str
    name: Optional[str] = None
    rssi: Optional[int] = None
    advertisement_data: Optional[Dict] = None
    is_connectable: bool = True


@dataclass
class BLECommand:
    """Represents a BLE command."""
    handle: str
    command: str
    data: bytes
    response_expected: bool = True


class BLEClientBase(ABC):
    """Abstract base class for BLE clients."""
    
    @abstractmethod
    async def connect(self, address: str) -> bool:
        """Connect to a BLE device."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the BLE device."""
        pass
    
    @abstractmethod
    async def read_characteristic(self, uuid: str) -> bytes:
        """Read a characteristic value."""
        pass
    
    @abstractmethod
    async def write_characteristic(self, uuid: str, data: bytes) -> bool:
        """Write a characteristic value."""
        pass
    
    @abstractmethod
    async def discover_devices(self, timeout: float = 10.0) -> List[BLEDevice]:
        """Discover nearby BLE devices."""
        pass


class BLEClientBleak(BLEClientBase):
    """Modern BLE client using bleak library for cross-platform support."""
    
    def __init__(self):
        try:
            from bleak import BleakClient, BleakScanner
            self.BleakClient = BleakClient
            self.BleakScanner = BleakScanner
            self._client: Optional[BleakClient] = None
            self._connected = False
        except ImportError:
            raise BLEError(
                "Bleak library not found. Install with: pip install bleak\n"
                "This provides cross-platform BLE support."
            )
    
    async def connect(self, address: str) -> bool:
        """Connect to a BLE device using bleak."""
        try:
            self._client = self.BleakClient(address)
            await self._client.connect()
            self._connected = True
            logger.info(f"Connected to BLE device: {address}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to BLE device {address}: {e}")
            raise BLEError(f"Connection failed: {e}")
    
    async def disconnect(self) -> bool:
        """Disconnect from the BLE device."""
        if self._client and self._connected:
            try:
                await self._client.disconnect()
                self._connected = False
                logger.info("Disconnected from BLE device")
                return True
            except Exception as e:
                logger.error(f"Failed to disconnect: {e}")
        return False
    
    async def read_characteristic(self, uuid: str) -> bytes:
        """Read a characteristic value."""
        if not self._client or not self._connected:
            raise BLEError("Not connected to any device")
        
        try:
            data = await self._client.read_gatt_char(uuid)
            logger.debug(f"Read characteristic {uuid}: {data.hex()}")
            return data
        except Exception as e:
            logger.error(f"Failed to read characteristic {uuid}: {e}")
            raise BLEError(f"Read failed: {e}")
    
    async def write_characteristic(self, uuid: str, data: bytes) -> bool:
        """Write a characteristic value."""
        if not self._client or not self._connected:
            raise BLEError("Not connected to any device")
        
        try:
            await self._client.write_gatt_char(uuid, data)
            logger.debug(f"Wrote to characteristic {uuid}: {data.hex()}")
            return True
        except Exception as e:
            logger.error(f"Failed to write characteristic {uuid}: {e}")
            raise BLEError(f"Write failed: {e}")
    
    async def discover_devices(self, timeout: float = 10.0) -> List[BLEDevice]:
        """Discover nearby BLE devices."""
        try:
            devices = await self.BleakScanner.discover(timeout=timeout)
            ble_devices = []
            
            for device in devices:
                ble_device = BLEDevice(
                    address=device.address,
                    name=device.name,
                    rssi=device.rssi,
                    advertisement_data=device.metadata,
                    is_connectable=True
                )
                ble_devices.append(ble_device)
            
            logger.info(f"Discovered {len(ble_devices)} BLE devices")
            return ble_devices
            
        except Exception as e:
            logger.error(f"Device discovery failed: {e}")
            raise BLEError(f"Discovery failed: {e}")


class BLEClientLegacy(BLEClientBase):
    """Legacy BLE client using pexpect and gatttool (Linux only)."""
    
    def __init__(self):
        if platform.system().lower() != 'linux':
            raise BLEError("Legacy BLE client only supports Linux")
        
        try:
            import pexpect
            self.pexpect = pexpect
            self._gatt = None
            self._connected = False
        except ImportError:
            raise BLEError(
                "pexpect library not found. Install with: pip install pexpect\n"
                "This is required for legacy Linux BLE support."
            )
    
    async def connect(self, address: str) -> bool:
        """Connect using gatttool."""
        try:
            self._gatt = self.pexpect.spawn(f'gatttool -b {address} -t random -I')
            self._gatt.sendline('connect')
            self._gatt.expect('Connection successful', timeout=10)
            self._connected = True
            logger.info(f"Connected to BLE device via gatttool: {address}")
            return True
        except Exception as e:
            logger.error(f"gatttool connection failed: {e}")
            raise BLEError(f"gatttool connection failed: {e}")
    
    async def disconnect(self) -> bool:
        """Disconnect from gatttool."""
        if self._gatt and self._connected:
            try:
                self._gatt.sendline('disconnect')
                self._gatt.sendline('exit')
                self._connected = False
                return True
            except Exception as e:
                logger.error(f"gatttool disconnect failed: {e}")
        return False
    
    async def read_characteristic(self, uuid: str) -> bytes:
        """Read characteristic using gatttool."""
        if not self._gatt or not self._connected:
            raise BLEError("Not connected to any device")
        
        try:
            self._gatt.sendline(f'char-read-uuid {uuid}')
            self._gatt.expect('handle: ', timeout=10)
            self._gatt.expect('\r\n', timeout=10)
            data_hex = self._gatt.before.decode().strip()
            data = bytes.fromhex(data_hex.replace(' ', ''))
            logger.debug(f"Read characteristic {uuid}: {data.hex()}")
            return data
        except Exception as e:
            logger.error(f"gatttool read failed: {e}")
            raise BLEError(f"Read failed: {e}")
    
    async def write_characteristic(self, uuid: str, data: bytes) -> bool:
        """Write characteristic using gatttool."""
        if not self._gatt or not self._connected:
            raise BLEError("Not connected to any device")
        
        try:
            data_hex = data.hex()
            self._gatt.sendline(f'char-write-req {uuid} {data_hex}')
            logger.debug(f"Wrote to characteristic {uuid}: {data_hex}")
            return True
        except Exception as e:
            logger.error(f"gatttool write failed: {e}")
            raise BLEError(f"Write failed: {e}")
    
    async def discover_devices(self, timeout: float = 10.0) -> List[BLEDevice]:
        """Device discovery using hcitool."""
        try:
            import subprocess
            result = subprocess.run(['hcitool', 'lescan'], 
                                  timeout=timeout, 
                                  capture_output=True, 
                                  text=True)
            
            devices = []
            for line in result.stdout.split('\n'):
                if ':' in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        address = parts[0]
                        name = ' '.join(parts[1:]) if len(parts) > 1 else None
                        devices.append(BLEDevice(address=address, name=name))
            
            logger.info(f"Discovered {len(devices)} BLE devices via hcitool")
            return devices
            
        except Exception as e:
            logger.error(f"hcitool discovery failed: {e}")
            raise BLEError(f"Discovery failed: {e}")


class TractiveBLEClient:
    """
    High-level BLE client specifically for Tractive GPS trackers.
    
    This class provides a modern, integrated interface for BLE communication
    with Tractive devices, including automatic discovery, connection management,
    and Tractive-specific command handling.
    """
    
    # Tractive BLE UUIDs and handles
    BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
    BATTERY_LEVEL_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
    TRACTIVE_SERVICE_UUID = "c1670003-2c5d-42fd-be9b-1f2dd6681818"
    COMMAND_CHAR_UUID = "c1670003-2c5d-42fd-be9b-1f2dd6681818"
    
    # Tractive BLE command codes
    BLE_COMMANDS = {
        'light_on': bytes.fromhex('0b00080280000000000000004b'),
        'light_off': bytes.fromhex('0b000802010000000000000001'),
        'sound_on': bytes.fromhex('0b0019022001040102010101e0'),
        'sound_off': bytes.fromhex('0b001902010000000000000001'),
    }
    
    def __init__(self, prefer_modern: bool = True):
        """
        Initialize the Tractive BLE client.
        
        Args:
            prefer_modern: If True, try to use bleak (cross-platform) first,
                          fall back to gatttool if needed.
        """
        self.prefer_modern = prefer_modern
        self._client: Optional[BLEClientBase] = None
        self._connection_state = BLEConnectionState.DISCONNECTED
        self._device_address: Optional[str] = None
        self._connection_callbacks: List[Callable] = []
        
    async def initialize(self) -> None:
        """Initialize the BLE client."""
        if self.prefer_modern:
            try:
                self._client = BLEClientBleak()
                logger.info("Using modern BLE client (bleak)")
                return
            except BLEError as e:
                logger.warning(f"Modern BLE client unavailable: {e}")
        
        # Fall back to legacy client
        try:
            self._client = BLEClientLegacy()
            logger.info("Using legacy BLE client (gatttool)")
        except BLEError as e:
            raise BLEError(
                f"No BLE client available: {e}\n"
                "Install bleak for cross-platform support: pip install bleak\n"
                "Or on Linux, install pexpect: pip install pexpect"
            )
    
    async def discover_tractive_devices(self, timeout: float = 10.0) -> List[BLEDevice]:
        """
        Discover nearby Tractive devices.
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            List of discovered Tractive BLE devices
        """
        if not self._client:
            await self.initialize()
        
        logger.info("Discovering Tractive BLE devices...")
        all_devices = await self._client.discover_devices(timeout)
        
        # Filter for potential Tractive devices
        tractive_devices = []
        for device in all_devices:
            if (device.name and 'tractive' in device.name.lower()) or \
               (device.address and self._is_tractive_address(device.address)):
                tractive_devices.append(device)
        
        logger.info(f"Found {len(tractive_devices)} potential Tractive devices")
        return tractive_devices
    
    def _is_tractive_address(self, address: str) -> bool:
        """Check if a MAC address might belong to a Tractive device."""
        # This would need to be populated with known Tractive MAC prefixes
        # For now, we'll use a simple heuristic
        return True  # Accept all devices for now
    
    async def connect(self, device_address: str) -> bool:
        """
        Connect to a Tractive device.
        
        Args:
            device_address: MAC address of the device
            
        Returns:
            True if connection successful
        """
        if not self._client:
            await self.initialize()
        
        try:
            self._connection_state = BLEConnectionState.CONNECTING
            self._device_address = device_address
            
            success = await self._client.connect(device_address)
            
            if success:
                self._connection_state = BLEConnectionState.CONNECTED
                logger.info(f"Successfully connected to Tractive device: {device_address}")
                
                # Notify callbacks
                for callback in self._connection_callbacks:
                    try:
                        callback(True, device_address)
                    except Exception as e:
                        logger.error(f"Connection callback error: {e}")
                
                return True
            else:
                self._connection_state = BLEConnectionState.ERROR
                return False
                
        except Exception as e:
            self._connection_state = BLEConnectionState.ERROR
            logger.error(f"BLE connection failed: {e}")
            raise BLEError(f"Connection failed: {e}")
    
    async def disconnect(self) -> bool:
        """Disconnect from the current device."""
        if self._client and self._connection_state == BLEConnectionState.CONNECTED:
            try:
                success = await self._client.disconnect()
                self._connection_state = BLEConnectionState.DISCONNECTED
                
                # Notify callbacks
                for callback in self._connection_callbacks:
                    try:
                        callback(False, self._device_address)
                    except Exception as e:
                        logger.error(f"Disconnection callback error: {e}")
                
                return success
            except Exception as e:
                logger.error(f"BLE disconnection failed: {e}")
                self._connection_state = BLEConnectionState.ERROR
                return False
        return True
    
    async def get_battery_level(self) -> int:
        """
        Get battery level via BLE.
        
        Returns:
            Battery level percentage (0-100)
        """
        if self._connection_state != BLEConnectionState.CONNECTED:
            raise BLEError("Not connected to any device")
        
        try:
            data = await self._client.read_characteristic(self.BATTERY_LEVEL_CHAR_UUID)
            if data:
                battery_level = int.from_bytes(data, byteorder='little')
                logger.info(f"BLE battery level: {battery_level}%")
                return battery_level
            else:
                raise BLEError("No battery data received")
        except Exception as e:
            logger.error(f"Failed to read battery level: {e}")
            raise BLEError(f"Battery read failed: {e}")
    
    async def send_command(self, command: str, state: Optional[str] = None) -> bool:
        """
        Send a command to the Tractive device.
        
        Args:
            command: Command type ('light', 'sound', etc.)
            state: Command state ('on', 'off') if applicable
            
        Returns:
            True if command sent successfully
        """
        if self._connection_state != BLEConnectionState.CONNECTED:
            raise BLEError("Not connected to any device")
        
        # Build command key
        if state:
            command_key = f"{command}_{state}"
        else:
            command_key = command
        
        if command_key not in self.BLE_COMMANDS:
            raise BLEError(f"Unknown BLE command: {command_key}")
        
        try:
            command_data = self.BLE_COMMANDS[command_key]
            success = await self._client.write_characteristic(
                self.COMMAND_CHAR_UUID, 
                command_data
            )
            
            if success:
                logger.info(f"BLE command sent: {command_key}")
                return True
            else:
                raise BLEError("Command write failed")
                
        except Exception as e:
            logger.error(f"Failed to send BLE command {command_key}: {e}")
            raise BLEError(f"Command failed: {e}")
    
    def add_connection_callback(self, callback: Callable[[bool, str], None]) -> None:
        """
        Add a callback for connection state changes.
        
        Args:
            callback: Function called with (connected: bool, address: str)
        """
        self._connection_callbacks.append(callback)
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected to a device."""
        return self._connection_state == BLEConnectionState.CONNECTED
    
    @property
    def connection_state(self) -> BLEConnectionState:
        """Get current connection state."""
        return self._connection_state
    
    @property
    def device_address(self) -> Optional[str]:
        """Get address of currently connected device."""
        return self._device_address if self.is_connected else None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Synchronous wrapper for easier integration
class TractiveBLESync:
    """Synchronous wrapper for TractiveBLEClient."""
    
    def __init__(self, prefer_modern: bool = True):
        self._async_client = TractiveBLEClient(prefer_modern)
        self._loop = None
    
    def _run_async(self, coro):
        """Run an async coroutine synchronously."""
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we need to run in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop exists, create a new one
            return asyncio.run(coro)
    
    def discover_tractive_devices(self, timeout: float = 10.0) -> List[BLEDevice]:
        """Discover nearby Tractive devices (sync)."""
        return self._run_async(self._async_client.discover_tractive_devices(timeout))
    
    def connect(self, device_address: str) -> bool:
        """Connect to a Tractive device (sync)."""
        return self._run_async(self._async_client.connect(device_address))
    
    def disconnect(self) -> bool:
        """Disconnect from the current device (sync)."""
        return self._run_async(self._async_client.disconnect())
    
    def get_battery_level(self) -> int:
        """Get battery level via BLE (sync)."""
        return self._run_async(self._async_client.get_battery_level())
    
    def send_command(self, command: str, state: Optional[str] = None) -> bool:
        """Send a command to the Tractive device (sync)."""
        return self._run_async(self._async_client.send_command(command, state))
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected to a device."""
        return self._async_client.is_connected
    
    @property
    def connection_state(self) -> BLEConnectionState:
        """Get current connection state."""
        return self._async_client.connection_state
    
    @property
    def device_address(self) -> Optional[str]:
        """Get address of currently connected device."""
        return self._async_client.device_address
    
    def add_connection_callback(self, callback: Callable[[bool, str], None]) -> None:
        """Add a callback for connection state changes."""
        self._async_client.add_connection_callback(callback)


def get_ble_client(prefer_modern: bool = True) -> TractiveBLESync:
    """
    Factory function to get a BLE client.
    
    Args:
        prefer_modern: If True, prefer bleak over gatttool
        
    Returns:
        TractiveBLESync instance
    """
    return TractiveBLESync(prefer_modern=prefer_modern)
