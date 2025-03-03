import requests, base64, time
from PIL import Image
import pytesseract
from io import BytesIO
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Common CAPTCHA selectors and identifiers
CAPTCHA_IDENTIFIERS = [
    {"by": By.ID, "value": "captcha"},
    {"by": By.ID, "value": "captchaimg"},
    {"by": By.CSS_SELECTOR, "value": "img[src*='captcha']"},
    {"by": By.CSS_SELECTOR, "value": "div.g-recaptcha"},
    {"by": By.CSS_SELECTOR, "value": "iframe[src*='recaptcha']"},
    {"by": By.CSS_SELECTOR, "value": "iframe[src*='captcha']"},
    {"by": By.XPATH, "value": "//img[contains(@alt,'captcha')]"}
]

# CAPTCHA input field selectors
CAPTCHA_INPUT_SELECTORS = [
    {"by": By.ID, "value": "captcha-input"},
    {"by": By.NAME, "value": "captcha"},
    {"by": By.CSS_SELECTOR, "value": "input[placeholder*='captcha' i]"},
    {"by": By.CSS_SELECTOR, "value": "input[name*='captcha' i]"}
]

class CaptchaSolver:
    def __init__(self, driver, config=None):
        self.driver = driver
        self.config = config or {}
        self.api_key = self.config.get('2captcha_api_key', os.environ.get('CAPTCHA_API_KEY', ''))
        self.temp_dir = self.config.get('temp_dir', 'temp_captcha')
        self.auto_solve = self.config.get('auto_solve', True)
        
        # Create temp directory if needed
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def detect_captcha(self, timeout=5):
        """
        Checks if current page contains a CAPTCHA.
        Returns the CAPTCHA element and its type if found, None otherwise.
        """
        for identifier in CAPTCHA_IDENTIFIERS:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((identifier["by"], identifier["value"]))
                )
                # Determine the type of CAPTCHA
                html = element.get_attribute("outerHTML")
                if "g-recaptcha" in html:
                    return {"element": element, "type": "recaptcha"}
                elif "hcaptcha" in html:
                    return {"element": element, "type": "hcaptcha"}
                else:
                    return {"element": element, "type": "image"}
            except (TimeoutException, NoSuchElementException):
                continue
        return None
        
    def find_captcha_input(self):
        """Find the input field for CAPTCHA solution."""
        for selector in CAPTCHA_INPUT_SELECTORS:
            try:
                return self.driver.find_element(selector["by"], selector["value"])
            except NoSuchElementException:
                continue
        return None
    
    def find_submit_button(self):
        """Find the submit button for the form containing CAPTCHA."""
        try:
            # Common submit button selectors
            for selector in ["input[type='submit']", "button[type='submit']", 
                             "button:contains('Submit')", "button:contains('Verify')"]:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    return elements[0]
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def solve_captcha(self, captcha_info=None):
        """
        Main method to solve detected CAPTCHA.
        Returns True if CAPTCHA was solved successfully, False otherwise.
        """
        if not captcha_info:
            captcha_info = self.detect_captcha()
            
        if not captcha_info:
            print("No CAPTCHA detected on this page")
            return True  # No CAPTCHA to solve
            
        captcha_type = captcha_info["type"]
        element = captcha_info["element"]
        
        solution = None
        timestamp = int(time.time())
        screenshot_path = f"{self.temp_dir}/captcha_{timestamp}.png"
        
        print(f"CAPTCHA detected! Type: {captcha_type}")
        
        if captcha_type == "image":
            # Try OCR first for image captchas
            solution = self.solve_captcha_ocr(element, screenshot_path)
            # If OCR fails or returns unlikely solution, try 2captcha
            if not solution or len(solution) < 3:
                if self.api_key:
                    solution = self.solve_captcha_2captcha(element, screenshot_path)
                else:
                    print("OCR solution failed and no 2CAPTCHA API key provided")
                    return False
        elif captcha_type in ["recaptcha", "hcaptcha"]:
            if not self.api_key:
                print(f"Cannot solve {captcha_type} without 2CAPTCHA API key")
                return False
            # Get the site key
            if captcha_type == "recaptcha":
                site_key = self.driver.execute_script(
                    "return document.querySelector('.g-recaptcha').getAttribute('data-sitekey')"
                )
                solution = self.solve_recaptcha(site_key)
            else:
                site_key = self.driver.execute_script(
                    "return document.querySelector('div[data-sitekey]').getAttribute('data-sitekey')"
                )
                solution = self.solve_hcaptcha(site_key)
        
        if not solution:
            print("Failed to solve CAPTCHA")
            return False
            
        # Input the solution if it's an image CAPTCHA
        if captcha_type == "image":
            input_field = self.find_captcha_input()
            if input_field:
                input_field.clear()
                input_field.send_keys(solution)
                # Find and click submit button
                submit_button = self.find_submit_button()
                if submit_button:
                    submit_button.click()
                    return True
            else:
                print("Could not find CAPTCHA input field")
                return False
        # For reCAPTCHA or hCAPTCHA, the solution is handled by JavaScript
        else:
            # Set the g-recaptcha-response or h-captcha-response
            response_type = "g-recaptcha-response" if captcha_type == "recaptcha" else "h-captcha-response"
            self.driver.execute_script(
                f"document.getElementById('{response_type}').innerHTML = '{solution}'"
            )
            # Submit the form
            submit_button = self.find_submit_button()
            if submit_button:
                submit_button.click()
                return True
            else:
                print("Could not find submit button")
                return False
    
    def solve_captcha_ocr(self, element, screenshot_path="captcha.png"):
        """Solve image CAPTCHA using local OCR."""
        try:
            # Take screenshot of just the CAPTCHA element
            element.screenshot(screenshot_path)
            # Use Tesseract OCR to read text from image
            text = pytesseract.image_to_string(Image.open(screenshot_path))
            text = text.strip().replace(" ", "").replace("\n", "")
            print(f"OCR detected text: {text}")
            return text
        except Exception as e:
            print(f"Error solving CAPTCHA with OCR: {e}")
            return None

    def solve_captcha_2captcha(self, element, screenshot_path="captcha.png"):
        """Solve image CAPTCHA using 2CAPTCHA service."""
        try:
            # Take screenshot of just the CAPTCHA element
            element.screenshot(screenshot_path)
            # Send CAPTCHA to 2CAPTCHA service
            with open(screenshot_path, 'rb') as f:
                response = requests.post(
                    'https://2captcha.com/in.php',
                    files={'file': f},
                    data={'key': self.api_key}
                )
            if not response.text.startswith('OK|'):
                print(f"Error sending CAPTCHA to 2CAPTCHA: {response.text}")
                return None
            # Format: OK|12345678
            captcha_id = response.text.split('|')[1]
            # Wait for solution
            for _ in range(30):  # Timeout after 30 attempts (approx. 60 seconds)
                time.sleep(2)
                solution_response = requests.get(
                    f'https://2captcha.com/res.php?key={self.api_key}&action=get&id={captcha_id}'
                )
                if solution_response.text.startswith('OK|'):
                    solution = solution_response.text.split('|')[1]
                    print(f"2CAPTCHA solution: {solution}")
                    return solution
                if solution_response.text != 'CAPCHA_NOT_READY':
                    print(f"Error getting solution from 2CAPTCHA: {solution_response.text}")
                    return None
            print("Timeout waiting for 2CAPTCHA solution")
            return None
        except Exception as e:
            print(f"Error solving CAPTCHA with 2CAPTCHA: {e}")
            return None
            
    def solve_recaptcha(self, site_key):
        """Solve Google reCAPTCHA using 2CAPTCHA service."""
        try:
            page_url = self.driver.current_url
            # Send request to 2CAPTCHA
            response = requests.post(
                'https://2captcha.com/in.php',
                data={
                    'key': self.api_key,
                    'method': 'userrecaptcha',
                    'googlekey': site_key,
                    'pageurl': page_url
                }
            )
            if not response.text.startswith('OK|'):
                print(f"Error sending reCAPTCHA to 2CAPTCHA: {response.text}")
                return None
            captcha_id = response.text.split('|')[1]
            # Wait for solution
            for _ in range(60):  # Timeout after 60 attempts (approx. 120 seconds)
                time.sleep(2)
                solution_response = requests.get(
                    f'https://2captcha.com/res.php?key={self.api_key}&action=get&id={captcha_id}'
                )
                if solution_response.text.startswith('OK|'):
                    return solution_response.text.split('|')[1]
                if solution_response.text != 'CAPCHA_NOT_READY':
                    print(f"Error getting reCAPTCHA solution: {solution_response.text}")
                    return None
            print("Timeout waiting for reCAPTCHA solution")
            return None
        except Exception as e:
            print(f"Error solving reCAPTCHA: {e}")
            return None
            
    def solve_hcaptcha(self, site_key):
        """Solve hCaptcha using 2CAPTCHA service."""
        try:
            page_url = self.driver.current_url
            # Send request to 2CAPTCHA
            response = requests.post(
                'https://2captcha.com/in.php',
                data={
                    'key': self.api_key,
                    'method': 'hcaptcha',
                    'sitekey': site_key,
                    'pageurl': page_url
                }
            )
            if not response.text.startswith('OK|'):
                print(f"Error sending hCaptcha to 2CAPTCHA: {response.text}")
                return None
            captcha_id = response.text.split('|')[1]
            # Wait for solution
            for _ in range(60):
                time.sleep(2)
                solution_response = requests.get(
                    f'https://2captcha.com/res.php?key={self.api_key}&action=get&id={captcha_id}'
                )
                if solution_response.text.startswith('OK|'):
                    return solution_response.text.split('|')[1]
                if solution_response.text != 'CAPCHA_NOT_READY':
                    print(f"Error getting hCaptcha solution: {solution_response.text}")
                    return None
            print("Timeout waiting for hCaptcha solution")
            return None
        except Exception as e:
            print(f"Error solving hCaptcha: {e}")
            return None
