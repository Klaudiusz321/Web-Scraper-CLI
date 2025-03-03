# scraper/exporter.py
import csv
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

def export_to_csv(data_list, filename="results.csv"):
    # Create or validate header
    if data_list and isinstance(data_list[0], dict):
        headers = list(data_list[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data_list)

def export_to_json(data_list, filename="results.json"):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data_list, f, indent=4, ensure_ascii=False)

def export_to_xml(data_list, filename="results.xml"):
    root = ET.Element("data")
    
    for item in data_list:
        item_elem = ET.SubElement(root, "item")
        for key, value in item.items():
            child = ET.SubElement(item_elem, key)
            child.text = str(value)
    
    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(pretty_xml)
