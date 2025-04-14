"""
Logging configuration for the web scraper.
"""
import logging
import sys
from pathlib import Path
from typing import Optional

from webscraper_cli.config import settings

# Create logs directory if it doesn't exist
logs_dir = Path(settings.BASE_DIR) / "logs"
logs_dir.mkdir(exist_ok=True)

def get_logger(name: str, log_level: Optional[str] = None) -> logging.Logger:
    """
    Get a logger with the specified name and configuration.
    
    Args:
        name: The name of the logger
        log_level: Optional log level to override the default
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Set log level from config or parameter
    level = log_level or settings.LOG_LEVEL
    logger.setLevel(getattr(logging, level))
    
    # Avoid adding duplicate handlers
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))
        logger.addHandler(console_handler)
        
        # File handler
        file_handler = logging.FileHandler(settings.LOG_FILE)
        file_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))
        logger.addHandler(file_handler)
    
    return logger

class LoggerMixin:
    """
    Mixin class to add logging capabilities to any class.
    """
    
    @property
    def logger(self) -> logging.Logger:
        """
        Get the logger for this class.
        
        Returns:
            Logger instance with the class name
        """
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger 