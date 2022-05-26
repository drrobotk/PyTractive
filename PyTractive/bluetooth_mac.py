
import asyncio, argparse
from bleak import BleakClient

address = "2C34464E-9C38-279D-923C-E60D5EBBC3E8"
char = "c1670003-2c5d-42fd-be9b-1f2dd6681818"
sensor_cmds = {
    'sound': {'on': '0b0019022001040102010101e0', 'off': '0b001902010000000000000001'}, 
    'light': {'on': '0b00080280000000000000004b', 'off': '0b000802010000000000000001'}
}

async def main(address, sensor, switch):
    chars = sensor_cmds.get(sensor)
    async with BleakClient(address) as client:
        print('Connected to:', address)
        battery_byte = await client.read_gatt_char('00002a19-0000-1000-8000-00805f9b34fb')
        battery_level = int.from_bytes(battery_byte, byteorder='big', signed=False)
        print(f"Battery level: {battery_level}%")
        cmd = bytes.fromhex(chars.get(switch))
        for _ in range(10000):
            await client.write_gatt_char(char, cmd)

def connect(args):
    stop = False
    print('Connecting.',end = '', flush=True)
    while stop == False:
        try:
            print('.', end = '', flush=True)
            asyncio.run(main(**args))
            stop = True
        except: 
            pass

if __name__ == "__main__":
    argparse = argparse.ArgumentParser()
    argparse.add_argument(
        '-sensor',
        help='Sensor (options: light, sound).',
        metavar='sensor',
        required=True
    )
    argparse.add_argument(
        '-switch',
        help='Switch (options: on, off).',
        metavar='switch',
        required=True
    )
    args = argparse.parse_args()
    if args.sensor not in ('light', 'sound'):
        raise ValueError('Sensor must be either light or sound.')
    if args.switch not in ('on', 'off'):
        raise ValueError('Switch must be either on or off.')
    args_dict = {'address': address, 'sensor': args.sensor, 'switch': args.switch}
    connect(args_dict)