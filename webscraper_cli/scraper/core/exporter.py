"""
Data export utilities for various formats.
"""
import csv
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, Any, Optional, List, Union, TextIO
from pathlib import Path
import pickle
import yaml
import zipfile
import io
import os
import datetime

from webscraper_cli.config import settings
from webscraper_cli.utils.logger import LoggerMixin
from webscraper_cli.utils.exceptions import ExportError

class DataExporter(LoggerMixin):
    """
    Exports scraped data to various formats.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data exporter.
        
        Args:
            config: Optional configuration override (default: use settings module)
        """
        self.config = config or settings.get_config()
        self.export_dir = Path(self.config.get('export_dir', 'exported_data'))
        self.export_dir.mkdir(exist_ok=True)
    
    def export_data(self, data_list: List[Dict[str, Any]], filename: Optional[str] = None, 
                   format: str = "json", **kwargs) -> str:
        """
        Export data to the specified format.
        
        Args:
            data_list: List of data dictionaries to export
            filename: Optional filename (generated if not provided)
            format: Export format (default: json)
            **kwargs: Additional options for specific formats
            
        Returns:
            Path to the exported file
            
        Raises:
            ExportError: If export fails or format is unsupported
        """
        try:
            # Validate data
            if not isinstance(data_list, list):
                raise ExportError("Data must be a list of dictionaries")
            
            if not data_list:
                self.logger.warning("Exporting empty data list")
            
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"scraper_data_{timestamp}"
            
            # Ensure file has the correct extension
            if not filename.endswith(f".{format}"):
                filename = f"{filename}.{format}"
            
            # Get the full path
            file_path = self.export_dir / filename
            
            # Export based on format
            if format.lower() == "csv":
                return self.export_to_csv(data_list, file_path, **kwargs)
            elif format.lower() == "json":
                return self.export_to_json(data_list, file_path, **kwargs)
            elif format.lower() == "xml":
                return self.export_to_xml(data_list, file_path, **kwargs)
            elif format.lower() == "pickle":
                return self.export_to_pickle(data_list, file_path, **kwargs)
            elif format.lower() == "yaml":
                return self.export_to_yaml(data_list, file_path, **kwargs)
            elif format.lower() == "excel":
                return self.export_to_excel(data_list, file_path, **kwargs)
            elif format.lower() == "zip":
                return self.export_to_zip(data_list, file_path, **kwargs)
            else:
                raise ExportError(f"Unsupported export format: {format}")
                
        except Exception as e:
            error_msg = f"Export error: {str(e)}"
            self.logger.error(error_msg)
            raise ExportError(error_msg)
    
    def export_to_csv(self, data_list: List[Dict[str, Any]], 
                     file_path: Union[str, Path], **kwargs) -> str:
        """
        Export data to CSV format.
        
        Args:
            data_list: List of data dictionaries to export
            file_path: Output file path
            **kwargs: Additional options (dialect, delimiter, etc.)
            
        Returns:
            Path to the exported file
        """
        try:
            # Ensure we have a Path object
            file_path = Path(file_path)
            
            # Create or validate header
            if data_list and isinstance(data_list[0], dict):
                # Use all keys from all dictionaries to ensure complete headers
                headers = set()
                for item in data_list:
                    headers.update(item.keys())
                headers = sorted(list(headers))
                
                # Get CSV options
                dialect = kwargs.get('dialect', 'excel')
                delimiter = kwargs.get('delimiter', ',')
                
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(
                        f, fieldnames=headers, dialect=dialect, 
                        delimiter=delimiter, extrasaction='ignore'
                    )
                    writer.writeheader()
                    writer.writerows(data_list)
                
                self.logger.info(f"Data exported to CSV: {file_path}")
                return str(file_path)
            else:
                raise ExportError("Data list is empty or not a list of dictionaries")
                
        except Exception as e:
            error_msg = f"CSV export error: {str(e)}"
            self.logger.error(error_msg)
            raise ExportError(error_msg)
    
    def export_to_json(self, data_list: List[Dict[str, Any]], 
                      file_path: Union[str, Path], **kwargs) -> str:
        """
        Export data to JSON format.
        
        Args:
            data_list: List of data dictionaries to export
            file_path: Output file path
            **kwargs: Additional options (indent, etc.)
            
        Returns:
            Path to the exported file
        """
        try:
            # Ensure we have a Path object
            file_path = Path(file_path)
            
            # Get JSON options
            indent = kwargs.get('indent', 4)
            ensure_ascii = kwargs.get('ensure_ascii', False)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_list, f, indent=indent, ensure_ascii=ensure_ascii, default=str)
            
            self.logger.info(f"Data exported to JSON: {file_path}")
            return str(file_path)
            
        except Exception as e:
            error_msg = f"JSON export error: {str(e)}"
            self.logger.error(error_msg)
            raise ExportError(error_msg)
    
    def export_to_xml(self, data_list: List[Dict[str, Any]], 
                     file_path: Union[str, Path], **kwargs) -> str:
        """
        Export data to XML format.
        
        Args:
            data_list: List of data dictionaries to export
            file_path: Output file path
            **kwargs: Additional options (root_name, item_name, etc.)
            
        Returns:
            Path to the exported file
        """
        try:
            # Ensure we have a Path object
            file_path = Path(file_path)
            
            # Get XML options
            root_name = kwargs.get('root_name', 'data')
            item_name = kwargs.get('item_name', 'item')
            
            # Create root element
            root = ET.Element(root_name)
            
            # Add items
            for item in data_list:
                item_elem = ET.SubElement(root, item_name)
                self._dict_to_xml(item, item_elem)
            
            # Format the XML string
            rough_string = ET.tostring(root, 'utf-8')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="  ")
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            
            self.logger.info(f"Data exported to XML: {file_path}")
            return str(file_path)
            
        except Exception as e:
            error_msg = f"XML export error: {str(e)}"
            self.logger.error(error_msg)
            raise ExportError(error_msg)
    
    def _dict_to_xml(self, d: Dict[str, Any], parent: ET.Element) -> None:
        """
        Convert a dictionary to XML elements.
        
        Args:
            d: Dictionary to convert
            parent: Parent XML element
        """
        for key, value in d.items():
            if isinstance(value, dict):
                child = ET.SubElement(parent, str(key))
                self._dict_to_xml(value, child)
            elif isinstance(value, list):
                child = ET.SubElement(parent, str(key))
                for item in value:
                    if isinstance(item, dict):
                        item_elem = ET.SubElement(child, 'item')
                        self._dict_to_xml(item, item_elem)
                    else:
                        item_elem = ET.SubElement(child, 'item')
                        item_elem.text = str(item)
            else:
                child = ET.SubElement(parent, str(key))
                child.text = str(value)
    
    def export_to_pickle(self, data_list: List[Dict[str, Any]], 
                        file_path: Union[str, Path], **kwargs) -> str:
        """
        Export data to Pickle format.
        
        Args:
            data_list: List of data dictionaries to export
            file_path: Output file path
            **kwargs: Additional options (protocol, etc.)
            
        Returns:
            Path to the exported file
        """
        try:
            # Ensure we have a Path object
            file_path = Path(file_path)
            
            # Get Pickle options
            protocol = kwargs.get('protocol', pickle.HIGHEST_PROTOCOL)
            
            with open(file_path, 'wb') as f:
                pickle.dump(data_list, f, protocol=protocol)
            
            self.logger.info(f"Data exported to Pickle: {file_path}")
            return str(file_path)
            
        except Exception as e:
            error_msg = f"Pickle export error: {str(e)}"
            self.logger.error(error_msg)
            raise ExportError(error_msg)
    
    def export_to_yaml(self, data_list: List[Dict[str, Any]], 
                      file_path: Union[str, Path], **kwargs) -> str:
        """
        Export data to YAML format.
        
        Args:
            data_list: List of data dictionaries to export
            file_path: Output file path
            **kwargs: Additional options
            
        Returns:
            Path to the exported file
        """
        try:
            # Ensure we have a Path object
            file_path = Path(file_path)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data_list, f, default_flow_style=False, allow_unicode=True)
            
            self.logger.info(f"Data exported to YAML: {file_path}")
            return str(file_path)
            
        except Exception as e:
            error_msg = f"YAML export error: {str(e)}"
            self.logger.error(error_msg)
            raise ExportError(error_msg)
    
    def export_to_excel(self, data_list: List[Dict[str, Any]], 
                       file_path: Union[str, Path], **kwargs) -> str:
        """
        Export data to Excel format.
        
        Args:
            data_list: List of data dictionaries to export
            file_path: Output file path
            **kwargs: Additional options (sheet_name, etc.)
            
        Returns:
            Path to the exported file
        """
        try:
            # Lazy import pandas to avoid dependency if not used
            import pandas as pd
            
            # Ensure we have a Path object
            file_path = Path(file_path)
            
            # Get Excel options
            sheet_name = kwargs.get('sheet_name', 'Data')
            
            # Convert to DataFrame and export
            df = pd.DataFrame(data_list)
            df.to_excel(file_path, sheet_name=sheet_name, index=False)
            
            self.logger.info(f"Data exported to Excel: {file_path}")
            return str(file_path)
            
        except ImportError:
            error_msg = "Excel export requires pandas and openpyxl packages"
            self.logger.error(error_msg)
            raise ExportError(error_msg)
        except Exception as e:
            error_msg = f"Excel export error: {str(e)}"
            self.logger.error(error_msg)
            raise ExportError(error_msg)
    
    def export_to_zip(self, data_list: List[Dict[str, Any]], 
                     file_path: Union[str, Path], **kwargs) -> str:
        """
        Export data to a ZIP file containing multiple formats.
        
        Args:
            data_list: List of data dictionaries to export
            file_path: Output file path
            **kwargs: Additional options (formats, etc.)
            
        Returns:
            Path to the exported file
        """
        try:
            # Ensure we have a Path object
            file_path = Path(file_path)
            
            # Get ZIP options
            formats = kwargs.get('formats', ['json', 'csv', 'xml'])
            
            # Create a temporary directory for files
            temp_dir = self.export_dir / "temp_zip"
            temp_dir.mkdir(exist_ok=True)
            
            try:
                # Export to each format
                exported_files = []
                for fmt in formats:
                    temp_file = temp_dir / f"data.{fmt}"
                    if fmt == 'json':
                        self.export_to_json(data_list, temp_file)
                    elif fmt == 'csv':
                        self.export_to_csv(data_list, temp_file)
                    elif fmt == 'xml':
                        self.export_to_xml(data_list, temp_file)
                    else:
                        self.logger.warning(f"Unsupported format for ZIP: {fmt}")
                        continue
                    
                    exported_files.append(temp_file)
                
                # Create ZIP file
                with zipfile.ZipFile(file_path, 'w') as zipf:
                    for file in exported_files:
                        zipf.write(file, file.name)
                
                self.logger.info(f"Data exported to ZIP: {file_path}")
                return str(file_path)
                
            finally:
                # Clean up temporary files
                for file in temp_dir.glob('*'):
                    try:
                        file.unlink()
                    except:
                        pass
                
                try:
                    temp_dir.rmdir()
                except:
                    pass
                
        except Exception as e:
            error_msg = f"ZIP export error: {str(e)}"
            self.logger.error(error_msg)
            raise ExportError(error_msg)


