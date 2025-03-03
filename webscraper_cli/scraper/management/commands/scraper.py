from django.core.management.base import BaseCommand
from scraper.webscraper import WebScraper
from scraper.exporter import export_to_csv, export_to_json, export_to_xml
from scraper.data_processing import clean_text, get_top_words, analyze_sentiment, extract_entities
from scraper.db import save_result
from scraper.api_client import APIClient
import datetime
import os
import json

class Command(BaseCommand):
    help = "Runs interactive Web Scraper CLI tool (Django + Selenium)."

    def handle(self, *args, **options):
        # Create scraper instance (opens headless browser)
        scraper = WebScraper()
        # Create API client instance
        api_client = APIClient()
        print("Welcome to Web Scraper CLI. Type 'help' to see available commands.")
        
        # Data collected from websites and API
        scraped_data = {}
        current_url = None
        
        while True:
            cmd = input("scraper> ").strip()
            if cmd.lower() in ("exit", "quit"):
                scraper.close()
                print("Goodbye!")
                break
            elif cmd.lower() == "help":
                self.show_help()
            elif cmd.lower().startswith("navigate "):
                current_url = cmd[9:].strip()
                try:
                    scraper.navigate(current_url)
                    # Initialize data for this page
                    scraped_data[current_url] = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "title": scraper.driver.title,
                        "html": None,
                        "texts": {}
                    }
                    print(f"Navigation to {current_url} completed successfully")
                except Exception as e:
                    print(f"Error during navigation: {e}")
            elif cmd.lower().startswith("click "):
                selector = cmd[6:].strip()
                try:
                    scraper.click(selector)
                    print(f"Clicked element: {selector}")
                except Exception as e:
                    print(f"Error during click: {e}")
            elif cmd.lower() == "get_html":
                if current_url and current_url in scraped_data:
                    try:
                        html = scraper.get_html()
                        scraped_data[current_url]["html"] = html
                        print("HTML retrieved (first 100 characters):")
                        print(html[:100] + "..." if len(html) > 100 else html)
                    except Exception as e:
                        print(f"Error retrieving HTML: {e}")
                else:
                    print("First navigate to a page using 'navigate' command")
            elif cmd.lower().startswith("get_text "):
                if current_url and current_url in scraped_data:
                    selector = cmd[9:].strip()
                    try:
                        text = scraper.get_text(selector)
                        scraped_data[current_url]["texts"][selector] = text
                        print(f"Text from element {selector}:")
                        print(text[:100] + "..." if len(text) > 100 else text)
                    except Exception as e:
                        print(f"Error retrieving text: {e}")
                else:
                    print("First navigate to a page using 'navigate' command")
            elif cmd.lower().startswith("save "):
                params = cmd[5:].strip().split()
                if not params:
                    print("Missing format. Use: save [format] [filename]")
                    continue
                
                if not scraped_data:
                    print("No data to save. First scrape some data.")
                    continue
                
                format_type = params[0].lower()
                filename = params[1] if len(params) > 1 else f"scraper_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Ensure file extension is appropriate
                if not filename.endswith(f".{format_type}"):
                    filename = f"{filename}.{format_type}"
                
                try:
                    data_list = []
                    for url, data in scraped_data.items():
                        item = {
                            "url": url,
                            "timestamp": data["timestamp"],
                            "title": data["title"],
                            "html_length": len(data["html"]) if data["html"] else 0,
                            "texts": data["texts"]
                        }
                        data_list.append(item)
                    
                    # Add path to export directory
                    export_dir = "exported_data"
                    os.makedirs(export_dir, exist_ok=True)
                    file_path = os.path.join(export_dir, filename)
                    
                    if format_type == "csv":
                        export_to_csv(data_list, file_path)
                    elif format_type == "json":
                        export_to_json(data_list, file_path)
                    elif format_type == "xml":
                        export_to_xml(data_list, file_path)
                    elif format_type == "db":
                        for item in data_list:
                            save_result(item)
                        file_path = "database"
                    else:
                        print(f"Unsupported format: {format_type}. Available formats: csv, json, xml, db")
                        continue
                    
                    print(f"Data saved successfully to: {file_path}")
                except Exception as e:
                    print(f"Error during saving data: {e}")
            elif cmd.lower() == "status":
                if scraped_data:
                    print("\nScraped pages:")
                    for url, data in scraped_data.items():
                        html_status = "Retrieved" if data["html"] else "Missing"
                        print(f"URL: {url}")
                        print(f"  Title: {data['title']}")
                        print(f"  HTML: {html_status}")
                        print(f"  Text elements: {len(data['texts'])}")
                        print()
                else:
                    print("No scraped data.")
            elif cmd.lower() == "clear":
                scraped_data = {}
                current_url = None
                print("Cleared all collected data.")
            elif cmd.lower().startswith("api_get "):
                url = cmd[8:].strip()
                response = api_client.get(url)
                if response and response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"Status: {response.status_code}")
                        print(f"Content type: {response.headers.get('Content-Type')}")
                        
                        if isinstance(data, list):
                            print(f"Number of objects: {len(data)}")
                            if len(data) > 0:
                                print("Sample object:")
                                print(json.dumps(data[0], indent=2, ensure_ascii=False)[:300] + "...")
                        else:
                            print("JSON response (fragment):")
                            print(json.dumps(data, indent=2, ensure_ascii=False)[:300] + "...")
                    except Exception as e:
                        print(f"Unexpected error while processing JSON: {e}")
                else:
                    print(f"Error during retrieval: Code {response.status_code if response else 'no response'}")
            else:
                print(f"Unknown command: {cmd}. Type 'help' to see available options.")
    
    def show_help(self):
        print("""
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
        """)
