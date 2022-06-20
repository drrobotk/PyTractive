# pyTractive GPS
Python module and script to interact with the Tractive GPS tracker.


## Requirements

* Python 3
* [geopy](https://pypi.org/project/geopy/)
* [folium](https://pypi.org/project/folium/)
* [pandas](https://pypi.org/project/pandas/)
* [pillow](https://pypi.org/project/Pillow/) 

### Environment Variables

The following environment variables should be set.

| Key | Value | Notes |
| --- | --- | --- 
| `tractive_username` | name@host.com | Tractive username  |
| `tractive_password` | encoded_password | Tractive password encoded in base64 (ascii)  |
| `latlong` | (str(lattitude), str(longnitude)) | The latlong of the home GPS location.  |

```
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
```

### Directory layout:
    .
    ├── main.py                    # Main script              
    ├── tractive.py                # Class and functions for Tractive
    ├── ble_tractive.py            # Bluetooth low energy control (experimental)  
    ├── requirements.txt           # Python library requirements
    ├── login.conf                 # File to store login credentials and home GPS location
    └── README.md                  # This README file.
                    
## What is Tractive GPS?

![tractive_logo](https://camo.githubusercontent.com/6dbfd1a54584066a2b629f438f1a9a83738a62d8810c190f415134e5ca80e928/68747470733a2f2f7777772e636f75706f6e736b6973732e636f6d2f77702d636f6e74656e742f75706c6f6164732f323031392f30342f54726163746976652d4c6f676f2d323030783230302e706e67)

Tractive GPS Activity Monitor allows you to track your pet wherever it goes by showing the live location in the free Tractive GPS app on your smartphone or in your web browser, with location updates every 2-3 seconds in live mode. 

<img src="https://camo.githubusercontent.com/3a1244425a0fd06e9318e74ec08e0c533b9281d01ca4195b47fe9b1071c8ab36/68747470733a2f2f63646e2d65712e6e69636573686f70732e636f6d2f75706c6f61642f696d6167652f70726f647563742f6c617267652f64656661756c742f74726163746976652d6770732d747261636b65722d696b6174692d666f722d636174732d312d70632d3537343734392d656e2e706e67" alt="tractive_tracker" width="500"/>

The cat tracker records the daily activity of your kitty and shows you how active, playful or calm they are, and how much time they are sleeping, as well as being able to set activity goals for them. 

The app also allows you to view your cat's location history to see how much they are moving each day as well as finding out where their adventures take them, see the usual places they visit and where they spend most of their time with the heat map. 

The tracker collar is waterproof and lightweight at only 30g, making it perfectly designed for adventurous cats. Tractive charges a subscription fee that covers the cost for all mobile charges and provides you with unlimited location tracking.
