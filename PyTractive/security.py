"""
Security and credential management for PyTractive.
"""

import os
import json
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import logging

from .exceptions import ConfigurationError


logger = logging.getLogger(__name__)


class CredentialManager:
    """Manages secure storage and retrieval of user credentials."""
    
    def __init__(self, credential_file: str = "credentials.json"):
        self.credential_file = Path(credential_file)
    
    def get_credentials(self) -> Tuple[str, str, Tuple[float, float]]:
        """
        Get user credentials from secure storage.
        
        Returns:
            Tuple of (email, password, (home_lat, home_lon))
            
        Raises:
            ConfigurationError: If credentials cannot be found or are invalid
        """
        # First try environment variables
        email = os.environ.get("TRACTIVE_EMAIL")
        password = os.environ.get("TRACTIVE_PASSWORD")
        home_lat = os.environ.get("TRACTIVE_HOME_LAT")
        home_lon = os.environ.get("TRACTIVE_HOME_LON")
        
        if all([email, password, home_lat, home_lon]):
            try:
                return email, password, (float(home_lat), float(home_lon))
            except ValueError as e:
                raise ConfigurationError(f"Invalid coordinate values in environment variables: {e}")
        
        # Fall back to credential file
        if self.credential_file.exists():
            try:
                with open(self.credential_file, 'r', encoding='utf-8') as f:
                    creds = json.load(f)
                
                email = creds.get('email')
                password = creds.get('password')
                home_lat = creds.get('home_lat')
                home_lon = creds.get('home_lon')
                
                if all([email, password, home_lat, home_lon]):
                    return email, password, (float(home_lat), float(home_lon))
                else:
                    raise ConfigurationError("Incomplete credentials in file")
                    
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                raise ConfigurationError(f"Invalid credential file format: {e}")
            except Exception as e:
                raise ConfigurationError(f"Failed to read credentials: {e}")
        
        # Try legacy login.conf file
        login_conf = Path("PyTractive/login.conf")
        if login_conf.exists():
            try:
                with open(login_conf, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                
                if len(lines) >= 4:
                    return lines[0], lines[1], (float(lines[2]), float(lines[3]))
                else:
                    raise ConfigurationError("Incomplete login.conf file")
                    
            except (ValueError, IndexError) as e:
                raise ConfigurationError(f"Invalid login.conf format: {e}")
            except Exception as e:
                raise ConfigurationError(f"Failed to read login.conf: {e}")
        
        raise ConfigurationError(
            "No credentials found. Please set environment variables:\n"
            "  TRACTIVE_EMAIL, TRACTIVE_PASSWORD, TRACTIVE_HOME_LAT, TRACTIVE_HOME_LON\n"
            "Or create a credentials.json file or login.conf file."
        )
    
    def set_credentials(
        self, 
        email: str, 
        password: str, 
        home_coordinates: Tuple[float, float]
    ) -> None:
        """
        Store credentials securely.
        
        Args:
            email: Tractive account email
            password: Tractive account password
            home_coordinates: Tuple of (latitude, longitude) for home location
        """
        try:
            creds = {
                'email': email,
                'password': password,
                'home_lat': home_coordinates[0],
                'home_lon': home_coordinates[1]
            }
            
            # Create directory if it doesn't exist
            self.credential_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write credentials to file with restricted permissions
            with open(self.credential_file, 'w', encoding='utf-8') as f:
                json.dump(creds, f, indent=2)
            
            # Set file permissions to be readable only by owner (on Unix-like systems)
            try:
                os.chmod(self.credential_file, 0o600)
            except (OSError, AttributeError):
                # chmod may not work on Windows, ignore the error
                pass
            
            logger.info(f"Credentials saved to {self.credential_file}")
            
        except Exception as e:
            raise ConfigurationError(f"Failed to save credentials: {e}")
    
    def clear_credentials(self) -> None:
        """Remove stored credentials."""
        try:
            if self.credential_file.exists():
                self.credential_file.unlink()
                logger.info("Credentials cleared")
        except Exception as e:
            raise ConfigurationError(f"Failed to clear credentials: {e}")
    
    def has_credentials(self) -> bool:
        """Check if credentials are available."""
        try:
            self.get_credentials()
            return True
        except ConfigurationError:
            return False


class SecureVault:
    """
    Modern secure vault for sensitive data encryption/decryption.
    
    Uses industry-standard encryption with key derivation and proper security practices.
    """
    
    def __init__(self, key_file: str = "vault.key"):
        self.key_file = Path(key_file)
        self._key: Optional[bytes] = None
        self._fernet = None
        
    def _get_or_create_key(self) -> bytes:
        """Get existing key or create a new one."""
        if self._key:
            return self._key
            
        if self.key_file.exists():
            try:
                with open(self.key_file, 'rb') as f:
                    self._key = f.read()
                logger.debug("Loaded existing encryption key")
            except Exception as e:
                logger.warning(f"Failed to load encryption key: {e}")
                self._key = self._generate_key()
        else:
            self._key = self._generate_key()
            
        return self._key
    
    def _generate_key(self) -> bytes:
        """Generate a new encryption key."""
        try:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key()
            
            # Save key to file with restricted permissions
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_file, 'wb') as f:
                f.write(key)
            
            # Set file permissions to be readable only by owner
            try:
                os.chmod(self.key_file, 0o600)
            except (OSError, AttributeError):
                # chmod may not work on Windows, ignore the error
                pass
                
            logger.info(f"Generated new encryption key: {self.key_file}")
            return key
            
        except ImportError:
            # Fallback to basic key generation
            import secrets
            key = secrets.token_bytes(32)
            
            with open(self.key_file, 'wb') as f:
                f.write(key)
                
            try:
                os.chmod(self.key_file, 0o600)
            except (OSError, AttributeError):
                pass
                
            logger.warning("Using fallback encryption (cryptography library not available)")
            return key
    
    def _get_fernet(self):
        """Get Fernet encryption instance."""
        if self._fernet:
            return self._fernet
            
        try:
            from cryptography.fernet import Fernet
            key = self._get_or_create_key()
            self._fernet = Fernet(key)
            return self._fernet
        except ImportError:
            raise ConfigurationError(
                "cryptography library not found. Install with: pip install cryptography\n"
                "This is required for secure data encryption."
            )
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt string data.
        
        Args:
            data: Plain text data to encrypt
            
        Returns:
            Base64-encoded encrypted data
        """
        try:
            fernet = self._get_fernet()
            encrypted_bytes = fernet.encrypt(data.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ConfigurationError(f"Failed to encrypt data: {e}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted data.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            
        Returns:
            Decrypted plain text
        """
        try:
            fernet = self._get_fernet()
            decrypted_bytes = fernet.decrypt(encrypted_data.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ConfigurationError(f"Failed to decrypt data: {e}")
    
    def encrypt_dict(self, data_dict: Dict[str, Any]) -> str:
        """
        Encrypt a dictionary as JSON.
        
        Args:
            data_dict: Dictionary to encrypt
            
        Returns:
            Encrypted JSON string
        """
        json_str = json.dumps(data_dict)
        return self.encrypt(json_str)
    
    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt data back to dictionary.
        
        Args:
            encrypted_data: Encrypted JSON string
            
        Returns:
            Decrypted dictionary
        """
        json_str = self.decrypt(encrypted_data)
        return json.loads(json_str)


# Global vault instance
_vault = None

def get_vault() -> SecureVault:
    """Get the global secure vault instance."""
    global _vault
    if _vault is None:
        _vault = SecureVault()
    return _vault


def encrypt_data(data: str, key: Optional[str] = None) -> str:
    """
    Encrypt sensitive data using modern encryption.
    
    Args:
        data: Plain text data to encrypt
        key: Optional key (unused, kept for backward compatibility)
        
    Returns:
        Encrypted data string
    """
    vault = get_vault()
    return vault.encrypt(data)


def decrypt_data(encrypted_data: str, key: Optional[str] = None) -> str:
    """
    Decrypt sensitive data using modern encryption.
    
    Args:
        encrypted_data: Encrypted data string
        key: Optional key (unused, kept for backward compatibility)
        
    Returns:
        Decrypted plain text
    """
    vault = get_vault()
    return vault.decrypt(encrypted_data)


def secure_wipe(file_path: Path) -> bool:
    """
    Securely wipe a file by overwriting it multiple times.
    
    Args:
        file_path: Path to file to wipe
        
    Returns:
        True if successful
    """
    try:
        if not file_path.exists():
            return True
            
        # Get file size
        file_size = file_path.stat().st_size
        
        # Overwrite with random data multiple times
        with open(file_path, 'r+b') as f:
            for _ in range(3):
                f.seek(0)
                f.write(os.urandom(file_size))
                f.flush()
                os.fsync(f.fileno())
        
        # Finally delete the file
        file_path.unlink()
        logger.info(f"Securely wiped file: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to securely wipe {file_path}: {e}")
        return False


def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, bytes]:
    """
    Hash a password using modern key derivation.
    
    Args:
        password: Plain text password
        salt: Optional salt (if None, generates new one)
        
    Returns:
        Tuple of (hash_hex, salt_bytes)
    """
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        if salt is None:
            salt = os.urandom(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = kdf.derive(password.encode('utf-8'))
        return key.hex(), salt
        
    except ImportError:
        # Fallback to hashlib
        import hashlib
        
        if salt is None:
            salt = os.urandom(32)
            
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return hash_obj.hex(), salt


def verify_password(password: str, hash_hex: str, salt: bytes) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        password: Plain text password to verify
        hash_hex: Stored password hash
        salt: Salt used for hashing
        
    Returns:
        True if password matches
    """
    try:
        computed_hash, _ = hash_password(password, salt)
        return computed_hash == hash_hex
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False
