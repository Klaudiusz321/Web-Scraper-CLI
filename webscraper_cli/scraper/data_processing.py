# scraper/data_processing.py
import re
from bs4 import BeautifulSoup
from collections import Counter
import pandas as pd
from textblob import TextBlob
import spacy
import datetime
from scraper.db import save_to_mongodb

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

def clean_text(raw_html: str) -> str:
    # 1. Remove HTML
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ")
    
    # 2. Remove special characters and normalize spaces
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # 3. Trim
    return text.strip().lower()

def get_top_words(cleaned_text: str, top_n: int = 10):
    words = cleaned_text.split()
    return Counter(words).most_common(top_n)

def analyze_sentiment(cleaned_text: str):
    analysis = TextBlob(cleaned_text)
    return analysis

def extract_entities(cleaned_text: str):
    doc = nlp(cleaned_text)
    return [ent for ent in doc.ents]

def create_dataframe(data_list: list) -> pd.DataFrame:
    return pd.DataFrame(data_list)

def process_and_save_data(url, html_content, text_elements=None):
   
    # Initialize the document to be stored
    document = {
        "url": url,
        "timestamp": datetime.datetime.now(),
        "raw_html_length": len(html_content) if html_content else 0,
        "processed": {}
    }
    
    # Process HTML content if available
    if html_content:
        cleaned = clean_text(html_content)
        document["processed"]["cleaned_text"] = cleaned[:1000]  # Store a preview
        document["processed"]["word_count"] = len(cleaned.split())
        
        # Extract top words
        top_words = get_top_words(cleaned)
        document["processed"]["top_words"] = dict(top_words)
        
        # Analyze sentiment
        sentiment = analyze_sentiment(cleaned)
        document["processed"]["sentiment"] = {
            "polarity": sentiment.polarity,
            "subjectivity": sentiment.subjectivity
        }
        
        # Extract entities
        entities = extract_entities(cleaned)
        document["processed"]["entities"] = [
            {"text": ent.text, "label": ent.label_} for ent in entities
        ]
    
    # Process individual text elements if available
    if text_elements:
        document["text_elements"] = {}
        for selector, text in text_elements.items():
            document["text_elements"][selector] = {
                "text": text[:500],  # Store a preview
                "length": len(text)
            }
    
    # Save to MongoDB
    result = save_to_mongodb(document)
    
    return {
        "mongodb_id": str(result),
        "document": document
    }

def process_dynamic_scrape(scraper, url):
   
    try:
        # Navigate to URL
        scraper.navigate(url)
        
        # Get HTML content
        html_content = scraper.get_html()
        
        # Get page title
        title = scraper.driver.title
        
        # Extract common text elements
        text_elements = {
            "title": title,
            "body": scraper.get_text("body") if scraper.element_exists("body") else "",
            "h1": scraper.get_text("h1") if scraper.element_exists("h1") else "",
            "p": scraper.get_text("p") if scraper.element_exists("p") else ""
        }
        
        # Process and save to MongoDB
        result = process_and_save_data(url, html_content, text_elements)
        
        return {
            "success": True,
            "url": url,
            "mongodb_id": result["mongodb_id"],
            "message": f"Data for {url} processed and saved to MongoDB"
        }
        
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "error": str(e),
            "message": f"Error processing {url}: {str(e)}"
        }
