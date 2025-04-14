"""
Unit tests for the exporter module.
"""
import unittest
import os
import json
import csv
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

from webscraper_cli.scraper.core.exporter import DataExporter, export_to_json, export_to_csv, export_to_xml

class TestExporter(unittest.TestCase):
    """Test the data exporter functionality."""
    
    def setUp(self):
        """Set up the test environment."""
        self.exporter = DataExporter()
        
        # Create a temporary directory for test exports
        self.temp_dir = Path(tempfile.mkdtemp())
        self.exporter.export_dir = self.temp_dir
        
        # Sample test data
        self.test_data = [
            {"url": "https://example.com", "title": "Example Domain", "status": 200},
            {"url": "https://example.org", "title": "Example.org", "status": 200},
        ]
    
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
    
    def test_json_export(self):
        """Test exporting to JSON format."""
        file_path = self.temp_dir / "test_export.json"
        result = self.exporter.export_to_json(self.test_data, file_path)
        
        # Check that the file exists
        self.assertTrue(file_path.exists())
        
        # Check that the content is valid JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["url"], "https://example.com")
            self.assertEqual(data[1]["title"], "Example.org")
    
    def test_csv_export(self):
        """Test exporting to CSV format."""
        file_path = self.temp_dir / "test_export.csv"
        result = self.exporter.export_to_csv(self.test_data, file_path)
        
        # Check that the file exists
        self.assertTrue(file_path.exists())
        
        # Check that the content is valid CSV
        with open(file_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["url"], "https://example.com")
            self.assertEqual(rows[1]["title"], "Example.org")
    
    def test_xml_export(self):
        """Test exporting to XML format."""
        file_path = self.temp_dir / "test_export.xml"
        result = self.exporter.export_to_xml(self.test_data, file_path)
        
        # Check that the file exists
        self.assertTrue(file_path.exists())
        
        # Check that the content is valid XML
        tree = ET.parse(file_path)
        root = tree.getroot()
        items = root.findall(".//item")
        self.assertEqual(len(items), 2)
        
        # Find and check values
        urls = root.findall(".//item/url")
        self.assertEqual(urls[0].text, "https://example.com")
        self.assertEqual(urls[1].text, "https://example.org")
    
    def test_export_data_function(self):
        """Test the export_data function with different formats."""
        # Test JSON export
        json_path = self.exporter.export_data(self.test_data, "test_data.json", "json")
        self.assertTrue(Path(json_path).exists())
        
        # Test CSV export
        csv_path = self.exporter.export_data(self.test_data, "test_data.csv", "csv")
        self.assertTrue(Path(csv_path).exists())
        
        # Test XML export
        xml_path = self.exporter.export_data(self.test_data, "test_data.xml", "xml")
        self.assertTrue(Path(xml_path).exists())
    
    def test_convenience_functions(self):
        """Test the convenience export functions."""
        # Using absolute paths for testing
        json_path = str(self.temp_dir / "func_test.json")
        csv_path = str(self.temp_dir / "func_test.csv")
        xml_path = str(self.temp_dir / "func_test.xml")
        
        # Test each function
        export_to_json(self.test_data, json_path)
        export_to_csv(self.test_data, csv_path)
        export_to_xml(self.test_data, xml_path)
        
        # Verify files exist
        self.assertTrue(os.path.exists(json_path))
        self.assertTrue(os.path.exists(csv_path))
        self.assertTrue(os.path.exists(xml_path))

if __name__ == "__main__":
    unittest.main() 