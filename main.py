"""
Main script for Tractive GPS tracker.

Options can be accessed via switches in the commandline argument e.g: `python main.py --help`.
"""
import sys, webbrowser, time, requests, argparse, folium
from PIL import Image
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from datetime import datetime

from tractive import Tractive, IFTTT_trigger

__author__ = ['Dr. Usman Kayani']

def front() -> tuple:
    """General tracker data shown when script executed."""
    (   battery_level, hw_status, network_timestamp, 
        temperature_state, GPS_state, battery_save_mode
    ) = Pet.get_device_data()

    network_time_ago = int(time.time()) - network_timestamp
    network_datetime = datetime.fromtimestamp(network_timestamp)

    print('------------------------------------------------------------------------------------------------------------------------')
    print(f'Last network connection: {network_datetime} ({_time_ago(network_time_ago)})')
    print(f'Tracker ID: {Pet.tracker_id}')
    print(f'Hardware status: {hw_status}')
    print(f'Temperature state: {temperature_state}')
    print(f'Battery level: {battery_level}%')
    print(f'Battery saver mode: {battery_save_mode}')
    print(f'GPS state: {GPS_state}')
    _saver(battery_level)
    print('------------------------------------------------------------------------------------------------------------------------')
    return battery_level, network_time_ago

def gps(switch) -> None:
    """GPS data display switch."""
    latlong, GPS_timestamp, GPS_uncertainty, alt, speed, course = Pet.get_GPS()
    GPS_time_ago = int(time.time()) - GPS_timestamp
    GPS_datetime = datetime.fromtimestamp(GPS_timestamp)
    geolocator = Nominatim(user_agent='tractive')
    location = geolocator.reverse(latlong)
    
    distance_home = int(geodesic(Pet.home, latlong).m)
    
    print(f'Last GPS connection: {GPS_datetime} ({_time_ago(GPS_time_ago)})')
    print(f'GPS uncertainty: {GPS_uncertainty}%')
    print(f'GPS coordinates: {latlong}')
    print(f'Address: {location.address}')
    print(f'Distance from Home: {distance_home}m')
    print(f'Altitude: {alt}')
    print(f'Speed: {speed}')
    print(f'Course: {course}')
    if distance_home < 50:
        print('------------------------------Cat is NEAR HOME!!!---------------------------------------')
    if switch:
        center0 = (latlong[0] + float(Pet.home[0]))/2
        center1 = (latlong[1] + float(Pet.home[1]))/2
        if distance_home < 100:
            zoom = 20
        elif distance_home < 200:
            zoom = 18
        else:
            zoom = 16
        folium_map = folium.Map(location=[center0, center1], zoom_start=zoom, control_scale=True)

        data = f'Network: {_time_ago(network_time_ago)} | GPS: {_time_ago(GPS_time_ago)} \
        | Battery: {battery_level}% | Distance: {distance_home}m'

        popup = folium.Popup(data,min_width=420,max_width=420)
        folium.Marker([latlong[0], latlong[1]], popup=popup).add_to(folium_map)
        folium.Marker([Pet.home[0], Pet.home[1]], popup='Home').add_to(folium_map)
        points = (latlong, Pet.home)
        folium.PolyLine(points, color="darkred", weight=6, opacity=5, popup=f'{distance_home}m').add_to(folium_map)
        folium_map.save('map.html')
        webbrowser.open_new('map.html')
    print('------------------------------------------------------------------------------------------------------------------------')

