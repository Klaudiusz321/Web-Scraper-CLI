"""
CAPTCHA detection and solving mechanisms.
"""
from typing import Dict, Any, Optional, List, Tuple, Union
import time
import re
import base64
import io
import os
from PIL import Image
import cv2
import numpy as np
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from webscraper_cli.config import settings
from webscraper_cli.utils.logger import LoggerMixin
from webscraper_cli.utils.exceptions import CaptchaError
from webscraper_cli.utils.retry import retry
from webscraper_cli.utils.security import load_credentials

class CaptchaSolver(LoggerMixin):
    """
    Handles detection and solving of various types of CAPTCHAs.
    """
    
    # Common CAPTCHA patterns
    CAPTCHA_PATTERNS = {
        # reCAPTCHA v2
        'recaptcha_v2': {
            'iframe': 'iframe[src*="recaptcha"]',
            'checkbox': 'div.recaptcha-checkbox-border',
            'image_challenge': 'div.rc-imageselect-desc'
        },
        # hCaptcha
        'hcaptcha': {
            'iframe': 'iframe[src*="hcaptcha.com"]',
            'checkbox': '#checkbox',
            'challenge': '.challenge-container'
        },
        # Simple image captcha
        'image_captcha': {
            'image': 'img[alt*="captcha"], img[id*="captcha"], img[class*="captcha"], img[src*="captcha"]',
            'input': 'input[name*="captcha"], input[id*="captcha"], input[class*="captcha"]'
        },
        # Text-based captcha
        'text_captcha': {
            'question': '.captcha-question, #captcha-question, div[class*="captcha-question"]',
            'input': 'input[name*="captcha"], input[id*="captcha"]'
        }
    }
    
    def __init__(self, driver, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the CAPTCHA solver.
        
        Args:
            driver: Selenium WebDriver instance
            config: Optional configuration override (default: use settings module)
        """
        self.driver = driver
        self.config = config or settings.get_config().get('captcha_settings', {})
        self.timeout = self.config.get('timeout', 30)
        self.service = self.config.get('service', 'local')
        self.api_key = self.config.get('api_key', '') or os.environ.get('CAPTCHA_API_KEY', '')
        
        # Try to load API key from credentials if not in config
        if not self.api_key and self.service != 'local':
            try:
                master_password = os.environ.get('MASTER_PASSWORD', '')
                if master_password:
                    credentials = load_credentials(master_password)
                    self.api_key = credentials.get('captcha_api_key', '')
            except Exception as e:
                self.logger.warning(f"Failed to load CAPTCHA API key from credentials: {str(e)}")
    
    def detect_captcha(self) -> Optional[Dict[str, Any]]:
        """
        Detect if a CAPTCHA is present on the current page.
        
        Returns:
            Dictionary with CAPTCHA information or None if not detected
        """
        self.logger.debug("Detecting CAPTCHA on current page")
        
        # Check for reCAPTCHA v2
        if self._element_exists(self.CAPTCHA_PATTERNS['recaptcha_v2']['iframe']):
            self.logger.info("Detected reCAPTCHA v2")
            return {'type': 'recaptcha_v2', 'iframe': self.CAPTCHA_PATTERNS['recaptcha_v2']['iframe']}
        
        # Check for hCaptcha
        if self._element_exists(self.CAPTCHA_PATTERNS['hcaptcha']['iframe']):
            self.logger.info("Detected hCaptcha")
            return {'type': 'hcaptcha', 'iframe': self.CAPTCHA_PATTERNS['hcaptcha']['iframe']}
        
        # Check for image captcha
        if self._element_exists(self.CAPTCHA_PATTERNS['image_captcha']['image']):
            self.logger.info("Detected image CAPTCHA")
            image_selector = self.CAPTCHA_PATTERNS['image_captcha']['image']
            input_selector = self.CAPTCHA_PATTERNS['image_captcha']['input']
            return {
                'type': 'image_captcha',
                'image_selector': image_selector,
                'input_selector': self._find_existing_selector(input_selector)
            }
        
        # Check for text captcha
        if self._element_exists(self.CAPTCHA_PATTERNS['text_captcha']['question']):
            self.logger.info("Detected text CAPTCHA")
            question_selector = self.CAPTCHA_PATTERNS['text_captcha']['question']
            input_selector = self.CAPTCHA_PATTERNS['text_captcha']['input']
            return {
                'type': 'text_captcha',
                'question_selector': question_selector,
                'input_selector': self._find_existing_selector(input_selector)
            }
        
        # Also check generic patterns
        if re.search(r'captcha', self.driver.page_source, re.IGNORECASE):
            self.logger.info("Detected possible CAPTCHA (string match)")
            return {'type': 'unknown', 'detected_by': 'string_match'}
        
        return None
    
    def _element_exists(self, selector: str) -> bool:
        """Check if element exists on the current page."""
        try:
            self.driver.find_element(By.CSS_SELECTOR, selector)
            return True
        except NoSuchElementException:
            return False
    
    def _find_existing_selector(self, selectors: str) -> Optional[str]:
        """Find the first existing selector from a comma-separated list."""
        for selector in selectors.split(','):
            selector = selector.strip()
            if self._element_exists(selector):
                return selector
        return None
    
    def solve_captcha(self, captcha_info: Dict[str, Any]) -> bool:
        """
        Attempt to solve the detected CAPTCHA.
        
        Args:
            captcha_info: Dictionary with CAPTCHA information from detect_captcha()
            
        Returns:
            True if solved successfully, False otherwise
        """
        captcha_type = captcha_info.get('type')
        
        if not captcha_type:
            self.logger.warning("Cannot solve CAPTCHA: missing type information")
            return False
        
        self.logger.info(f"Attempting to solve {captcha_type} CAPTCHA")
        
        try:
            if captcha_type == 'recaptcha_v2':
                return self._solve_recaptcha_v2(captcha_info)
            elif captcha_type == 'hcaptcha':
                return self._solve_hcaptcha(captcha_info)
            elif captcha_type == 'image_captcha':
                return self._solve_image_captcha(captcha_info)
            elif captcha_type == 'text_captcha':
                return self._solve_text_captcha(captcha_info)
            else:
                self.logger.warning(f"Unsupported CAPTCHA type: {captcha_type}")
                return False
        except Exception as e:
            self.logger.error(f"Error solving CAPTCHA: {str(e)}")
            return False
    
    def _solve_recaptcha_v2(self, captcha_info: Dict[str, Any]) -> bool:
        """Solve reCAPTCHA v2."""
        if self.service == 'local':
            self.logger.warning("Local solving not implemented for reCAPTCHA")
            return False
        
        iframe_selector = captcha_info.get('iframe')
        
        try:
            # Switch to the reCAPTCHA iframe
            iframe = self.driver.find_element(By.CSS_SELECTOR, iframe_selector)
            self.driver.switch_to.frame(iframe)
            
            # Click the checkbox
            checkbox = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.CAPTCHA_PATTERNS['recaptcha_v2']['checkbox']))
            )
            checkbox.click()
            
            # Switch back to main content
            self.driver.switch_to.default_content()
            
            # Wait to see if we need to solve an image challenge
            time.sleep(2)
            
            # Check if we have an image challenge
            image_iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[title*='challenge']")
            if image_iframes:
                self.logger.info("reCAPTCHA image challenge detected")
                
                if self.service == 'anti-captcha' and self.api_key:
                    return self._solve_recaptcha_with_service()
                
                self.logger.warning("Cannot solve reCAPTCHA image challenge without a service")
                return False
            
            # If no image challenge appeared, we passed
            self.logger.info("reCAPTCHA solved successfully (checkbox only)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error solving reCAPTCHA: {str(e)}")
            return False
    
    def _solve_recaptcha_with_service(self) -> bool:
        """Solve reCAPTCHA using an external service."""
        try:
            # Get the sitekey
            site_key = self.driver.execute_script(
                "return document.querySelector('div.g-recaptcha').getAttribute('data-sitekey')"
            )
            
            if not site_key:
                self.logger.error("Could not find reCAPTCHA site key")
                return False
            
            # Use Anti-Captcha API to solve
            if self.service == 'anti-captcha':
                self.logger.info("Using Anti-Captcha service to solve reCAPTCHA")
                # Implementation would go here - simplified for this example
                
                # Wait for the solution
                time.sleep(5)
                
                # Apply the solution using JavaScript
                self.driver.execute_script(
                    f"document.getElementById('g-recaptcha-response').innerHTML = 'solution';"
                )
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error solving reCAPTCHA with service: {str(e)}")
            return False
    
    def _solve_hcaptcha(self, captcha_info: Dict[str, Any]) -> bool:
        """Solve hCaptcha."""
        # Implementation similar to reCAPTCHA but with hCaptcha specifics
        self.logger.info("hCaptcha solving not fully implemented")
        return False
    
    def _solve_image_captcha(self, captcha_info: Dict[str, Any]) -> bool:
        """Solve simple image CAPTCHA."""
        image_selector = captcha_info.get('image_selector')
        input_selector = captcha_info.get('input_selector')
        
        if not image_selector or not input_selector:
            self.logger.error("Missing selectors for image CAPTCHA")
            return False
        
        try:
            # Get the image element
            img_element = self.driver.find_element(By.CSS_SELECTOR, image_selector)
            
            # Get the image source
            img_src = img_element.get_attribute('src')
            
            if not img_src:
                self.logger.error("Could not get image source")
                return False
            
            # Process and solve the CAPTCHA
            captcha_text = None
            
            if self.service == 'local':
                captcha_text = self._solve_image_captcha_locally(img_src)
            else:
                captcha_text = self._solve_image_captcha_with_service(img_src)
            
            if not captcha_text:
                self.logger.warning("Failed to solve image CAPTCHA")
                return False
            
            # Enter the solution
            input_element = self.driver.find_element(By.CSS_SELECTOR, input_selector)
            input_element.clear()
            input_element.send_keys(captcha_text)
            
            # Find and click submit button
            submit_buttons = self.driver.find_elements(
                By.XPATH, 
                "//button[@type='submit'] | //input[@type='submit']"
            )
            
            if submit_buttons:
                submit_buttons[0].click()
                self.logger.info("Image CAPTCHA solution submitted")
                return True
            else:
                self.logger.warning("Could not find submit button for CAPTCHA")
                return False
                
        except Exception as e:
            self.logger.error(f"Error solving image CAPTCHA: {str(e)}")
            return False
    
    def _solve_image_captcha_locally(self, img_src: str) -> Optional[str]:
        """Attempt to solve image CAPTCHA using local OCR (simplified)."""
        self.logger.info("Attempting to solve image CAPTCHA locally")
        
        try:
            # Download the image
            import requests
            from io import BytesIO
            
            if img_src.startswith('data:image'):
                # Handle base64 encoded image
                b64_data = img_src.split(',')[1]
                img_data = base64.b64decode(b64_data)
                image = Image.open(BytesIO(img_data))
            else:
                # Handle URL image
                response = requests.get(img_src)
                image = Image.open(BytesIO(response.content))
            
            # Preprocess the image (convert to grayscale, apply thresholding, etc.)
            image = image.convert('L')  # Convert to grayscale
            
            # Use OCR to read the text (simplified)
            try:
                import pytesseract
                captcha_text = pytesseract.image_to_string(image, config='--psm 8')
                captcha_text = re.sub(r'\W+', '', captcha_text)  # Remove non-alphanumeric
                
                if captcha_text:
                    self.logger.info(f"OCR result: {captcha_text}")
                    return captcha_text
                else:
                    self.logger.warning("OCR could not read CAPTCHA text")
                    return None
            except ImportError:
                self.logger.warning("pytesseract not installed for OCR")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in local CAPTCHA solving: {str(e)}")
            return None
    
    def _solve_image_captcha_with_service(self, img_src: str) -> Optional[str]:
        """Solve image CAPTCHA using an external service."""
        if not self.api_key:
            self.logger.warning("No API key for CAPTCHA service")
            return None
            
        self.logger.info(f"Using {self.service} service to solve image CAPTCHA")
        
        # Implementation would depend on the specific service API
        # This is a simplified example
        time.sleep(2)
        return "example123"
    
    def _solve_text_captcha(self, captcha_info: Dict[str, Any]) -> bool:
        """Solve text-based CAPTCHA."""
        question_selector = captcha_info.get('question_selector')
        input_selector = captcha_info.get('input_selector')
        
        if not question_selector or not input_selector:
            self.logger.error("Missing selectors for text CAPTCHA")
            return False
        
        try:
            # Get the question text
            question_element = self.driver.find_element(By.CSS_SELECTOR, question_selector)
            question_text = question_element.text
            
            if not question_text:
                self.logger.error("Could not get CAPTCHA question text")
                return False
            
            # Analyze and solve the question
            answer = self._solve_text_captcha_question(question_text)
            
            if not answer:
                self.logger.warning(f"Could not solve text CAPTCHA: {question_text}")
                return False
            
            # Enter the answer
            input_element = self.driver.find_element(By.CSS_SELECTOR, input_selector)
            input_element.clear()
            input_element.send_keys(answer)
            
            # Find and click submit button
            submit_buttons = self.driver.find_elements(
                By.XPATH, 
                "//button[@type='submit'] | //input[@type='submit']"
            )
            
            if submit_buttons:
                submit_buttons[0].click()
                self.logger.info("Text CAPTCHA solution submitted")
                return True
            else:
                self.logger.warning("Could not find submit button for CAPTCHA")
                return False
                
        except Exception as e:
            self.logger.error(f"Error solving text CAPTCHA: {str(e)}")
            return False
    
    def _solve_text_captcha_question(self, question: str) -> Optional[str]:
        """Analyze and solve a text-based CAPTCHA question."""
        self.logger.info(f"Attempting to solve text CAPTCHA: {question}")
        
        # Look for common patterns
        
        # Math questions
        math_match = re.search(r'what is (\d+) \+ (\d+)', question, re.IGNORECASE)
        if math_match:
            num1 = int(math_match.group(1))
            num2 = int(math_match.group(2))
            return str(num1 + num2)
        
        math_match = re.search(r'what is (\d+) minus (\d+)', question, re.IGNORECASE)
        if math_match:
            num1 = int(math_match.group(1))
            num2 = int(math_match.group(2))
            return str(num1 - num2)
        
        # Word questions
        if "capital of france" in question.lower():
            return "Paris"
        if "largest planet" in question.lower():
            return "Jupiter"
        
        # If service is available, use it
        if self.service != 'local' and self.api_key:
            return self._solve_text_captcha_with_service(question)
        
        self.logger.warning(f"Could not solve text CAPTCHA: {question}")
        return None
    
    def _solve_text_captcha_with_service(self, question: str) -> Optional[str]:
        """Solve text CAPTCHA using an external service."""
        # Implementation would depend on the specific service API
        self.logger.info(f"Using {self.service} service to solve text CAPTCHA")
        
        # Simplified example
        time.sleep(2)
        return "example answer" 