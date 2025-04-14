"""
Rate limiter utility to enforce request rate limits.
"""
import time
from functools import wraps
from typing import Callable, Dict, Any, Optional
from collections import deque

from webscraper_cli.config import settings
from webscraper_cli.utils.exceptions import RateLimitError
from webscraper_cli.utils.logger import get_logger

logger = get_logger("rate_limiter")

class RateLimiter:
    """
    Rate limiter to enforce request limits.
    """
    
    def __init__(self, max_requests: int = None, time_window: int = 60):
        """
        Initialize the rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in the time window
            time_window: Time window in seconds (default: 60 seconds)
        """
        self.max_requests = max_requests or settings.MAX_REQUESTS_PER_MINUTE
        self.time_window = time_window
        self.request_timestamps = deque()
    
    def _cleanup_old_requests(self) -> None:
        """Remove request timestamps that are outside the time window."""
        current_time = time.time()
        while self.request_timestamps and current_time - self.request_timestamps[0] > self.time_window:
            self.request_timestamps.popleft()
    
    def can_make_request(self) -> bool:
        """
        Check if a request can be made without exceeding the rate limit.
        
        Returns:
            True if request is allowed, False otherwise
        """
        if not settings.USE_RATE_LIMITING:
            return True
            
        self._cleanup_old_requests()
        return len(self.request_timestamps) < self.max_requests
    
    def record_request(self) -> None:
        """Record that a request was made."""
        self.request_timestamps.append(time.time())
    
    def wait_if_needed(self) -> float:
        """
        Wait if necessary to respect rate limits.
        
        Returns:
            Time waited in seconds
        """
        if not settings.USE_RATE_LIMITING:
            return 0.0
            
        self._cleanup_old_requests()
        
        # If we haven't reached the limit, no need to wait
        if len(self.request_timestamps) < self.max_requests:
            return 0.0
            
        # Calculate how long to wait
        wait_time = self.time_window - (time.time() - self.request_timestamps[0])
        if wait_time > 0:
            logger.debug(f"Rate limit reached. Waiting {wait_time:.2f} seconds")
            time.sleep(wait_time)
            return wait_time
            
        return 0.0


# Global rate limiter instance
_rate_limiter = RateLimiter()

def rate_limited(func: Callable) -> Callable:
    """
    Decorator to apply rate limiting to a function.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function with rate limiting
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _rate_limiter.can_make_request():
            wait_time = _rate_limiter.wait_if_needed()
            logger.info(f"Rate limited request - waited {wait_time:.2f}s")
        
        _rate_limiter.record_request()
        return func(*args, **kwargs)
    
    return wrapper 