﻿# Web-Scraper-CLI
Web Scraper CLI – Advanced Interactive Web Scraping Tool

This project is an advanced CLI web scraper built with Python and Django. It leverages Selenium (using headless Chrome) to dynamically interact with websites, providing the following features:

Available commands:
        
        Web scraper commands:
        - navigate [url] - navigate to specified URL
        - click [selector] - click element with specified CSS selector
        - get_html - retrieve and save HTML code of current page
        - get_text [selector] - retrieve and save text from element
        - save [format] [filename] - save collected data
        
        API REST commands:
        - api_get [url] - execute GET request to API
        - api_post [url] [json_data] - execute POST request to API
        - api_auth_basic [username] [password] - set Basic authentication
        - api_auth_token [token] - set Bearer token authentication
        - api_header [key] [value] - set HTTP header
        - api_save [filename] - save last API response to file
        - api_info - show information about last response
        
        Other commands:
        - status - show amount and type of collected data
        - clear - clear all collected data
        - help - display this help
        - exit/quit - exit program

Interactive Navigation: Navigate to any URL and execute commands (e.g., nav <URL>, extract <CSS>) in an interactive CLI.
Data Extraction: Retrieve HTML content and specific text elements from a page, with built-in support for cleaning, sentiment analysis, and entity extraction using BeautifulSoup, NLTK, TextBlob, and spaCy.
Automation & Login: Automate form filling and login processes for secured websites.
CAPTCHA Solving: Integrates both local OCR (using pytesseract) and external services like 2Captcha to solve various CAPTCHA challenges.
Data Export: Export collected data into multiple formats including CSV, JSON, and XML.
Modular & Extensible: A clean, modular codebase that makes it easy to extend and adapt to different websites.
Technologies Used
Python 3
Django (CLI command framework)
Selenium (headless Chrome)
MongoDB (optional, for data storage)
BeautifulSoup, NLTK, TextBlob, spaCy (for data processing and NLP)
2Captcha API & pytesseract (for CAPTCHA solving)
Installation & Usage
Clone the repository and set up a virtual environment.
Install dependencies using:
bash
Copy
pip install -r requirements.txt
Configure environment variables (e.g., CAPTCHA_API_KEY).
Run the interactive scraper:
bash
Copy
python manage.py scraper
Use commands like nav <URL>, extract <CSS>, analyze, and save_csv to navigate, scrape, analyze, and export data.
