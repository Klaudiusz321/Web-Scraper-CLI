"""
Central configuration settings for the web scraper.
"""
import os
from pathlib import Path
import logging
from typing import Dict, Any, Optional

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = BASE_DIR / "exported_data"
API_EXPORT_DIR = BASE_DIR / "exported_api"
DATABASE_DIR = BASE_DIR / "database"

# Ensure directories exist
EXPORT_DIR.mkdir(exist_ok=True)
API_EXPORT_DIR.mkdir(exist_ok=True)
DATABASE_DIR.mkdir(exist_ok=True)

# Database settings
DB_PATH = DATABASE_DIR / "scraper_data.db"
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
MONGO_DB = os.environ.get('MONGO_DB', 'webscraper')
MONGO_COLLECTION = os.environ.get('MONGO_COLLECTION', 'scraped_data')

# Selenium/Scraper settings
BROWSER_SETTINGS = {
    "headless": True,
    "disable_gpu": True, 
    "no_sandbox": True,
    "disable_dev_shm_usage": True,
    "disable_extensions": True,
    "window_size": "1920,1080"
}

# Timeout settings (in seconds)
TIMEOUTS = {
    "page_load": 30,
    "element_wait": 10,
    "captcha_wait": 20,
    "api_request": 15
}

# Logging configuration
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FILE = BASE_DIR / "logs" / "webscraper.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# API Client settings
DEFAULT_HEADERS = {
    "User-Agent": "WebScraperCLI/1.0"
}

# Export settings
DEFAULT_EXPORT_FORMAT = "json"

# Captcha settings
CAPTCHA_SETTINGS = {
    "auto_solve": True,
    "service": os.environ.get('CAPTCHA_SERVICE', 'local'),
    "api_key": os.environ.get('CAPTCHA_API_KEY', ''),
    "timeout": 30
}

# Security settings
SSL_VERIFY = True
USE_RATE_LIMITING = True
MAX_REQUESTS_PER_MINUTE = 10

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

def get_config() -> Dict[str, Any]:
    """Get the complete configuration dictionary."""
    return {
        "base_dir": str(BASE_DIR),
        "export_dir": str(EXPORT_DIR),
        "api_export_dir": str(API_EXPORT_DIR),
        "database_dir": str(DATABASE_DIR),
        "db_path": str(DB_PATH),
        "mongo_uri": MONGO_URI,
        "mongo_db": MONGO_DB,
        "mongo_collection": MONGO_COLLECTION,
        "browser_settings": BROWSER_SETTINGS,
        "timeouts": TIMEOUTS,
        "log_level": LOG_LEVEL,
        "log_file": str(LOG_FILE),
        "log_format": LOG_FORMAT,
        "default_headers": DEFAULT_HEADERS,
        "default_export_format": DEFAULT_EXPORT_FORMAT,
        "captcha_settings": CAPTCHA_SETTINGS,
        "ssl_verify": SSL_VERIFY,
        "use_rate_limiting": USE_RATE_LIMITING,
        "max_requests_per_minute": MAX_REQUESTS_PER_MINUTE,
        "max_retries": MAX_RETRIES,
        "retry_delay": RETRY_DELAY
    }

def get_setting(key: str, default: Optional[Any] = None) -> Any:
    """
    Get a specific setting by key.
    
    Args:
        key: The configuration key to retrieve
        default: Optional default value if key doesn't exist
        
    Returns:
        The configuration value or default if not found
    """
    config = get_config()
    return config.get(key, default) 