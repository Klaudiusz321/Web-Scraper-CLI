"""
Security utilities for the web scraper CLI.
"""
import os
import base64
import json
from typing import Dict, Any, Optional
from pathlib import Path
import ssl
import certifi
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from webscraper_cli.config import settings
from webscraper_cli.utils.logger import get_logger
from webscraper_cli.utils.exceptions import ConfigurationError

logger = get_logger("security")

# Credentials file location
CREDENTIALS_FILE = Path(settings.BASE_DIR) / "credentials" / "credentials.enc"
CREDENTIALS_FILE.parent.mkdir(exist_ok=True)

# Generate a key from password and salt
def _generate_key(password: str, salt: Optional[bytes] = None) -> tuple:
    """
    Generate an encryption key from a password and salt.
    
    Args:
        password: Password string
        salt: Optional salt bytes (generated if not provided)
        
    Returns:
        Tuple of (key, salt)
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt

def save_credentials(credentials: Dict[str, Any], master_password: str) -> None:
    """
    Encrypt and save credentials to file.
    
    Args:
        credentials: Dictionary of credentials to save
        master_password: Master password for encryption
    """
    try:
        # Generate key and salt
        key, salt = _generate_key(master_password)
        
        # Encrypt the credentials
        f = Fernet(key)
        credentials_bytes = json.dumps(credentials).encode()
        encrypted_data = f.encrypt(credentials_bytes)
        
        # Save to file
        with open(CREDENTIALS_FILE, 'wb') as file:
            file.write(salt + encrypted_data)
        
        logger.info(f"Credentials saved to {CREDENTIALS_FILE}")
    except Exception as e:
        logger.error(f"Failed to save credentials: {str(e)}")
        raise ConfigurationError(f"Failed to save credentials: {str(e)}")

def load_credentials(master_password: str) -> Dict[str, Any]:
    """
    Load and decrypt credentials from file.
    
    Args:
        master_password: Master password for decryption
        
    Returns:
        Dictionary of credentials
    """
    if not CREDENTIALS_FILE.exists():
        logger.warning(f"Credentials file does not exist: {CREDENTIALS_FILE}")
        return {}
        
    try:
        # Read encrypted data
        with open(CREDENTIALS_FILE, 'rb') as file:
            file_data = file.read()
            
        # Extract salt (first 16 bytes) and encrypted data
        salt = file_data[:16]
        encrypted_data = file_data[16:]
        
        # Generate key from password and salt
        key, _ = _generate_key(master_password, salt)
        
        # Decrypt the data
        f = Fernet(key)
        decrypted_data = f.decrypt(encrypted_data)
        
        return json.loads(decrypted_data.decode())
    except Exception as e:
        logger.error(f"Failed to load credentials: {str(e)}")
        raise ConfigurationError(f"Failed to load credentials: {str(e)}")

def get_ssl_context() -> ssl.SSLContext:
    """
    Get an SSL context configured for secure connections.
    
    Returns:
        Configured SSL context
    """
    if not settings.SSL_VERIFY:
        logger.warning("SSL verification is disabled. This is not recommended for production use.")
        return ssl._create_unverified_context()
    
    context = ssl.create_default_context(cafile=certifi.where())
    # Set secure protocols
    context.options |= ssl.OP_NO_SSLv2
    context.options |= ssl.OP_NO_SSLv3
    context.options |= ssl.OP_NO_TLSv1
    context.options |= ssl.OP_NO_TLSv1_1
    
    # Set secure ciphers
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20')
    
    return context 