"""
Core web scraper implementation.
"""
from typing import Dict, Any, Optional, List, Tuple
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time

from webscraper_cli.config import settings
from webscraper_cli.utils.logger import LoggerMixin
from webscraper_cli.utils.exceptions import ScraperNavigationError, ElementNotFoundError
from webscraper_cli.utils.retry import retry
from webscraper_cli.utils.rate_limiter import rate_limited

class WebScraper(LoggerMixin):
    """
    Core web scraper class that handles browser automation and navigation.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the web scraper with browser settings.
        
        Args:
            config: Optional configuration override (default: use settings module)
        """
        self.config = config or settings.get_config()
        self.browser_settings = self.config.get('browser_settings', {})
        self.timeouts = self.config.get('timeouts', {})
        
        self.logger.info("Initializing WebScraper")
        self._setup_browser()
        
        # Store current URL for reference
        self.current_url = None
        
        # Initialize captcha solver if available
        self.captcha_solver = None
        if self.config.get('captcha_settings', {}).get('auto_solve', True):
            try:
                from webscraper_cli.scraper.core.captcha import CaptchaSolver
                self.captcha_solver = CaptchaSolver(self.driver, self.config.get('captcha_settings', {}))
                self.logger.info("CAPTCHA solver initialized")
            except ImportError:
                self.logger.warning("CAPTCHA solver module not available")
    
    def _setup_browser(self) -> None:
        """Set up the browser with configuration options."""
        options = webdriver.ChromeOptions()
        
        # Apply browser settings from config
        if self.browser_settings.get('headless', True):
            options.add_argument("--headless")
        
        if self.browser_settings.get('disable_gpu', True):
            options.add_argument("--disable-gpu")
            
        if self.browser_settings.get('no_sandbox', True):
            options.add_argument("--no-sandbox")
            
        if self.browser_settings.get('disable_dev_shm_usage', True):
            options.add_argument("--disable-dev-shm-usage")
        
        if self.browser_settings.get('disable_extensions', True):
            options.add_argument("--disable-extensions")
            
        window_size = self.browser_settings.get('window_size', "1920,1080")
        options.add_argument(f"--window-size={window_size}")
        
        # Add additional arguments from config
        additional_args = self.browser_settings.get('additional_args', [])
        for arg in additional_args:
            options.add_argument(arg)
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.logger.info("Chrome browser initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome browser: {str(e)}")
            raise RuntimeError(f"Failed to initialize Chrome browser: {str(e)}")
    
    @rate_limited
    @retry(exceptions=(TimeoutException, ConnectionError))
    def navigate(self, url: str) -> 'WebScraper':
        """
        Navigate to specified URL and handle any CAPTCHAs encountered.
        
        Args:
            url: URL to navigate to
            
        Returns:
            Self for method chaining
            
        Raises:
            ScraperNavigationError: If navigation fails
        """
        self.logger.info(f"Navigating to {url}")
        
        try:
            self.driver.get(url)
            self.current_url = url
            
            # Wait for page to load
            self._wait_for_page_load()
            
            # Check for and solve CAPTCHA if auto_solve is enabled
            if self.captcha_solver and self.config.get('captcha_settings', {}).get('auto_solve', True):
                captcha_info = self.captcha_solver.detect_captcha()
                if captcha_info:
                    self.logger.info(f"CAPTCHA detected on {url} - attempting to solve automatically")
                    solved = self.captcha_solver.solve_captcha(captcha_info)
                    if solved:
                        self.logger.info("CAPTCHA solved successfully")
                        # Wait for page to load after CAPTCHA solution
                        time.sleep(3)
                        self._wait_for_page_load()
                    else:
                        self.logger.warning("Failed to solve CAPTCHA automatically")
            
            self.logger.debug(f"Navigation to {url} successful")
            return self
            
        except Exception as e:
            error_msg = f"Failed to navigate to {url}: {str(e)}"
            self.logger.error(error_msg)
            raise ScraperNavigationError(error_msg, {"url": url})
    
    def _wait_for_page_load(self, timeout: Optional[int] = None) -> None:
        """
        Wait for page to load by checking document.readyState.
        
        Args:
            timeout: Timeout in seconds (default from config)
        """
        timeout = timeout or self.timeouts.get('page_load', 30)
        
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            self.logger.warning(f"Page load timeout after {timeout}s")
    
    def element_exists(self, css_selector: str) -> bool:
        """
        Check if element exists on the page.
        
        Args:
            css_selector: CSS selector to find
            
        Returns:
            True if element exists, False otherwise
        """
        try:
            self.driver.find_element(By.CSS_SELECTOR, css_selector)
            return True
        except NoSuchElementException:
            return False
    
    @retry(exceptions=TimeoutException)
    def wait_for_element(self, by: By, identifier: str, timeout: Optional[int] = None) -> Any:
        """
        Wait for element to appear on page.
        
        Args:
            by: Selenium By locator
            identifier: Element identifier
            timeout: Timeout in seconds (default from config)
            
        Returns:
            The found element
            
        Raises:
            ElementNotFoundError: If the element is not found
        """
        timeout = timeout or self.timeouts.get('element_wait', 10)
        
        try:
            self.logger.debug(f"Waiting for element: {by}={identifier}")
            wait = WebDriverWait(self.driver, timeout)
            element = wait.until(EC.presence_of_element_located((by, identifier)))
            return element
        except TimeoutException as e:
            error_msg = f"Element not found: {by}={identifier} (timeout: {timeout}s)"
            self.logger.error(error_msg)
            raise ElementNotFoundError(error_msg, {"by": str(by), "identifier": identifier})
    
    def execute_js(self, script: str, *args) -> Any:
        """
        Execute JavaScript code on page.
        
        Args:
            script: JavaScript code to execute
            *args: Arguments to pass to the script
            
        Returns:
            Result of JavaScript execution
        """
        self.logger.debug(f"Executing JavaScript: {script[:50]}{'...' if len(script) > 50 else ''}")
        return self.driver.execute_script(script, *args)
    
    @rate_limited
    def click(self, css_selector: str) -> 'WebScraper':
        """
        Click on element specified by CSS selector.
        
        Args:
            css_selector: CSS selector to click
            
        Returns:
            Self for method chaining
            
        Raises:
            ElementNotFoundError: If the element is not found
        """
        try:
            self.logger.info(f"Clicking element: {css_selector}")
            element = self.driver.find_element(By.CSS_SELECTOR, css_selector)
            element.click()
            
            # Wait for page changes after click
            time.sleep(1)
            
            # Check for CAPTCHA after clicking
            if self.captcha_solver and self.config.get('captcha_settings', {}).get('auto_solve', True):
                captcha_info = self.captcha_solver.detect_captcha()
                if captcha_info:
                    self.logger.info("CAPTCHA detected after clicking - attempting to solve")
                    self.captcha_solver.solve_captcha(captcha_info)
            
            return self
            
        except NoSuchElementException as e:
            error_msg = f"Element not found for click: {css_selector}"
            self.logger.error(error_msg)
            raise ElementNotFoundError(error_msg, {"selector": css_selector})
        except Exception as e:
            self.logger.error(f"Error clicking element {css_selector}: {str(e)}")
            raise
    
    def get_html(self) -> str:
        """
        Get page HTML source.
        
        Returns:
            HTML source code
        """
        self.logger.debug("Getting page HTML source")
        return self.driver.page_source
    
    def get_text(self, css_selector: str) -> str:
        """
        Get text from element specified by CSS selector.
        
        Args:
            css_selector: CSS selector
            
        Returns:
            Element text content
            
        Raises:
            ElementNotFoundError: If the element is not found
        """
        try:
            self.logger.debug(f"Getting text from selector: {css_selector}")
            element = self.driver.find_element(By.CSS_SELECTOR, css_selector)
            return element.text
        except NoSuchElementException:
            error_msg = f"Element not found for get_text: {css_selector}"
            self.logger.error(error_msg)
            raise ElementNotFoundError(error_msg, {"selector": css_selector})
    
    def get_attribute(self, css_selector: str, attribute: str) -> Optional[str]:
        """
        Get attribute value from element specified by CSS selector.
        
        Args:
            css_selector: CSS selector
            attribute: Attribute name to get
            
        Returns:
            Attribute value or None if not found
            
        Raises:
            ElementNotFoundError: If the element is not found
        """
        try:
            self.logger.debug(f"Getting attribute '{attribute}' from selector: {css_selector}")
            element = self.driver.find_element(By.CSS_SELECTOR, css_selector)
            return element.get_attribute(attribute)
        except NoSuchElementException:
            error_msg = f"Element not found for get_attribute: {css_selector}"
            self.logger.error(error_msg)
            raise ElementNotFoundError(error_msg, {"selector": css_selector, "attribute": attribute})
    
    def login(self, login_url: str, username: str, password: str) -> 'WebScraper':
        """
        Login to website with credentials and handle any CAPTCHAs.
        
        Args:
            login_url: URL of login page
            username: Username/email for login
            password: Password for login
            
        Returns:
            Self for method chaining
        """
        self.navigate(login_url)
        
        # Common selectors for login forms
        username_selectors = ["input[name='username']", "input[name='email']", "input[name='login']", 
                              "input[id='username']", "input[id='email']"]
        password_selectors = ["input[name='password']", "input[id='password']", "input[type='password']"]
        submit_selectors = ["input[type='submit']", "button[type='submit']", 
                            "button:contains('Login')", "button:contains('Sign in')"]
        
        # Try to find and fill username field
        username_filled = False
        for selector in username_selectors:
            if self.element_exists(selector):
                try:
                    username_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    username_field.clear()
                    username_field.send_keys(username)
                    username_filled = True
                    self.logger.debug(f"Username filled with selector: {selector}")
                    break
                except Exception as e:
                    self.logger.warning(f"Failed to fill username with selector {selector}: {str(e)}")
        
        if not username_filled:
            self.logger.warning("Could not find username field with common selectors")
        
        # Try to find and fill password field
        password_filled = False
        for selector in password_selectors:
            if self.element_exists(selector):
                try:
                    password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    password_field.clear()
                    password_field.send_keys(password)
                    password_filled = True
                    self.logger.debug(f"Password filled with selector: {selector}")
                    break
                except Exception as e:
                    self.logger.warning(f"Failed to fill password with selector {selector}: {str(e)}")
        
        if not password_filled:
            self.logger.warning("Could not find password field with common selectors")
        
        # Check for CAPTCHA before submitting
        if self.captcha_solver:
            captcha_info = self.captcha_solver.detect_captcha()
            if captcha_info:
                self.logger.info("CAPTCHA detected on login form - attempting to solve")
                self.captcha_solver.solve_captcha(captcha_info)
        
        # Click submit button
        submit_clicked = False
        for selector in submit_selectors:
            if self.element_exists(selector):
                try:
                    self.click(selector)
                    submit_clicked = True
                    self.logger.debug(f"Login form submitted with selector: {selector}")
                    break
                except Exception as e:
                    self.logger.warning(f"Failed to click submit button with selector {selector}: {str(e)}")
        
        if not submit_clicked:
            self.logger.warning("Could not find submit button with common selectors")
        
        # Check for CAPTCHA after submission
        time.sleep(2)  # Wait for possible CAPTCHA
        if self.captcha_solver:
            captcha_info = self.captcha_solver.detect_captcha()
            if captcha_info:
                self.logger.info("CAPTCHA detected after login submission - attempting to solve")
                self.captcha_solver.solve_captcha(captcha_info)
        
        return self
    
    def close(self) -> None:
        """Close browser and clean up resources."""
        self.logger.info("Closing WebScraper browser")
        try:
            self.driver.quit()
        except Exception as e:
            self.logger.warning(f"Error closing browser: {str(e)}")
    
    def __enter__(self) -> 'WebScraper':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with clean up."""
        self.close() 