# Convenience functions using the default exporter

# Exporter instance
_exporter = None

def get_exporter() -> DataExporter:
    """
    Get the data exporter instance.
    
    Returns:
        Data exporter instance
    """
    global _exporter
    if _exporter is None:
        _exporter = DataExporter()
    return _exporter

def export_to_csv(data_list: List[Dict[str, Any]], filename: str = "results.csv", **kwargs) -> str:
    """
    Export data to CSV format.
    
    Args:
        data_list: List of data dictionaries to export
        filename: Output filename
        **kwargs: Additional options
        
    Returns:
        Path to the exported file
    """
    return get_exporter().export_to_csv(data_list, filename, **kwargs)

def export_to_json(data_list: List[Dict[str, Any]], filename: str = "results.json", **kwargs) -> str:
    """
    Export data to JSON format.
    
    Args:
        data_list: List of data dictionaries to export
        filename: Output filename
        **kwargs: Additional options
        
    Returns:
        Path to the exported file
    """
    return get_exporter().export_to_json(data_list, filename, **kwargs)

def export_to_xml(data_list: List[Dict[str, Any]], filename: str = "results.xml", **kwargs) -> str:
    """
    Export data to XML format.
    
    Args:
        data_list: List of data dictionaries to export
        filename: Output filename
        **kwargs: Additional options
        
    Returns:
        Path to the exported file
    """
    return get_exporter().export_to_xml(data_list, filename, **kwargs)

def export_data(data_list: List[Dict[str, Any]], filename: Optional[str] = None, 
               format: str = "json", **kwargs) -> str:
    """
    Export data to the specified format.
    
    Args:
        data_list: List of data dictionaries to export
        filename: Optional filename (generated if not provided)
        format: Export format (default: json)
        **kwargs: Additional options for specific formats
        
    Returns:
        Path to the exported file
    """
    return get_exporter().export_data(data_list, filename, format, **kwargs) 