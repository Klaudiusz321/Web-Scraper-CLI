"""
Database access and operations.
"""
import sqlite3
import json
import os
import datetime
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
from pymongo import MongoClient, errors as mongo_errors
from bson.objectid import ObjectId
import threading
from contextlib import contextmanager
import atexit

from webscraper_cli.config import settings
from webscraper_cli.utils.logger import LoggerMixin
from webscraper_cli.utils.exceptions import DatabaseError
from webscraper_cli.utils.retry import retry

class DatabaseManager(LoggerMixin):
    """
    Base class for database managers.
    """
    pass


class SQLiteManager(DatabaseManager):
    """
    SQLite database manager with connection pooling.
    """
    
    # Thread-local storage for connections
    _local = threading.local()
    _pool_lock = threading.Lock()
    _pool = {}  # Connection pool
    
    def __init__(self, db_path: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize SQLite database manager.
        
        Args:
            db_path: Optional database path (default: from settings)
            config: Optional configuration override (default: use settings module)
        """
        self.config = config or settings.get_config()
        self.db_path = db_path or self.config.get('db_path')
        
        if not self.db_path:
            db_dir = Path(self.config.get('database_dir', 'database'))
            db_dir.mkdir(exist_ok=True)
            self.db_path = str(db_dir / "scraper_data.db")
        
        self.logger.info(f"SQLite database initialized: {self.db_path}")
        self._init_db()
        
        # Register cleanup on program exit
        atexit.register(self.close_all_connections)
    
    @classmethod
    def close_all_connections(cls):
        """Close all connections in the pool."""
        with cls._pool_lock:
            for conn in cls._pool.values():
                try:
                    conn.close()
                except:
                    pass
            cls._pool.clear()
    
    @contextmanager
    def get_connection(self) -> sqlite3.Connection:
        """
        Get a connection from the pool or create a new one.
        
        Returns:
            SQLite connection
            
        Raises:
            DatabaseError: If connection fails
        """
        # Check if we already have a connection for this thread
        if not hasattr(self._local, 'connection'):
            # Create a new connection
            try:
                thread_id = threading.get_ident()
                
                with self._pool_lock:
                    # Check if we have a connection in the pool for this thread
                    if thread_id in self._pool:
                        conn = self._pool[thread_id]
                    else:
                        # Create a new connection
                        conn = sqlite3.connect(self.db_path)
                        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                        self._pool[thread_id] = conn
                
                # Set the local thread connection
                self._local.connection = conn
                
            except sqlite3.Error as e:
                error_msg = f"SQLite connection error: {str(e)}"
                self.logger.error(error_msg)
                raise DatabaseError(error_msg)
        
        try:
            # Return the connection
            yield self._local.connection
        except sqlite3.Error as e:
            error_msg = f"SQLite error: {str(e)}"
            self.logger.error(error_msg)
            raise DatabaseError(error_msg)
    
    def _init_db(self) -> None:
        """Initialize database with required tables."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Create scraped_results table
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
                
                # Create configuration table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS configuration (
                    id INTEGER PRIMARY KEY,
                    key TEXT UNIQUE,
                    value TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                ''')
                
                conn.commit()
                
                self.logger.debug("SQLite database tables initialized")
        except Exception as e:
            error_msg = f"Failed to initialize SQLite database: {str(e)}"
            self.logger.error(error_msg)
            raise DatabaseError(error_msg)
    
    def save_result(self, data: Dict[str, Any]) -> int:
        """
        Save a scraping result to the database.
        
        Args:
            data: Dictionary of data to save
            
        Returns:
            ID of the inserted record
            
        Raises:
            DatabaseError: If save fails
        """
        try:
            with self.get_connection() as conn:
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
                
                self.logger.info(f"Saved result for URL: {url}")
                return cursor.lastrowid
                
        except Exception as e:
            error_msg = f"Failed to save result to SQLite: {str(e)}"
            self.logger.error(error_msg)
            raise DatabaseError(error_msg)
    
    def get_results(self, limit: int = 100, url_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get scraping results from the database.
        
        Args:
            limit: Maximum number of results to return
            url_filter: Optional URL filter
            
        Returns:
            List of results
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if url_filter:
                    cursor.execute(
                        'SELECT * FROM scraped_results WHERE url LIKE ? ORDER BY id DESC LIMIT ?',
                        (f'%{url_filter}%', limit)
                    )
                else:
                    cursor.execute(
                        'SELECT * FROM scraped_results ORDER BY id DESC LIMIT ?',
                        (limit,)
                    )
                
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    data = json.loads(row['data'])
                    data['id'] = row['id']
                    results.append(data)
                
                self.logger.debug(f"Retrieved {len(results)} results from SQLite")
                return results
                
        except Exception as e:
            error_msg = f"Failed to get results from SQLite: {str(e)}"
            self.logger.error(error_msg)
            raise DatabaseError(error_msg)
    
    def delete_result(self, result_id: int) -> bool:
        """
        Delete a scraping result from the database.
        
        Args:
            result_id: ID of the result to delete
            
        Returns:
            True if deleted, False otherwise
            
        Raises:
            DatabaseError: If delete fails
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    'DELETE FROM scraped_results WHERE id = ?',
                    (result_id,)
                )
                
                conn.commit()
                
                deleted = cursor.rowcount > 0
                if deleted:
                    self.logger.info(f"Deleted result with ID: {result_id}")
                else:
                    self.logger.warning(f"No result found with ID: {result_id}")
                
                return deleted
                
        except Exception as e:
            error_msg = f"Failed to delete result from SQLite: {str(e)}"
            self.logger.error(error_msg)
            raise DatabaseError(error_msg)


class MongoDBManager(DatabaseManager):
    """
    MongoDB database manager with connection pooling.
    """
    
    # Connection pool
    _clients = {}
    _pool_lock = threading.Lock()
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize MongoDB database manager.
        
        Args:
            config: Optional configuration override (default: use settings module)
        """
        self.config = config or settings.get_config()
        self.mongo_uri = self.config.get('mongo_uri', 'mongodb://localhost:27017/')
        self.db_name = self.config.get('mongo_db', 'webscraper')
        self.collection_name = self.config.get('mongo_collection', 'scraped_data')
        
        self.logger.info(f"MongoDB initialized: {self.db_name}.{self.collection_name}")
        
        # Register cleanup on program exit
        atexit.register(self.close_all_connections)
    
    @classmethod
    def close_all_connections(cls):
        """Close all connections in the pool."""
        with cls._pool_lock:
            for client in cls._clients.values():
                try:
                    client.close()
                except:
                    pass
            cls._clients.clear()
    
    @retry(exceptions=(mongo_errors.ConnectionFailure, mongo_errors.ServerSelectionTimeoutError))
    def get_client(self) -> MongoClient:
        """
        Get a MongoDB client from the pool or create a new one.
        
        Returns:
            MongoDB client
            
        Raises:
            DatabaseError: If connection fails
        """
        uri = self.mongo_uri
        
        with self._pool_lock:
            if uri not in self._clients:
                try:
                    client = MongoClient(uri)
                    # Test the connection
                    client.admin.command('ping')
                    self._clients[uri] = client
                    self.logger.debug("Created new MongoDB connection")
                except Exception as e:
                    error_msg = f"MongoDB connection error: {str(e)}"
                    self.logger.error(error_msg)
                    raise DatabaseError(error_msg)
            
            return self._clients[uri]
    
    def get_db(self):
        """
        Get the MongoDB database.
        
        Returns:
            MongoDB database
        """
        client = self.get_client()
        return client[self.db_name]
    
    def get_collection(self):
        """
        Get the MongoDB collection.
        
        Returns:
            MongoDB collection
        """
        db = self.get_db()
        return db[self.collection_name]
    
    def save_document(self, document: Dict[str, Any]) -> str:
        """
        Save a document to MongoDB.
        
        Args:
            document: Document to save
            
        Returns:
            ID of the inserted document
            
        Raises:
            DatabaseError: If save fails
        """
        try:
            collection = self.get_collection()
            
            # Add metadata
            if "metadata" not in document:
                document["metadata"] = {}
            
            document["metadata"]["created_at"] = datetime.datetime.now()
            document["metadata"]["source"] = "web_scraper_cli"
            
            # Insert document
            result = collection.insert_one(document)
            
            self.logger.info(f"Saved document to MongoDB with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            error_msg = f"Failed to save document to MongoDB: {str(e)}"
            self.logger.error(error_msg)
            raise DatabaseError(error_msg)
    
    def get_documents(self, query: Optional[Dict[str, Any]] = None, 
                     limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get documents from MongoDB.
        
        Args:
            query: Optional query filter
            limit: Maximum number of documents to return
            
        Returns:
            List of documents
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            collection = self.get_collection()
            
            if query is None:
                query = {}
            
            cursor = collection.find(query).limit(limit)
            
            # Convert ObjectId to string for JSON serialization
            results = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                results.append(doc)
            
            self.logger.debug(f"Retrieved {len(results)} documents from MongoDB")
            return results
            
        except Exception as e:
            error_msg = f"Failed to get documents from MongoDB: {str(e)}"
            self.logger.error(error_msg)
            raise DatabaseError(error_msg)
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from MongoDB.
        
        Args:
            document_id: ID of the document to delete
            
        Returns:
            True if deleted, False otherwise
            
        Raises:
            DatabaseError: If delete fails
        """
        try:
            collection = self.get_collection()
            
            # Convert string ID to ObjectId if needed
            if isinstance(document_id, str):
                document_id = ObjectId(document_id)
            
            result = collection.delete_one({'_id': document_id})
            
            deleted = result.deleted_count > 0
            if deleted:
                self.logger.info(f"Deleted document with ID: {document_id}")
            else:
                self.logger.warning(f"No document found with ID: {document_id}")
            
            return deleted
            
        except Exception as e:
            error_msg = f"Failed to delete document from MongoDB: {str(e)}"
            self.logger.error(error_msg)
            raise DatabaseError(error_msg)


# Convenience functions using the default database managers

# SQLite manager instance
_sqlite_manager = None

def get_sqlite_manager() -> SQLiteManager:
    """
    Get the SQLite manager instance.
    
    Returns:
        SQLite manager instance
    """
    global _sqlite_manager
    if _sqlite_manager is None:
        _sqlite_manager = SQLiteManager()
    return _sqlite_manager

# MongoDB manager instance
_mongodb_manager = None

def get_mongodb_manager() -> MongoDBManager:
    """
    Get the MongoDB manager instance.
    
    Returns:
        MongoDB manager instance
    """
    global _mongodb_manager
    if _mongodb_manager is None:
        _mongodb_manager = MongoDBManager()
    return _mongodb_manager

# Convenience functions for SQLite

def save_to_sqlite(data: Dict[str, Any]) -> int:
    """
    Save data to SQLite.
    
    Args:
        data: Data to save
        
    Returns:
        ID of the inserted record
    """
    return get_sqlite_manager().save_result(data)

def get_from_sqlite(limit: int = 100, url_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get data from SQLite.
    
    Args:
        limit: Maximum number of results to return
        url_filter: Optional URL filter
        
    Returns:
        List of results
    """
    return get_sqlite_manager().get_results(limit, url_filter)

def delete_from_sqlite(result_id: int) -> bool:
    """
    Delete data from SQLite.
    
    Args:
        result_id: ID of the result to delete
        
    Returns:
        True if deleted, False otherwise
    """
    return get_sqlite_manager().delete_result(result_id)

# Convenience functions for MongoDB

def save_to_mongodb(document: Dict[str, Any]) -> str:
    """
    Save document to MongoDB.
    
    Args:
        document: Document to save
        
    Returns:
        ID of the inserted document
    """
    return get_mongodb_manager().save_document(document)

def get_from_mongodb(query: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get documents from MongoDB.
    
    Args:
        query: Optional query filter
        limit: Maximum number of documents to return
        
    Returns:
        List of documents
    """
    return get_mongodb_manager().get_documents(query, limit)

def delete_from_mongodb(document_id: str) -> bool:
    """
    Delete document from MongoDB.
    
    Args:
        document_id: ID of the document to delete
        
    Returns:
        True if deleted, False otherwise
    """
    return get_mongodb_manager().delete_document(document_id) 