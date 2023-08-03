"""
Experimental script to access the Tractive GPS tracker via bluetooth (ble) to
display the battery level and turn the light or buzzer on or off.
"""
from typing import Optional
import pexpect, sys, argparse
from colorama import Style 

__author__ = ['Dr. Usman Kayani']

def io_req(handle: str, code: Optional[str] = None) -> str:
    if code:
        return f'char-write-req {handle} {code}'
    else:
        return f'char-read-uuid {handle}'

def connect_to_device(gatt, device_mac):
    print(Style.RESET_ALL + 'Connecting to', device_mac)
    while True:
        gatt.sendline('connect')
        try:
            gatt.expect('Connection successful', timeout=2)
            print('Connected!')
            return
        except:
            pass

def read_battery_level(gatt):
    command = io_req('00002a19-0000-1000-8000-00805f9b34fb')
    gatt.sendline(command)
    gatt.expect('handle: ', timeout=10)
    gatt.expect('\r\n', timeout=10)
    print(f'Battery level: {int(gatt.before[16:18], 16)}%')

def handle_commands(gatt, handle):
    if len(sys.argv) > 2:
        while True:
            if sys.argv[2] == 'cmd':
                print('cmd: ')
                cdl = input()
            else:
                cdl = sys.argv[2] + ' ' + sys.argv[3]
                flag = False
            if cdl.split()[0] == 'light':
                if cdl.split()[1] == 'on':
                    command = io_req(handle, '0b00080280000000000000004b')
                elif cdl.split()[1] == 'off':
                    command = io_req(handle, '0b000802010000000000000001')
            elif cdl.split()[0] == 'sound':
                if cdl.split()[1] == 'on':
                    command = io_req(handle, '0b0019022001040102010101e0')
                elif cdl.split()[1] == 'off':
                    command = io_req(handle, '0b001902010000000000000001')
            elif cdl.split()[0] == 'exit':
                sys.exit()
            gatt.sendline(command)

def disconnect_from_device(gatt):
    gatt.sendline('disconnect')
    gatt.sendline('exit')

if __name__ == '__main__':
    # Device mac address.
    device_mac = sys.argv[1]

    # Run gatttool interactively.
    gatt = pexpect.spawn(f'gatttool -b {device_mac} -t random -I')
    
    # Connect to the device.
    connect_to_device(gatt, device_mac)

    # Read battery level.
    read_battery_level(gatt)

    # Handle commands.
    command = io_req('c1670003-2c5d-42fd-be9b-1f2dd6681818')
    gatt.sendline(command)
    gatt.expect('handle: ', timeout=10)
    gatt.expect('\r\n', timeout=10)
    handle = gatt.before[0:6]
    handle_commands(gatt, handle)

    # Disconnect from the device.
    disconnect_from_device(gatt)
