import pexpect, sys, argparse
from colorama import Fore, Back, Style 

__author__ = ['Dr. Usman Kayani']


def write_req(handle, code):
	return f'char-write-req {handle} {code}'

if __name__ == '__main__':

	# parser = argparse.ArgumentParser(add_help=False)

	# Device mac address.
	DEVICE = sys.argv[1]

	# Run gatttool interactively.
	gatt = pexpect.spawn('gatttool -b ' + DEVICE + ' -t random -I')
	
	# Connect to the device.
	print(Style.RESET_ALL + 'Connecting to'),
	print(DEVICE)
	flag = True
	while flag:
		gatt.sendline('connect')
		try:
			gatt.expect('Connection successful', timeout=2)
			print('Connected!')
			flag = False
		except:
			pass

	command = 'char-read-uuid 00002a19-0000-1000-8000-00805f9b34fb'
	gatt.sendline(command)
	gatt.expect('handle: ', timeout=10)
	gatt.expect('\r\n', timeout=10)
	BATTERY = int(gatt.before[16:18], 16)
	print('Battery level: ' + str(BATTERY) + '%')

	command = 'char-read-uuid c1670003-2c5d-42fd-be9b-1f2dd6681818'
	gatt.sendline(command)
	gatt.expect('handle: ', timeout=10)
	gatt.expect('\r\n', timeout=10)
	handle = gatt.before[0:6]
	

	flag = True
	if len(sys.argv) > 2:
		while flag:
			if sys.argv[2] == 'cmd':
				print('cmd: ')
				cdl = raw_input()
			else:
				cdl = sys.argv[2] + ' ' + sys.argv[3]
				flag = False
			if cdl.split()[0] == 'light':
				if cdl.split()[1] == 'on':
					command = write_req(handle, '0b00080280000000000000004b')
				elif cdl.split()[1] == 'off':
					command = write_req(handle, '0b000802010000000000000001')
			elif cdl.split()[0] == 'sound':
				if cdl.split()[1] == 'on':
					command = write_req(handle, '0b0019022001040102010101e0')
				elif cdl.split()[1] == 'off':
					command = write_req(handle, '0b001902010000000000000001')
			elif cdl.split()[0] == 'exit':
				sys.exit()
			gatt.sendline(command)

	gatt.sendline('disconnect')
	gatt.sendline('exit')

