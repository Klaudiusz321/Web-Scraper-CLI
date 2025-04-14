"""
Custom exceptions for the web scraper.
"""
from typing import Optional, Dict, Any

class WebScraperException(Exception):
    """Base exception for all web scraper exceptions."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ScraperNavigationError(WebScraperException):
    """Exception raised when navigation fails."""
    pass


class ElementNotFoundError(WebScraperException):
    """Exception raised when an element is not found."""
    pass


class CaptchaError(WebScraperException):
    """Exception raised when a CAPTCHA cannot be solved."""
    pass


class APIError(WebScraperException):
    """Exception raised when an API request fails."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response_text: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(message, details)


class DatabaseError(WebScraperException):
    """Exception raised when a database operation fails."""
    pass


class ExportError(WebScraperException):
    """Exception raised when an export operation fails."""
    pass


class RateLimitError(WebScraperException):
    """Exception raised when rate limiting is enforced."""
    pass


class ConfigurationError(WebScraperException):
    """Exception raised when there's a configuration issue."""
    pass 