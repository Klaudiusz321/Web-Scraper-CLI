"""
API client for making requests to external APIs.
"""
import requests
from requests.auth import HTTPBasicAuth
import json
import os
from typing import Dict, Any, Optional, Union, List
import ssl
from pathlib import Path

from webscraper_cli.config import settings
from webscraper_cli.utils.logger import LoggerMixin
from webscraper_cli.utils.exceptions import APIError
from webscraper_cli.utils.retry import retry
from webscraper_cli.utils.rate_limiter import rate_limited
from webscraper_cli.utils.security import get_ssl_context

class APIClient(LoggerMixin):
    """
    Client for making requests to external APIs with authentication, 
    rate limiting, and error handling.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the API client.
        
        Args:
            config: Optional configuration override (default: use settings module)
        """
        self.config = config or settings.get_config()
        self.headers = self.config.get('default_headers', {}).copy()
        self.auth = None
        self.last_response = None
        self.last_url = None
        self.timeout = self.config.get('timeouts', {}).get('api_request', 15)
        self.ssl_verify = self.config.get('ssl_verify', True)
        
        # Create session for connection pooling
        self.session = requests.Session()
        
        # Use default headers
        if not self.headers:
            self.headers = {"User-Agent": "WebScraperCLI/1.0"}
        
        self.logger.info("API client initialized")
    
    def set_header(self, key: str, value: str) -> 'APIClient':
        """
        Set an HTTP header.
        
        Args:
            key: Header name
            value: Header value
            
        Returns:
            Self for method chaining
        """
        self.logger.debug(f"Setting header: {key}={value}")
        self.headers[key] = value
        return self
    
    def set_auth_basic(self, username: str, password: str) -> 'APIClient':
        """
        Set basic authentication.
        
        Args:
            username: Username for authentication
            password: Password for authentication
            
        Returns:
            Self for method chaining
        """
        self.logger.info(f"Setting basic authentication for user: {username}")
        self.auth = HTTPBasicAuth(username, password)
        return self
    
    def set_auth_token(self, token: str) -> 'APIClient':
        """
        Set token-based authentication.
        
        Args:
            token: Authentication token
            
        Returns:
            Self for method chaining
        """
        self.logger.info("Setting bearer token authentication")
        self.headers["Authorization"] = f"Bearer {token}"
        return self
    
    @rate_limited
    @retry(exceptions=(requests.RequestException,))
    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[requests.Response]:
        """
        Make a GET request.
        
        Args:
            url: URL to request
            params: Optional query parameters
            
        Returns:
            Response object or None if error
            
        Raises:
            APIError: If request fails
        """
        self.last_url = url
        self.logger.info(f"Making GET request to {url}")
        
        try:
            self.last_response = self.session.get(
                url, 
                headers=self.headers,
                params=params,
                auth=self.auth,
                timeout=self.timeout,
                verify=self.ssl_verify
            )
            
            self._check_response_status()
            return self.last_response
            
        except requests.RequestException as e:
            error_msg = f"Error during GET request to {url}: {str(e)}"
            self.logger.error(error_msg)
            raise APIError(error_msg, details={"url": url, "params": params})
    
    @rate_limited
    @retry(exceptions=(requests.RequestException,))
    def post(self, url: str, data: Optional[Dict[str, Any]] = None, 
             json_data: Optional[Dict[str, Any]] = None) -> Optional[requests.Response]:
        """
        Make a POST request.
        
        Args:
            url: URL to request
            data: Optional form data
            json_data: Optional JSON data
            
        Returns:
            Response object or None if error
            
        Raises:
            APIError: If request fails
        """
        self.last_url = url
        self.logger.info(f"Making POST request to {url}")
        
        try:
            self.last_response = self.session.post(
                url, 
                headers=self.headers,
                data=data,
                json=json_data,
                auth=self.auth,
                timeout=self.timeout,
                verify=self.ssl_verify
            )
            
            self._check_response_status()
            return self.last_response
            
        except requests.RequestException as e:
            error_msg = f"Error during POST request to {url}: {str(e)}"
            self.logger.error(error_msg)
            raise APIError(error_msg, details={"url": url})
    
    @rate_limited
    @retry(exceptions=(requests.RequestException,))
    def put(self, url: str, data: Optional[Dict[str, Any]] = None, 
            json_data: Optional[Dict[str, Any]] = None) -> Optional[requests.Response]:
        """
        Make a PUT request.
        
        Args:
            url: URL to request
            data: Optional form data
            json_data: Optional JSON data
            
        Returns:
            Response object or None if error
            
        Raises:
            APIError: If request fails
        """
        self.last_url = url
        self.logger.info(f"Making PUT request to {url}")
        
        try:
            self.last_response = self.session.put(
                url, 
                headers=self.headers,
                data=data,
                json=json_data,
                auth=self.auth,
                timeout=self.timeout,
                verify=self.ssl_verify
            )
            
            self._check_response_status()
            return self.last_response
            
        except requests.RequestException as e:
            error_msg = f"Error during PUT request to {url}: {str(e)}"
            self.logger.error(error_msg)
            raise APIError(error_msg, details={"url": url})
    
    @rate_limited
    @retry(exceptions=(requests.RequestException,))
    def delete(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[requests.Response]:
        """
        Make a DELETE request.
        
        Args:
            url: URL to request
            params: Optional query parameters
            
        Returns:
            Response object or None if error
            
        Raises:
            APIError: If request fails
        """
        self.last_url = url
        self.logger.info(f"Making DELETE request to {url}")
        
        try:
            self.last_response = self.session.delete(
                url, 
                headers=self.headers,
                params=params,
                auth=self.auth,
                timeout=self.timeout,
                verify=self.ssl_verify
            )
            
            self._check_response_status()
            return self.last_response
            
        except requests.RequestException as e:
            error_msg = f"Error during DELETE request to {url}: {str(e)}"
            self.logger.error(error_msg)
            raise APIError(error_msg, details={"url": url})
    
    def _check_response_status(self) -> None:
        """
        Check response status and raise exception if error.
        
        Raises:
            APIError: If response status is error
        """
        if not self.last_response:
            return
            
        if 400 <= self.last_response.status_code < 600:
            error_msg = f"API error: {self.last_response.status_code}"
            self.logger.error(f"{error_msg} - URL: {self.last_url}")
            
            # Try to extract error details from response
            response_text = self.last_response.text
            try:
                response_json = self.last_response.json()
                error_details = response_json.get('error') or response_json
            except:
                error_details = response_text[:500]  # Limit to 500 chars
            
            raise APIError(
                error_msg,
                status_code=self.last_response.status_code,
                response_text=response_text,
                details={"url": self.last_url}
            )
    
    def save_response(self, filename: Optional[str] = None) -> str:
        """
        Save the last response to a file.
        
        Args:
            filename: Optional filename (generated from URL if not provided)
            
        Returns:
            Path to the saved file
        """
        if not self.last_response:
            error_msg = "No response to save"
            self.logger.warning(error_msg)
            return error_msg
            
        # Create export directory
        export_dir = Path(self.config.get('api_export_dir', 'exported_api'))
        export_dir.mkdir(exist_ok=True)
        
        # Generate filename if not provided
        if not filename:
            from urllib.parse import urlparse
            parsed_url = urlparse(self.last_url)
            base_name = os.path.basename(parsed_url.path) or "api_response"
            filename = f"{base_name}.json"
        
        # Ensure file has extension
        if not any(filename.endswith(ext) for ext in ['.json', '.xml', '.txt']):
            filename = f"{filename}.json"
        
        file_path = export_dir / filename
        
        try:
            content_type = self.last_response.headers.get('Content-Type', '')
            
            # Handle different content types
            if 'json' in content_type:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.last_response.json(), f, indent=2, ensure_ascii=False)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.last_response.text)
            
            self.logger.info(f"Response saved to: {file_path}")
            return f"Response saved to: {file_path}"
            
        except Exception as e:
            error_msg = f"Error saving response: {str(e)}"
            self.logger.error(error_msg)
            return error_msg
    
    def get_response_info(self) -> Dict[str, Any]:
        """
        Get information about the last response.
        
        Returns:
            Dictionary with response information
        """
        if not self.last_response:
            return {"error": "No response available"}
        
        info = {
            "url": self.last_url,
            "status_code": self.last_response.status_code,
            "content_type": self.last_response.headers.get('Content-Type'),
            "content_length": self.last_response.headers.get('Content-Length'),
            "elapsed": str(self.last_response.elapsed),
            "encoding": self.last_response.encoding,
            "headers": dict(self.last_response.headers),
        }
        
        # Add response body preview
        try:
            if 'json' in info['content_type']:
                response_json = self.last_response.json()
                if isinstance(response_json, list):
                    info['body_preview'] = f"List with {len(response_json)} items"
                    if response_json:
                        info['first_item'] = response_json[0]
                else:
                    info['body_preview'] = response_json
            else:
                info['body_preview'] = self.last_response.text[:500]
        except:
            info['body_preview'] = self.last_response.text[:500]
        
        return info
    
    def close(self) -> None:
        """Close the session and free resources."""
        self.session.close()
        self.logger.debug("API client session closed")
    
    def __enter__(self) -> 'APIClient':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with clean up."""
        self.close() 