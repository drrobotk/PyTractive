"""
Module for Tracive GPS tracker communication.

Provides the methods:

* :func: `IFTTT_trigger`
* :class: `Tractive`
"""
import requests, json, time, base64, platform
from typing import Optional, Dict, Union
from pathlib import Path

import pandas as pd

from user_env import user_environ
from encryption import get_creds, initialize_creds

__author__ = ['Dr. Usman Kayani']

def IFTTT_trigger(action: str, key: str) -> None:
    """
    Trigger action via IFTTT.
    
    Args:
        action: str
            The action to trigger.
        key: str
            The IFTTT key.

    Returns:
        None
    """
    requests.post(f'https://maker.ifttt.com/trigger/{action}/with/key/{key}')

class Tractive(object):
    def __init__(self, filename: str = 'login.conf') -> None:
        """
        Initialize Tractive object.

        Args:
            filename: str
                The filename of the login configuration file.
        
        Returns:
            None
        """
        app_name = 'TRACTIVE'
        self.main_url = 'https://graph.tractive.com/3'
        is_environ = (
            user_environ(f'{app_name}_EMAIL') and
            user_environ(f'{app_name}_PASSWD') and
            user_environ(f'{app_name}_LATLONG')
        )

        if not is_environ and platform.system() != 'Windows':
            self.email, self.password, self.home = _read_creds(filename)
        else:
            initialize_creds(app_name)
            creds = get_creds(app_name)
            creds['latlong'] = [str(x) for x in creds['latlong']]
            self.email, self.password, self.home = creds.values()
        self.access_token, self.user_id = self._get_creds()
        self.tracker_id = self._tracker_id()
        
    def _get_creds(self) -> tuple:
        """Get access_token and user_id from credenials."""
        data = {
            'platform_email' : self.email, 
            'platform_token' : self.password, 
            'grant_type' : 'tractive'
        }
        creds_dict = _request_data(
            f'{self.main_url}/auth/token', 
            data=data
        )
        return creds_dict['access_token'], creds_dict['user_id']
    
    def _tracker_id(self) -> str:
        """Get tracker_id from access_token and user_id."""
        tracker_dict = _request_data(
            f'{self.main_url}/user/{self.user_id}/trackers', 
            self.access_token
        )
        return tracker_dict[0]['_id']
    
    def get_device_data(self, partial: bool = False) -> tuple:
        """
        Get device data from access_token and tracker_id.
        
        Args:
            partial: bool
                If True, return only the last entry.
        
        Returns:
            tuple
        """
        hw_report_url = f'{self.main_url}/device_hw_report/{self.tracker_id}'
        tracker_data_url = f'{self.main_url}/tracker/{self.tracker_id}'

        hw_report_dict = _request_data(hw_report_url, self.access_token)
        if partial:
            return hw_report_dict['battery_level'], hw_report_dict['time']

        device_data_dict = {
            **_request_data(tracker_data_url, self.access_token), 
            **hw_report_dict
        }

        try:
            return (
                device_data_dict['battery_level'], device_data_dict['hw_status'], 
                device_data_dict['time'], device_data_dict['temperature_state'], 
                device_data_dict['state'], device_data_dict['battery_save_mode']
            )
        except KeyError:
            return (
                device_data_dict['battery_level'], device_data_dict['hw_status'], 
                device_data_dict['time'], 'NA', 
                device_data_dict['state'], device_data_dict['battery_save_mode']
            )

    def get_GPS(self) -> tuple:
        """get GPS data using method 1."""
        gps_dict = _request_data(
            f'{self.main_url}/device_pos_report/{self.tracker_id}',
            self.access_token
        )
        try:
            return (
                gps_dict['latlong'], gps_dict['time'], gps_dict['pos_uncertainty'], 
                gps_dict['altitude'], gps_dict['speed'], gps_dict['course']
            )
        except KeyError:
            try:
                # Replace missing values on KeyError.
                return gps_dict['latlong'], gps_dict['time'], gps_dict['pos_uncertainty'], 0, gps_dict['speed'], 0
            except:
                # Fallback on method 2 as last resort.
                i = 1
                while gps_dict['time'] != self.get_GPS2(i)[1]:
                    i += 1
                return self.get_GPS2(i)
    
    def get_GPS2(self, i) -> tuple:
        """get GPS data using method 2."""
        now = int(time.time())
        before = now - 3600*i
        gps_dict = self._rGPS(start=now, end=before)
        try:
            return (
                gps_dict[0][-1]['latlong'], gps_dict[0][-1]['time'], gps_dict[0][-1]['pos_uncertainty'], 
                gps_dict[0][-1]['alt'], gps_dict[0][-1]['speed'], gps_dict[0][-1]['course']
            )
        except KeyError:
            # Replace missing values on KeyError.
            return (
                gps_dict[0][-1]['latlong'], gps_dict[0][-1]['time'], gps_dict[0][-1]['pos_uncertainty'], 
                gps_dict[0][-1]['alt'], gps_dict[0][-1]['speed'], 0
            )

    def _rGPS(self, start, end) -> Dict:
        """Get raw GPS data between two time intervals."""
        return (
            _request_data(
                f'{self.main_url}/tracker/{self.tracker_id}/positions?time_from={end}&time_to={start}&format=json_segments', 
                self.access_token
            )
        )

    def all_gps_data(
        self,
        export: Optional[bool] = False, 
        filename_csv: Optional[str] = 'gps_data.csv',
        convert_timestamp: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Export all gps data to csv.
        
        Args:
            export: bool
                If True, export data to csv.
            filename_csv: str
                The filename of the csv file.
            convert_timestamp: bool
                If True, convert timestamp to datetime.

        Returns:
            pd.DataFrame
        """
        total_data = []
        start = int(time.time())

        if Path(filename_csv).is_file():
            read_df = pd.read_csv(filename_csv)

            if isinstance(read_df.time[0], str):
                read_df['time'] = pd.to_datetime(read_df.time).apply(
                    lambda dt: int(dt.timestamp())
                )

            end = read_df['time'].iloc[-1]
        else:
            read_df = pd.DataFrame()
            end = self.get_pet_data(date_only=True)
        
        for data in self._rGPS(start, end):
            total_data += data

        df = (
            pd.concat([pd.DataFrame(total_data), read_df])
            .sort_values(by=['time'])
            .drop_duplicates(subset=['time'])
            .fillna(0)
            .reset_index(drop=True)
        )

        if convert_timestamp:
            df['time'] = pd.to_datetime(df['time'], unit='s')

        if export:
            df.to_csv(filename_csv, index=False)
        
        print(f'GPS data exported to {filename_csv}')
        return df
        
    def command(self, command, state) -> None:
        """
        Execute command on tracker and turn on/off sensors.
        
        Args:
            command: str
                The command to execute.
            state: str
                The state of the command.
        
        Returns:
            None
        """
        if state not in ('on', 'off'):
            raise ValueError('Incorrect state, please provide `on` or `off`.')
        if command not in (
            'battery_saver', 
            'live_tracking', 
            'led_control', 
            'buzzer_control'
        ):
            raise ValueError('Incorrect command.')
        if command == 'battery_saver':
                _request_data(
                    f'{self.main_url}/tracker/{self.tracker_id}/battery_save_mode',
                    self.access_token,
                    {'battery_save_mode' : state == 'on'}
                )
        else:
            _request_data(
                f'{self.main_url}/tracker/{self.tracker_id}/command/{command}/{state}',
                self.access_token
            )
        
    def chk_public_share(self) -> Union[str,int]:
        """Check if public share link exists and if so return id."""
        public_share_dict = _request_data(
            f'{self.main_url}/tracker/{self.tracker_id}/public_shares',
            self.access_token
        )
        if len(public_share_dict) > 0:
            return public_share_dict[0]['_id']
        else:
            return 0
            
    def generate_share_id(self, message: str) -> str:
        """
        Generate share id for public url.
        
        Args:
            message: str
                The message to share.
        
        Returns:
            str
        """
        share_id_dict = _request_data(
            f'{self.main_url}/public_share',
            self.access_token,
            {'tracker_id': self.tracker_id, 'message': message}
        )
        return share_id_dict['_id']
        
    def deactivate_share_id(self, share_id: str) -> None:
        """Deactivate current share id."""
        _request_data(
            f'{self.main_url}/public_share/{share_id}/deactivate',
            self.access_token,
            put=True
        ) 

    def public_share_link(self, share_id: str) -> tuple:
        """
        Obtain public share link and information.
        
        Args:
            share_id: str
                The share id.
        
        Returns:
            tuple
        """
        public_share_dict = _request_data(
            f'{self.main_url}/public_share/{share_id}',
            self.access_token
        )
        return (
            public_share_dict['share_link'], 
            public_share_dict['message'], 
            public_share_dict['created_at']
        )
        
    def get_pet_data(self, date_only: bool = False) -> tuple:
        """
        Get pet data from tractive.
        
        Args:
            date_only: bool

        Returns:
            tuple
        """
        pet_id = _request_data(
            f'{self.main_url}/user/{self.user_id}/trackable_objects', 
            self.access_token
        )[0]['_id']

        pet_data_dict = _request_data(
            f'{self.main_url}/trackable_object/{pet_id}',
            self.access_token
        )

        if date_only:
            return pet_data_dict['created_at']

        create_flag = False
        share_id = self.chk_public_share()
        if share_id == 0:
            create_flag = True
            share_id = self.generate_share_id('pet_data')

        link_id = self.public_share_link(share_id)[0][26:]

        breed_data = _request_data(
            f'{self.main_url}/public_share/{link_id}/info',
            self.access_token
        )

        if create_flag:
            self.deactivate_share_id(share_id)

        pet_data_dict.update(breed_data)
                
        return (
            pet_data_dict['details']['name'], pet_data_dict['details']['pet_type'], 
            pet_data_dict['details']['gender'], pet_data_dict['details']['neutered'], 
            pet_data_dict['created_at'], pet_data_dict['updated_at'], 
            pet_data_dict['details']['chip_id'], pet_data_dict['details']['birthday'], 
            pet_data_dict['details']['profile_picture_id'], pet_data_dict['breed_names'][0]
        )

def _read_creds(
    filename: str
) -> tuple:
    """Read credentials and home latlong from login.conf file."""
    creds_dict = {}
    with open(filename) as f:
        for line in f:
            (key, val) = line.split()
            creds_dict[key] = val
    return (
        creds_dict['email'], creds_dict['password'], 
        (creds_dict['lat'], creds_dict['long'])
    )

def _request_data(
    url: str,
    access_token: Optional[str] = None,  
    data: Optional[Dict] = None,
    put: Optional[bool] = False, 
) -> Dict:
    """
    Request (put, post, or get) data with headers for tractive client.
    
    Args:
        url: str
            The url to request.
        access_token: str
            The access token.
        data: dict
            The data to send.
        put: bool
            Whether to use put or post.
    
    Returns:
        dict
    """
    headers = {'X-Tractive-Client' : '5728aa1fc9077f7c32000186'}
    if access_token:
        headers.update({'Authorization': f'Bearer {access_token}'})

    if put:
        requests.put(url, headers=headers)
        return 0

    if data:
        response = requests.post(url, json=data, headers=headers)
    else:
        response = requests.get(url, headers=headers)

    return json.loads(response.text)
