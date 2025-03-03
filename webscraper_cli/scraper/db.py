# scraper/db.py

import sqlite3
import json
import os
import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId

# Ensure database directory exists
DB_DIR = "database"
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "scraper_data.db")

# MongoDB connection settings
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
MONGO_DB = os.environ.get('MONGO_DB', 'webscraper')
MONGO_COLLECTION = os.environ.get('MONGO_COLLECTION', 'scraped_data')

def init_db():
    """Initialize database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scraped_results (
        id INTEGER PRIMARY KEY,
        url TEXT,
        timestamp TEXT,
        title TEXT,
        data TEXT,
        created_at TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

def save_result(data: dict):
    """Save scraped result to database"""
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.datetime.now().isoformat()
    
    # Extract common fields
    url = data.get('url', '')
    timestamp = data.get('timestamp', now)
    title = data.get('title', '')
    
    # Convert entire data object to JSON string
    data_json = json.dumps(data, ensure_ascii=False)
    
    cursor.execute(
        'INSERT INTO scraped_results (url, timestamp, title, data, created_at) VALUES (?, ?, ?, ?, ?)',
        (url, timestamp, title, data_json, now)
    )
    
    conn.commit()
    conn.close()
    
    return cursor.lastrowid

def get_mongodb_client():
    """Get MongoDB client connection"""
    try:
        client = MongoClient(MONGO_URI)
        # Ping the server to check connection
        client.admin.command('ping')
        return client
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def save_to_mongodb(document):
    """
    Save document to MongoDB
    
    Args:
        document: Dictionary containing processed scrape data
        
    Returns:
        MongoDB ObjectId of inserted document
    """
    client = get_mongodb_client()
    
    if not client:
        raise ConnectionError("Could not connect to MongoDB")
    
    try:
        db = client[MONGO_DB]
        collection = db[MONGO_COLLECTION]
        
        # Add metadata
        if "metadata" not in document:
            document["metadata"] = {}
        
        document["metadata"]["created_at"] = datetime.datetime.now()
        document["metadata"]["source"] = "web_scraper_cli"
        
        # Insert document
        result = collection.insert_one(document)
        
        # Return the ID of the inserted document
        return result.inserted_id
    
    except Exception as e:
        raise Exception(f"Error saving to MongoDB: {e}")
    
    finally:
        client.close()

def get_from_mongodb(query=None, limit=10):
    """
    Retrieve documents from MongoDB
    
    Args:
        query: MongoDB query dict
        limit: Maximum number of documents to return
        
    Returns:
        List of documents
    """
    client = get_mongodb_client()
    
    if not client:
        return []
    
    try:
        db = client[MONGO_DB]
        collection = db[MONGO_COLLECTION]
        
        if query is None:
            query = {}
        
        cursor = collection.find(query).limit(limit)
        
        # Convert ObjectId to string for JSON serialization
        results = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            results.append(doc)
        
        return results
    
    except Exception as e:
        print(f"Error retrieving from MongoDB: {e}")
        return []
    
    finally:
        client.close()

def delete_from_mongodb(document_id):
    """
    Delete document from MongoDB by ID
    
    Args:
        document_id: String or ObjectId of document to delete
        
    Returns:
        Boolean indicating success
    """
    client = get_mongodb_client()
    
    if not client:
        return False
    
    try:
        db = client[MONGO_DB]
        collection = db[MONGO_COLLECTION]
        
        # Convert string ID to ObjectId if needed
        if isinstance(document_id, str):
            document_id = ObjectId(document_id)
        
        result = collection.delete_one({'_id': document_id})
        return result.deleted_count > 0
    
    except Exception as e:
        print(f"Error deleting from MongoDB: {e}")
        return False
    
    finally:
        client.close()