def pet(switch) -> None:
    """Pet data display switch."""
    (
        pet_name, pet_type, pet_gender, pet_neutered, 
        pet_creation, pet_update, pet_chip_id, 
        pet_birthday, pet_picture_id, breed
    ) =  Pet.get_pet_data()

    print('Details of pet:')
    print(f'Name: {pet_name}')
    print(f'Type: {pet_type}')
    print(f'Breed: {breed}')
    print(f'Gender: {pet_gender}')
    print(f'Birthday: {datetime.fromtimestamp(pet_birthday)}')
    print(f'Neutered: {pet_neutered}')
    print(f'Chip ID: {pet_chip_id}')
    print(f'Profile created: {datetime.fromtimestamp(pet_creation)}')
    print(f'Profile updated: {datetime.fromtimestamp(pet_update)}')
    print(f'Link to Picture: https://graph.tractive.com/3/media/resource/{pet_picture_id}.96_96_1.jpg')
    if switch:
        basewidth = 600
        img = Image.open(requests.get(f'https://graph.tractive.com/3/media/resource/{pet_picture_id}.96_96_1.jpg', stream=True).raw)
        wpercent = (basewidth/float(img.size[0]))
        hsize = int((float(img.size[1])*float(wpercent)))
        img = img.resize((basewidth,hsize), Image.ANTIALIAS)
        img.show() 
        #webbrowser.open_new('https://graph.tractive.com/3/media/resource/' + pet_picture_id + '.96_96_1.jpg')#

def trigger(distance_threshold: int) -> None:
    """Trigger notification for specified distance."""
    print(f'Trigger now started, you will recieve a notification and call when the distance from home is < {args.trigger}m')
    latlong = Pet.get_GPS()[0]
    distance_home = int(geodesic(Pet.home, latlong).m)
    last_distance = distance_home
    try:
        while distance_home >= distance_threshold:
            # Get latest GPS latlong and battery_level.
            latlong = Pet.get_GPS()[0]
            battery_level = Pet.get_device_data()[0]

            # Battery saver check.
            _saver(battery_level)

            # Calculate current distance home.
            distance_home = int(geodesic(Pet.home, latlong).m)

            # Check if new distance home is smaller than last current distance.
            if distance_home < last_distance:
                print(f'Closer....({distance_home}m)')
                last_distance = distance_home
                IFTTT_trigger(action='notification', key='enter_valid_key')

            # Pause for 10 seconds.
            time.sleep(10)
        print(f'Trigger ended. Distance from home is now: {distance_home}m.')
        IFTTT_trigger(action='call', key='enter_valid_key')
    except:
        GPS_timestamp = Pet.get_GPS()[1]
        GPS_time_ago = int(time.time()) - GPS_timestamp
        latlong = Pet.get_GPS()[0]
        distance_home = int(geodesic(Pet.home, latlong).m)
        print('Trigger stopped before completion.')
        print(f'Last distance from home is {distance_home}m {_time_ago(GPS_time_ago)} from {latlong}')
        sys.exit()

def new_location(switch) -> None:
    """Obtain new location from live feature."""
    # Store current last GPS and network time.
    GPSt1 = Pet.get_GPS()[1]
    Networkt1 = Pet.get_device_data()[2]

    # Turn on live tracking.
    Pet.command('live_tracking', 'on')
    print('Getting live location....')

    # Check network time until updated.
    Networkt2 = Networkt1
    while Networkt2 <= Networkt1:
        Networkt2 = Pet.get_device_data()[2]

    network_time_ago = int(time.time()) - Networkt2
    network_datetime = datetime.fromtimestamp(Networkt2)

    print('Network established!')
    print(f'Last network connection: {network_datetime} ({_time_ago(network_time_ago)})')
    print('Getting GPS.............')
    # Check gps time until updated.
    GPSt2 = GPSt1
    while GPSt2 <= GPSt1:
        GPSt2 = Pet.get_GPS()[1]

    # Turn off live tracking.
    time.sleep(6)
    Pet.command('live_tracking', 'off')

    # Display latest gps data.
    gps(switch)

def public(switch) -> None:
    """Generate public link with message and display data switch."""
    chk = Pet.chk_public_share()
    if args.public == 'on':
        if chk == 0:
            print('Enter message: ')
            message = str(input())
            share_id = Pet.generate_share_id(message)
        else:
            share_id = chk
            message = Pet.public_share_link(share_id)[1]
            print('Public link already exists.')
        print('------------------------------------------------------------------------------------------------------------------------')
        link = Pet.public_share_link(share_id)[0]
        created_at = Pet.public_share_link(share_id)[2]
        print(f'Link: {link}')
        print(f'Created at: {datetime.fromtimestamp(created_at)}')
        print(f'Message: {message}')
        if switch:
            webbrowser.open_new(link)
    else:
        if chk != 0:
            share_id = chk
            Pet.deactivate_share_id(share_id)
            print('Deactivated.')
        else:
            print('No link exists.')

