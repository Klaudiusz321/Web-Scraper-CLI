"""
Data processing and analysis utilities.
"""
import re
from typing import Dict, Any, Optional, List, Tuple, Union
import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from collections import Counter
import pandas as pd
import numpy as np
from textblob import TextBlob
import spacy
import concurrent.futures
from urllib.parse import urlparse

from webscraper_cli.config import settings
from webscraper_cli.utils.logger import LoggerMixin
from webscraper_cli.utils.exceptions import DatabaseError
from webscraper_cli.scraper.core.database import save_to_mongodb, save_to_sqlite

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # If model is not installed, use basic model
    import spacy.blank
    nlp = spacy.blank("en")

class DataProcessor(LoggerMixin):
    """
    Processes HTML and text data from web scraping.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data processor.
        
        Args:
            config: Optional configuration override (default: use settings module)
        """
        self.config = config or settings.get_config()
    
    def clean_text(self, raw_html: str) -> str:
        """
        Clean text from HTML, removing tags and special characters.
        
        Args:
            raw_html: Raw HTML content
            
        Returns:
            Cleaned text
        """
        try:
            # 1. Remove HTML
            soup = BeautifulSoup(raw_html, "html.parser")
            
            # Remove script and style elements
            for script_or_style in soup(["script", "style"]):
                script_or_style.extract()
                
            text = soup.get_text(separator=" ")
            
            # 2. Remove special characters and normalize spaces
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'[^\w\s]', ' ', text)
            
            # 3. Trim
            return text.strip().lower()
            
        except Exception as e:
            self.logger.error(f"Error cleaning text: {str(e)}")
            return ""
    
    def get_top_words(self, cleaned_text: str, top_n: int = 10, 
                     exclude_words: Optional[List[str]] = None) -> List[Tuple[str, int]]:
        """
        Get the most common words in the text.
        
        Args:
            cleaned_text: Cleaned text to analyze
            top_n: Number of top words to return
            exclude_words: Optional list of words to exclude
            
        Returns:
            List of (word, count) tuples
        """
        if not cleaned_text:
            return []
            
        # Default stopwords to exclude
        if exclude_words is None:
            exclude_words = ["the", "and", "is", "in", "to", "a", "of", "for", "on", "with"]
        
        # Tokenize and filter words
        words = cleaned_text.split()
        filtered_words = [word for word in words if word not in exclude_words and len(word) > 2]
        
        # Count and return top words
        return Counter(filtered_words).most_common(top_n)
    
    def analyze_sentiment(self, cleaned_text: str) -> Dict[str, float]:
        """
        Analyze the sentiment of the text.
        
        Args:
            cleaned_text: Cleaned text to analyze
            
        Returns:
            Dictionary with sentiment scores
        """
        if not cleaned_text:
            return {"polarity": 0.0, "subjectivity": 0.0}
            
        analysis = TextBlob(cleaned_text)
        return {
            "polarity": analysis.sentiment.polarity,
            "subjectivity": analysis.sentiment.subjectivity
        }
    
    def extract_entities(self, cleaned_text: str) -> List[Dict[str, str]]:
        """
        Extract named entities from the text.
        
        Args:
            cleaned_text: Cleaned text to analyze
            
        Returns:
            List of entity dictionaries
        """
        if not cleaned_text:
            return []
            
        # Limit text length to avoid performance issues
        if len(cleaned_text) > 10000:
            cleaned_text = cleaned_text[:10000]
            
        doc = nlp(cleaned_text)
        
        return [{"text": ent.text, "label": ent.label_} for ent in doc.ents]
    
    def create_dataframe(self, data_list: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Create a pandas DataFrame from a list of dictionaries.
        
        Args:
            data_list: List of data dictionaries
            
        Returns:
            Pandas DataFrame
        """
        return pd.DataFrame(data_list)
    
    def process_and_save_data(self, url: str, html_content: Optional[str] = None, 
                             text_elements: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Process and save scraped data.
        
        Args:
            url: URL of the scraped page
            html_content: Optional HTML content
            text_elements: Optional dictionary of text elements
            
        Returns:
            Dictionary with processing results
        """
        # Initialize the document to be stored
        document = {
            "url": url,
            "timestamp": datetime.datetime.now().isoformat(),
            "domain": urlparse(url).netloc,
            "raw_html_length": len(html_content) if html_content else 0,
            "processed": {}
        }
        
        # Process HTML content if available
        if html_content:
            cleaned = self.clean_text(html_content)
            document["processed"]["cleaned_text"] = cleaned[:1000]  # Store a preview
            document["processed"]["word_count"] = len(cleaned.split())
            
            # Extract top words
            top_words = self.get_top_words(cleaned)
            document["processed"]["top_words"] = dict(top_words)
            
            # Analyze sentiment
            sentiment = self.analyze_sentiment(cleaned)
            document["processed"]["sentiment"] = sentiment
            
            # Extract entities
            entities = self.extract_entities(cleaned)
            document["processed"]["entities"] = entities
        
        # Process individual text elements if available
        if text_elements:
            document["text_elements"] = {}
            for selector, text in text_elements.items():
                document["text_elements"][selector] = {
                    "text": text[:500],  # Store a preview
                    "length": len(text)
                }
                
                # Process this element if it's substantial
                if len(text) > 100:
                    document["text_elements"][selector]["sentiment"] = self.analyze_sentiment(text)
        
        # Save to databases
        try:
            # Save to MongoDB
            mongodb_id = save_to_mongodb(document)
            document["mongodb_id"] = str(mongodb_id)
            
            # Save to SQLite (without the full HTML to save space)
            document_for_sqlite = document.copy()
            if "raw_html" in document_for_sqlite:
                del document_for_sqlite["raw_html"]
            sqlite_id = save_to_sqlite(document_for_sqlite)
            document["sqlite_id"] = sqlite_id
            
        except DatabaseError as e:
            self.logger.error(f"Error saving data: {str(e)}")
            document["error"] = str(e)
        
        return document
    
    def process_dynamic_scrape(self, scraper, url: str) -> Dict[str, Any]:
        """
        Process a dynamic scraping session.
        
        Args:
            scraper: WebScraper instance
            url: URL to scrape
            
        Returns:
            Dictionary with processing results
        """
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
                "h2": ", ".join([scraper.get_text(f"h2:nth-of-type({i+1})") for i in range(3) 
                                if scraper.element_exists(f"h2:nth-of-type({i+1})")]),
                "p": ", ".join([scraper.get_text(f"p:nth-of-type({i+1})") for i in range(5) 
                              if scraper.element_exists(f"p:nth-of-type({i+1})")]),
                "meta_description": scraper.get_attribute("meta[name='description']", "content") 
                                   if scraper.element_exists("meta[name='description']") else ""
            }
            
            # Extract links
            if scraper.element_exists("a"):
                try:
                    links = scraper.driver.find_elements_by_tag_name("a")
                    text_elements["links"] = ", ".join([link.get_attribute("href") for link in links[:10] 
                                                      if link.get_attribute("href")])
                except:
                    text_elements["links"] = ""
            
            # Process and save to databases
            result = self.process_and_save_data(url, html_content, text_elements)
            
            return {
                "success": True,
                "url": url,
                "mongodb_id": result.get("mongodb_id", ""),
                "sqlite_id": result.get("sqlite_id", ""),
                "message": f"Data for {url} processed and saved",
                "title": title,
                "text_preview": text_elements.get("body", "")[:100] + "..." if text_elements.get("body", "") else ""
            }
            
        except Exception as e:
            self.logger.error(f"Error processing {url}: {str(e)}")
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "message": f"Error processing {url}: {str(e)}"
            }
    
    def batch_process_urls(self, scraper, urls: List[str], 
                          max_workers: int = 1) -> List[Dict[str, Any]]:
        """
        Process multiple URLs in sequence or parallel.
        
        Args:
            scraper: WebScraper instance
            urls: List of URLs to process
            max_workers: Maximum number of parallel workers (1 = sequential)
            
        Returns:
            List of processing results
        """
        results = []
        
        # Sequential processing
        if max_workers <= 1:
            for url in urls:
                result = self.process_dynamic_scrape(scraper, url)
                results.append(result)
                if not result["success"]:
                    self.logger.warning(f"Failed to process {url}: {result.get('error', 'Unknown error')}")
        
        # Parallel processing with multiple browser instances
        # Note: This is not fully implemented here, would require creating multiple WebScraper instances
        else:
            self.logger.warning("Parallel processing not fully implemented")
            for url in urls:
                result = self.process_dynamic_scrape(scraper, url)
                results.append(result)
        
        return results
    
    def generate_report(self, results: List[Dict[str, Any]], 
                       output_format: str = "json") -> Union[str, pd.DataFrame]:
        """
        Generate a report from processing results.
        
        Args:
            results: List of processing results
            output_format: Output format (json, csv, dataframe)
            
        Returns:
            Report in specified format
        """
        # Create a more readable summary
        summary = []
        for result in results:
            summary_item = {
                "url": result.get("url", ""),
                "success": result.get("success", False),
                "title": result.get("title", ""),
                "text_preview": result.get("text_preview", ""),
                "mongodb_id": result.get("mongodb_id", ""),
                "sqlite_id": result.get("sqlite_id", ""),
                "error": result.get("error", "")
            }
            summary.append(summary_item)
        
        # Convert to DataFrame
        df = pd.DataFrame(summary)
        
        # Return in requested format
        if output_format == "dataframe":
            return df
        elif output_format == "csv":
            return df.to_csv(index=False)
        else:  # json
            return df.to_json(orient="records") 