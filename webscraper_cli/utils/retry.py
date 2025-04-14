"""
Retry utility for handling transient failures.
"""
import time
import functools
import random
from typing import Callable, Type, Tuple, Optional, List, Any, Union

from webscraper_cli.config import settings
from webscraper_cli.utils.logger import get_logger

logger = get_logger("retry")

def retry(
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    max_retries: Optional[int] = None,
    delay: Optional[float] = None,
    backoff: float = 2.0,
    jitter: bool = True
) -> Callable:
    """
    Retry decorator to retry functions that might fail with transient errors.
    
    Args:
        exceptions: Exception or tuple of exceptions to catch
        max_retries: Maximum number of retries (default from settings)
        delay: Initial delay between retries in seconds (default from settings)
        backoff: Backoff multiplier (default: 2.0)
        jitter: Whether to add randomness to delay (default: True)
        
    Returns:
        Decorator function
    """
    max_retries = max_retries if max_retries is not None else settings.MAX_RETRIES
    delay = delay if delay is not None else settings.RETRY_DELAY
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retry_count = 0
            current_delay = delay
            
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        logger.warning(f"Maximum retries ({max_retries}) exceeded. Last error: {str(e)}")
                        raise
                    
                    # Add jitter to avoid thundering herd problem
                    sleep_time = current_delay
                    if jitter:
                        sleep_time = sleep_time * (0.5 + random.random())
                    
                    logger.info(
                        f"Retry {retry_count}/{max_retries} for {func.__name__} "
                        f"after error: {str(e)}. Waiting {sleep_time:.2f}s"
                    )
                    
                    time.sleep(sleep_time)
                    current_delay *= backoff
        
        return wrapper
    
    return decorator 