"""
Module to handle the encryption of the credentials.

Provides the functions:

*func*: `get_creds`
*func*: `initialize_creds`
*func*: `encrypt`
*func*: `decrypt`
*func*: `gen_unique_key`
"""
import os, base64, getpass
import uuid as UUID
from typing import Dict
from subprocess import check_output

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto import Random
from cryptography.fernet import Fernet

from .user_env import user_environ, add_user_environment

app_name = 'TRACTIVE'

def initialize_creds(
    app_name: str,
    reintialize: bool = False,
    enable_passcode: bool = False
) -> None:
    """
    Initialize the credentials (encryption key and password). 

    Args:
        app_name: str
            The name of the application.
        reintialize: bool
            Whether or not to reintialize the credentials.
        enable_passcode: bool
            Whether or not to enable the passcode.
    
    Returns:
        None
    """
    app_name = app_name.upper()
    # Check for credentials in the user environment variables.
    credentials = (
        user_environ(f'{app_name}_EMAIL') and
        user_environ(f'{app_name}_ENC_KEY') and 
        user_environ(f'{app_name}_PASSWD') and
        user_environ(f'{app_name}_LATLONG')
    )

    if not credentials or reintialize:
        # Generate key for Fernet encryption.
        key = Fernet.generate_key()

        email = input(f'Enter the email address for the {app_name} account: ')

        # Double encryption for storage using Fernet with an AES cipher and SHA256 hash.
        password = getpass.getpass(
            prompt=f'Enter your {app_name.lower()} password to double encrypt: '
        )

        latlong = input(f'Enter your latitude and longitude of your home location: ')

        # Add a passcode to the derived key for the SHA256 hash, if enabled.
        if enable_passcode:
            passcode = getpass.getpass(prompt=f'Please enter a passcode for the encryption key: ')
        else:
            passcode = ''

        # Encrypt password and add new user environment variables.
        enc_password = double_encrypt(key, password, passcode)
        enc_latlong = double_encrypt(key, latlong, passcode)
        add_user_environment(f'{app_name}_EMAIL', email)
        add_user_environment(f'{app_name}_ENC_KEY', key.decode())
        add_user_environment(f'{app_name}_PASSWD', enc_password)
        add_user_environment(f'{app_name}_LATLONG', enc_latlong)

def get_creds(
    app_name: str, 
    enable_passcode: bool = False
) -> Dict[str, str]:
    """
    Get the credentials for the `app_name` account.

    Args:
        app_name: str
            The name of the application.
        enable_passcode: bool
            Whether or not to enable the passcode.

    Returns:
        Dict[str, str]
            The credentials for the `app_name` account.
    """
    # Double decryption using Fernet with an AES cipher and SHA256 hash.
    app_name = app_name.upper()
    key = user_environ(f'{app_name}_ENC_KEY')

    # Get the passcode for the encryption key, if enabled.
    if enable_passcode:
        passcode = getpass.getpass(prompt=f'Enter the passcode: ')
    else:
        passcode = ''

    enc_password = user_environ(f'{app_name}_PASSWD')
    enc_latlong = user_environ(f'{app_name}_LATLONG')

    return {
        'username': user_environ(f'{app_name}_EMAIL'),
        'password': double_decrypt(key, enc_password, passcode),
        'latlong': eval(double_decrypt(key, enc_latlong, passcode))
    }

def double_encrypt(
    key: str,
    string: str,
    passcode: str = '',
) -> str:
    """
    Double encrypt a string using a key with SHA256 and AES.

    Args:
        key: str
            The key to use for encryption.
        string: str
            The string to encrypt.
        passcode: str
            The passcode to use for encryption.

    Returns:
        str
            The encrypted string.
    """
    return encrypt(gen_unique_key(passcode), Fernet(key).encrypt(string.encode()).decode())

def double_decrypt(
    key: str,
    enc_string: str,
    passcode: str = ''
) -> str:
    """
    Double decrypt a string using a key with SHA256 and AES.

    Args:
        key: str
            The key to use for decryption.
        enc_string: str
            The encrypted string to decrypt.
        passcode: str
            The passcode to use for decryption.

    Returns:
        str
            The decrypted string.
    """
    # First decryption with AES cipher and SHA256 hash using unique key.
    decrypt_pass1 = decrypt(gen_unique_key(passcode), enc_string)
    if not decrypt_pass1:
        raise ValueError("The pin code has been entered incorrectly or is required for the stored credentials.")

    # Second decryption with Fernet with generated key.
    return Fernet(key).decrypt(decrypt_pass1.encode()).decode()


def encrypt(
    key: str,
    source: str, 
) -> str:
    """
    Encrypt a string using a key with SHA256 and AES.

    Args:
        key: str
            The key to use for encryption.
        source: str
            The string to encrypt.
    
    Returns:
        str
            The encrypted string.
    """
    key = key.encode()
    source = source.encode()

    key = SHA256.new(key).digest()
    IV = Random.new().read(AES.block_size)
    encryptor = AES.new(key, AES.MODE_CBC, IV)

    padding = AES.block_size - len(source) % AES.block_size
    source += bytes([padding]) * padding 

    data = IV + encryptor.encrypt(source) 
    return base64.b64encode(data).decode("latin-1")

def decrypt(
    key: str,
    source: str, 
) -> str:
    """
    Decrypt a string using a key with SHA256 and AES.

    Args:
        key: str
            The key to use for decryption.
        source: str
            The string to decrypt.
    Returns:
        str
            The decrypted string.
    """
    key = key.encode()

    source = base64.b64decode(source.encode("latin-1"))

    key = SHA256.new(key).digest()
    IV = source[:AES.block_size] 

    decryptor = AES.new(key, AES.MODE_CBC, IV)
    data = decryptor.decrypt(source[AES.block_size:]) 
    padding = data[-1] 
    
    if data[-padding:] != bytes([padding]) * padding: 
        return False
    return data[:-padding].decode()

def gen_unique_key(
    passcode: str = ''
) -> str:
    """
    Generate unique key from PC UUID, username, and mac address.

    Args:
        passcode: str, optional
            A passcode to add to the key. Defaults to ''
    
    Returns:
        str
            The unique key.
    """
    # Get PC UUID from WMIC.
    uuid = (
        check_output('wmic csproduct get UUID')
        .decode()
        .replace(' ', '')
        .replace('\r', '')
        .split('\n')[1]
    )
    # Get current username.
    username = os.getlogin()
    # Get mac address.
    mac_addrr = str(hex(UUID.getnode()))

    # Obtain a unique key derived from the variables.
    return uuid + username + mac_addrr + passcode
