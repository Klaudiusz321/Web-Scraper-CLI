from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from scraper.captacha_solver import CaptchaSolver
import time



class WebScraper:
    def __init__(self, config=None):
        # Browser settings (Chrome) in headless mode
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(options=options)
        self.config = config or {}
        
        # Initialize CAPTCHA solver
        self.captcha_solver = CaptchaSolver(self.driver, self.config.get('captcha', {}))

    def navigate(self, url: str):
        """Navigate to specified URL and handle any CAPTCHAs encountered"""
        self.driver.get(url)
        
        # Check for and solve CAPTCHA if auto_solve is enabled
        if self.config.get('auto_solve_captcha', True):
            captcha_info = self.captcha_solver.detect_captcha()
            if captcha_info:
                print(f"CAPTCHA detected on {url} - attempting to solve automatically")
                solved = self.captcha_solver.solve_captcha(captcha_info)
                if solved:
                    print("CAPTCHA solved successfully!")
                    # Wait a bit for page to load after CAPTCHA solution
                    time.sleep(3)
                else:
                    print("Failed to solve CAPTCHA automatically")
        
        return self

    def element_exists(self, css_selector: str) -> bool:
        """Check if element exists on the page"""
        try:
            self.driver.find_element(By.CSS_SELECTOR, css_selector)
            return True
        except NoSuchElementException:
            return False

    def wait_for_element(self, by: By, identifier: str, timeout: int = 10):
        """Wait for element to appear on page"""
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.presence_of_element_located((by, identifier)))

    def execute_js(self, script: str):
        """Execute JavaScript code on page"""
        return self.driver.execute_script(script)

    def click(self, css_selector: str):
        """Click on element specified by CSS selector"""
        element = self.driver.find_element(By.CSS_SELECTOR, css_selector)
        element.click()
        
        # Check for CAPTCHA after clicking
        if self.config.get('auto_solve_captcha', True):
            time.sleep(1)  # Give page a moment to possibly show CAPTCHA
            captcha_info = self.captcha_solver.detect_captcha()
            if captcha_info:
                print("CAPTCHA detected after clicking - attempting to solve")
                self.captcha_solver.solve_captcha(captcha_info)
        
        return self

    def get_html(self) -> str:
        """Get page HTML source"""
        return self.driver.page_source

    def get_text(self, css_selector: str) -> str:
        """Get text from element specified by CSS selector"""
        element = self.driver.find_element(By.CSS_SELECTOR, css_selector)
        return element.text

    def close(self):
        """Close browser"""
        self.driver.quit()
    
    def login(self, login_url: str, username: str, password: str):
        """Login to website with credentials and handle any CAPTCHAs"""
        self.navigate(login_url)
        
        # Common selectors for login forms
        username_selectors = ["input[name='username']", "input[name='email']", "input[name='login']", "input[id='username']", "input[id='email']"]
        password_selectors = ["input[name='password']", "input[id='password']", "input[type='password']"]
        submit_selectors = ["input[type='submit']", "button[type='submit']", "button:contains('Login')", "button:contains('Sign in')"]
        
        # Try to find and fill username field
        for selector in username_selectors:
            try:
                username_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                username_field.clear()
                username_field.send_keys(username)
                break
            except NoSuchElementException:
                continue
        
        # Try to find and fill password field
        for selector in password_selectors:
            try:
                password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                password_field.clear()
                password_field.send_keys(password)
                break
            except NoSuchElementException:
                continue
        
        # Check for CAPTCHA before submitting
        captcha_info = self.captcha_solver.detect_captcha()
        if captcha_info:
            print("CAPTCHA detected on login form - attempting to solve")
            self.captcha_solver.solve_captcha(captcha_info)
        else:
            # No CAPTCHA, so click submit
            for selector in submit_selectors:
                try:
                    submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    submit_button.click()
                    break
                except NoSuchElementException:
                    continue
        
        # Check for CAPTCHA after submission
        time.sleep(2)  # Wait for possible CAPTCHA
        captcha_info = self.captcha_solver.detect_captcha()
        if captcha_info:
            print("CAPTCHA detected after login submission - attempting to solve")
            self.captcha_solver.solve_captcha(captcha_info)
        
        return self

    