import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import json
import os

class APIClient:
    def __init__(self):
        self.headers = {}
        self.auth = None
        self.last_response = None
        self.last_url = None
    
    def set_header(self, key, value):
       
        self.headers[key] = value
        return self
    
    def set_auth_basic(self, username, password):
        
        self.auth = HTTPBasicAuth(username, password)
        return self
    
    def set_auth_token(self, token):
       
        self.headers["Authorization"] = f"Bearer {token}"
        return self
    
    def get(self, url, params=None):
        
        self.last_url = url
        try:
            self.last_response = requests.get(
                url, 
                headers=self.headers,
                params=params,
                auth=self.auth
            )
            return self.last_response
        except Exception as e:
            print(f"Error during GET request: {e}")
            return None
    
    def post(self, url, data=None, json_data=None):
        
        self.last_url = url
        try:
            self.last_response = requests.post(
                url, 
                headers=self.headers,
                data=data,
                json=json_data,
                auth=self.auth
            )
            return self.last_response
        except Exception as e:
            print(f"Error during POST request: {e}")
            return None
            
    def save_response(self, filename=None):
        
        if not self.last_response:
            return "No response to save."
            
        if not filename:
            # Generuj nazwę pliku na podstawie URL
            from urllib.parse import urlparse
            parsed_url = urlparse(self.last_url)
            base_name = os.path.basename(parsed_url.path) or "api_response"
            filename = f"{base_name}.json"
        
        export_dir = "exported_api"
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.last_response.json(), f, indent=2, ensure_ascii=False)
            return f"Odpowiedź zapisana do: {file_path}"
        except Exception as e:
            return f"Błąd podczas zapisywania odpowiedzi: {e}"
    
    def get_last_response_info(self):
        """Zwraca informacje o ostatniej odpowiedzi"""

def fetch_items(url="https://api.przyklad.com/items"):
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        print("Liczba obiektów:", len(data))
        return data
    else:
        print("Błąd pobierania danych:", response.status_code)
        return []

def fetch_github_user(username, token):
    url = "https://api.github.com/user"
    res = requests.get(url, auth=HTTPBasicAuth(username, token))
    print(res.status_code, res.json())
    return res.json()

def filter_books(data):
    filtered_books = [item for item in data if item.get("category") == "books"]
    return filtered_books