def switches(args):
    """
    usage: main.py [-h] [--live state] [--led state] [--buzzer state] [--battery_saver state] [--public state] 
     [--trigger radius] [--gps [-I]] [--nloc [-I]] [--pet [-I]] [--export] 

    optional arguments:

    -h, --help              show this help message and exit

    --live state            GPS Live control. 
    --led state             LED control. 
    --buzzer state          Buzzer control.                           
    --battery_saver state   Battery saver control.                                 
    --public state          Public link share control.
    {state = 'on' or 'off'}

    --trigger radius        Trigger action within distance radius.

    --gps                   Current GPS location.
    --nloc                  New live location.
    --pet                   Pet data.
    [-I]                    optional: Interactive window.

    --export                Export GPS data to file `gps_data.csv`.
    """
    if args.help:
        help(switches)
        sys.exit()

    state = {'on', 'off'}
    if args.live in state:
        Pet.command('live_tracking', args.live)
        print(f'Live tracking is now {args.live}.')

    if args.led in state:
        Pet.command('led_control', args.led)
        print(f'LED tracking is now {args.led}.')
    
    if args.buzzer in state:
        Pet.command('buzzer_control', args.buzzer)
        print(f'Buzzer tracking is now {args.buzzer}.')

    if args.battery_saver in state:
        Pet.command('battery_saver', args.battery_saver)
        print(f'Battery saver is now {args.battery_saver}.')
            
    if args.public in state:
        public(args.I)
    elif args.public:
        raise ValueError('Incorrect state, the option must be on or off')

    if isinstance(args.trigger, int):
        trigger(args.trigger)
    elif args.public:
        raise ValueError('Distance trigger must be an integer.')

    if args.gps:
        gps(args.I)

    if args.pet:
        pet(args.I)

    if args.nloc:
        new_location(args.I)

    if args.export:
        Pet.all_gps_data(export=True)  

def _saver(battery_level) -> None:
    """Battery saver for given battery level."""
    if battery_level < 30:
        Pet.command('battery_saver', 'on')

def _time_ago(t: int) -> str:
    """Get time ago information from duration."""
    if t < 3600:
        return f'{int(t/ 60)} minutes ago'
    else:
        return f'{int(t / 3600)} hours and {int(t/60) - int(int(t/60)/60)*60} minutes ago'

if __name__ == '__main__':
    Pet = Tractive(filename='login.conf')
    battery_level, network_time_ago = front()

    parser = argparse.ArgumentParser(add_help=False)
    
    parser.add_argument('-h', '--help', action='store_true', help='show this help message and exit', required=False)

    parser.add_argument('--live', type=str, metavar='state', help='GPS Live control.')
    parser.add_argument('--led', type=str, metavar='state', help='LED control.')
    parser.add_argument('--buzzer', type=str, metavar='state', help='Buzzer control.')
    parser.add_argument('--battery_saver', type=str, metavar='state', help='Battery saver control.')
    parser.add_argument('--public', type=str, metavar='state', help='Public link share control.')

    parser.add_argument('--trigger', type=int, metavar='radius', help='Trigger action within distance radius.')

    parser.add_argument('--gps', action='store_true', help='Current GPS location.')
    parser.add_argument('--nloc', action='store_true', help='New live location.')
    parser.add_argument('--pet', action='store_true', help='Pet data.')
    parser.add_argument('-I', action='store_true', help='optional: Interactive window', required=False)

    parser.add_argument('--export', action='store_true', help='Export GPS data to file `gps_data.csv`.')
    
    args = parser.parse_args()
    switches(args)
    print('------------------------------------------------------------------------------------------------------------------------')
