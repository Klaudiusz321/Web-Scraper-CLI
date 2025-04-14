"""
Unit tests for the API client module.
"""
import unittest
from unittest.mock import patch, MagicMock
import json
import tempfile
from pathlib import Path

from webscraper_cli.scraper.core.api_client import APIClient

class TestAPIClient(unittest.TestCase):
    """Test the API client functionality."""
    
    def setUp(self):
        """Set up the test environment."""
        self.api_client = APIClient()
        
        # Create a mock response
        self.mock_response = MagicMock()
        self.mock_response.status_code = 200
        self.mock_response.headers = {"Content-Type": "application/json"}
        self.mock_response.text = '{"id": 1, "name": "Test"}'
        self.mock_response.json.return_value = {"id": 1, "name": "Test"}
        
        # Create a temporary directory for test exports
        self.temp_dir = Path(tempfile.mkdtemp())
        self.api_client.config = {"api_export_dir": str(self.temp_dir)}
    
    def tearDown(self):
        """Clean up after each test."""
        # Delete temporary test files
        for file in self.temp_dir.glob("*"):
            try:
                file.unlink()
            except:
                pass
        
        try:
            self.temp_dir.rmdir()
        except:
            pass
    
    @patch('webscraper_cli.scraper.core.api_client.requests.Session.get')
    def test_get_request(self, mock_get):
        """Test making a GET request."""
        # Configure the mock
        mock_get.return_value = self.mock_response
        
        # Make the request
        response = self.api_client.get("https://api.example.com/data")
        
        # Check that the mock was called correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://api.example.com/data")
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1, "name": "Test"})
    
    @patch('webscraper_cli.scraper.core.api_client.requests.Session.post')
    def test_post_request(self, mock_post):
        """Test making a POST request."""
        # Configure the mock
        mock_post.return_value = self.mock_response
        
        # Make the request
        json_data = {"key": "value"}
        response = self.api_client.post("https://api.example.com/data", json_data=json_data)
        
        # Check that the mock was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.example.com/data")
        self.assertEqual(kwargs["json"], json_data)
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1, "name": "Test"})
    
    def test_set_header(self):
        """Test setting a header."""
        self.api_client.set_header("X-API-Key", "12345")
        self.assertEqual(self.api_client.headers["X-API-Key"], "12345")
    
    def test_set_auth_basic(self):
        """Test setting basic authentication."""
        self.api_client.set_auth_basic("username", "password")
        self.assertIsNotNone(self.api_client.auth)
    
    def test_set_auth_token(self):
        """Test setting token authentication."""
        self.api_client.set_auth_token("abcdef123456")
        self.assertEqual(self.api_client.headers["Authorization"], "Bearer abcdef123456")
    
    @patch('webscraper_cli.scraper.core.api_client.requests.Session.get')
    def test_save_response(self, mock_get):
        """Test saving a response to a file."""
        # Configure the mock
        mock_get.return_value = self.mock_response
        
        # Make a request and save the response
        self.api_client.get("https://api.example.com/data")
        file_path = self.api_client.save_response("test_response.json")
        
        # Check that the file exists and contains the expected data
        output_file = self.temp_dir / "test_response.json"
        self.assertTrue(output_file.exists())
        
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(data, {"id": 1, "name": "Test"})
    
    @patch('webscraper_cli.scraper.core.api_client.requests.Session.get')
    def test_get_response_info(self, mock_get):
        """Test getting response information."""
        # Configure the mock
        mock_get.return_value = self.mock_response
        
        # Make a request
        self.api_client.get("https://api.example.com/data")
        
        # Get response info
        info = self.api_client.get_response_info()
        
        # Check the info
        self.assertEqual(info["status_code"], 200)
        self.assertEqual(info["content_type"], "application/json")
        self.assertEqual(info["url"], "https://api.example.com/data")
        self.assertIn("body_preview", info)

if __name__ == "__main__":
    unittest.main() 