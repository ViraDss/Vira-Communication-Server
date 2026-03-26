import asyncio
import logging
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from config import Config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.alerts_collection = None
        self.alert_images_collection = None
        self.is_connected = False
        self.change_stream = None

    async def connect(self):
        """Connect to MongoDB with proper SSL configuration"""
        try:
            logger.info("Connecting to MongoDB...")
            logger.info(f"Connection string: {Config.MONGODB_URI[:50]}...")
            
            # Add SSL parameters to connection string
            connection_string = Config.MONGODB_URI
            
            # If connection string doesn't have SSL parameters, add them
            if "ssl=true" not in connection_string and "tls=true" not in connection_string:
                if "?" in connection_string:
                    connection_string += "&ssl=true&ssl_cert_reqs=CERT_NONE"
                else:
                    connection_string += "?ssl=true&ssl_cert_reqs=CERT_NONE"
            
            logger.info(f"Final connection string: {connection_string[:50]}...")
            
            # Create client with proper SSL configuration
            self.client = AsyncIOMotorClient(
                connection_string,
                serverSelectionTimeoutMS=30000,  # Increased timeout
                connectTimeoutMS=30000,          # Increased timeout
                socketTimeoutMS=30000,           # Increased timeout
                maxPoolSize=10,
                retryWrites=True,
                w="majority"
            )
            
            # Test connection
            logger.info("Testing MongoDB connection...")
            await self.client.admin.command('ping')
            logger.info("MongoDB ping successful")
            
            # Set up database and collections
            self.db = self.client[Config.DATABASE_NAME]
            self.alerts_collection = self.db[Config.ALERTS_COLLECTION]
            self.alert_images_collection = self.db[Config.ALERT_IMAGES_COLLECTION]
            
            # Test database access
            logger.info(f"Testing database access: {Config.DATABASE_NAME}")
            await self.alerts_collection.count_documents({})
            await self.alert_images_collection.count_documents({})
            logger.info("Database access successful")
            
            self.is_connected = True
            logger.info("Successfully connected to MongoDB")
            
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failure: {e}")
            self.is_connected = False
            raise
        except ServerSelectionTimeoutError as e:
            logger.error(f"MongoDB server selection timeout: {e}")
            self.is_connected = False
            raise
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            self.is_connected = False
            raise
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        try:
            # Close change stream gracefully
            if self.change_stream:
                try:
                    await self.change_stream.close()
                    logger.info("Change stream closed successfully")
                except Exception as e:
                    if "operation was interrupted" in str(e) or "CursorKilled" in str(e):
                        logger.info("Change stream already closed during shutdown - this is normal")
                    else:
                        logger.error(f"Error closing change stream: {e}")
            
            # Close MongoDB client
            if self.client:
                try:
                    self.client.close()
                    logger.info("MongoDB client closed successfully")
                except Exception as e:
                    logger.error(f"Error closing MongoDB client: {e}")
                
            self.is_connected = False
            logger.info("Database disconnected successfully")
            
        except Exception as e:
            logger.error(f"Error during database disconnect: {e}")
            self.is_connected = False
    
    async def create_alert(self, alert_data: Dict[str, Any]) -> str:
        """Create a new alert"""
        try:
            if not self.is_connected:
                raise Exception("Database not connected")
            
            # Generate a unique alert_id if not provided
            if 'alert_id' not in alert_data or not alert_data['alert_id']:
                import uuid
                alert_data['alert_id'] = f"alert_{uuid.uuid4().hex[:8]}"
            
            # Add timestamp if not present
            if 'timestamp' not in alert_data:
                alert_data['timestamp'] = datetime.utcnow().isoformat()
            
            # Add created_at field
            alert_data['created_at'] = datetime.utcnow()
            
            # Set default values if not present
            if 'response' not in alert_data:
                alert_data['response'] = 0
            if 'image_received' not in alert_data:
                alert_data['image_received'] = 0
            if 'status' not in alert_data:
                alert_data['status'] = 'pending'
            
            result = await self.alerts_collection.insert_one(alert_data)
            logger.info(f"Created alert with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            raise
    
    async def insert_alert(self, alert_data: Dict[str, Any]) -> str:
        """Insert a new alert (alias for create_alert)"""
        return await self.create_alert(alert_data)
    
    async def update_alert(self, alert_id: str, update_data: Dict[str, Any]) -> bool:
        """Update alert with any data"""
        try:
            if not self.is_connected:
                raise Exception("Database not connected")
            
            from bson import ObjectId
            result = await self.alerts_collection.update_one(
                {'_id': ObjectId(alert_id)},
                {'$set': update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating alert {alert_id}: {e}")
            raise
    
    async def get_all_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all alerts"""
        try:
            if not self.is_connected:
                raise Exception("Database not connected")
            
            cursor = self.alerts_collection.find().sort('created_at', -1).limit(limit)
            alerts = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string and datetime to ISO format for JSON serialization
            for alert in alerts:
                if '_id' in alert:
                    alert['id'] = str(alert['_id'])
                    del alert['_id']
                
                # Convert datetime fields to ISO format strings
                if 'created_at' in alert and isinstance(alert['created_at'], datetime):
                    alert['created_at'] = alert['created_at'].isoformat()
                if 'updated_at' in alert and isinstance(alert['updated_at'], datetime):
                    alert['updated_at'] = alert['updated_at'].isoformat()
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            raise
    
    async def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific alert by ID"""
        try:
            if not self.is_connected:
                raise Exception("Database not connected")
            
            from bson import ObjectId
            alert = await self.alerts_collection.find_one({'_id': ObjectId(alert_id)})
            
            if alert:
                alert['id'] = str(alert['_id'])
                del alert['_id']
                
                # Convert datetime fields to ISO format strings
                if 'created_at' in alert and isinstance(alert['created_at'], datetime):
                    alert['created_at'] = alert['created_at'].isoformat()
                if 'updated_at' in alert and isinstance(alert['updated_at'], datetime):
                    alert['updated_at'] = alert['updated_at'].isoformat()
            
            return alert
            
        except Exception as e:
            logger.error(f"Error getting alert {alert_id}: {e}")
            raise
    
    async def update_alert_response(self, alert_id: str, response_data: Dict[str, Any]) -> bool:
        """Update alert response"""
        try:
            if not self.is_connected:
                raise Exception("Database not connected")
            
            from bson import ObjectId
            result = await self.alerts_collection.update_one(
                {'_id': ObjectId(alert_id)},
                {'$set': response_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating alert response: {e}")
            raise
    
    async def update_alert_image(self, alert_id: str, image_data: Dict[str, Any]) -> bool:
        """Update alert image"""
        try:
            if not self.is_connected:
                raise Exception("Database not connected")
            
            from bson import ObjectId
            result = await self.alerts_collection.update_one(
                {'_id': ObjectId(alert_id)},
                {'$set': image_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating alert image: {e}")
            raise
    
    
    async def start_change_stream(self, callback):
        """Start MongoDB change stream to watch for alert updates"""
        try:
            if not self.is_connected:
                logger.warning("Cannot start change stream: database not connected")
                return
            
            logger.info("Starting MongoDB change stream...")
            
            # Create change stream pipeline
            pipeline = [
                {
                    '$match': {
                        'operationType': {'$in': ['insert', 'update', 'replace']}
                    }
                }
            ]
            
            self.change_stream = self.alerts_collection.watch(pipeline)
            logger.info("MongoDB change stream created successfully")
            
            # Start listening for changes
            async for change in self.change_stream:
                try:
                    await callback(change)
                except Exception as e:
                    logger.error(f"Error in change stream callback: {e}")
                    
        except Exception as e:
            # Check if it's a shutdown-related error
            if "operation was interrupted" in str(e) or "CursorKilled" in str(e):
                logger.info("Change stream interrupted during shutdown - this is normal")
            else:
                logger.error(f"Error starting change stream: {e}")
            # Don't re-raise the exception to avoid blocking startup

    async def fix_database_schema(self):
        """Fix database schema issues"""
        try:
            if not self.is_connected:
                raise Exception("Database not connected")
            
            logger.info("Fixing database schema...")
            
            # Drop the problematic alert_id index if it exists
            try:
                await self.alerts_collection.drop_index("alert_id_1")
                logger.info("Dropped problematic alert_id index")
            except Exception as e:
                logger.info(f"alert_id index not found or already dropped: {e}")
            
            # Create a proper index on alert_id that allows null values
            try:
                await self.alerts_collection.create_index("alert_id", unique=True, sparse=True)
                logger.info("Created proper alert_id index with sparse option")
            except Exception as e:
                logger.info(f"alert_id index creation: {e}")
            
            # Create other useful indexes
            try:
                await self.alerts_collection.create_index("drone_id")
                await self.alerts_collection.create_index("created_at")
                await self.alerts_collection.create_index("status")
                logger.info("Created additional indexes")
            except Exception as e:
                logger.info(f"Additional index creation: {e}")
            
            # Create indexes for alert images collection
            try:
                await self.alert_images_collection.create_index("drone_id")
                await self.alert_images_collection.create_index("timestamp")
                await self.alert_images_collection.create_index("found")
                await self.alert_images_collection.create_index("name")
                logger.info("Created alert images indexes")
            except Exception as e:
                logger.info(f"Alert images index creation: {e}")
            
            logger.info("Database schema fixed successfully")
            
        except Exception as e:
            logger.error(f"Error fixing database schema: {e}")
            raise

    async def create_alert_image(self, alert_image_data: Dict[str, Any]) -> str:
        """Create a new alert image record"""
        try:
            if not self.is_connected:
                raise Exception("Database not connected")
            
            # Add created_at field
            alert_image_data['created_at'] = datetime.utcnow()
            result = await self.alert_images_collection.insert_one(alert_image_data)
            logger.info(f"Created alert image with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating alert image: {e}")
            raise


    async def get_alert_image(self, alert_image_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific alert image by ID"""
        try:
            if not self.is_connected:
                raise Exception("Database not connected")
            
            from bson import ObjectId
            alert_image = await self.alert_images_collection.find_one({'_id': ObjectId(alert_image_id)})
            
            if alert_image:
                alert_image['id'] = str(alert_image['_id'])
                del alert_image['_id']
                
                # Convert datetime fields to ISO format strings
                if 'created_at' in alert_image and isinstance(alert_image['created_at'], datetime):
                    alert_image['created_at'] = alert_image['created_at'].isoformat()
            
            return alert_image
            
        except Exception as e:
            logger.error(f"Error getting alert image {alert_image_id}: {e}")
            raise

    async def delete_alert_image(self, alert_image_id: str) -> bool:
        """Delete an alert image by ID"""
        try:
            if not self.is_connected:
                raise Exception("Database not connected")
            
            from bson import ObjectId
            result = await self.alert_images_collection.delete_one({'_id': ObjectId(alert_image_id)})
            
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error deleting alert image {alert_image_id}: {e}")
            raise

# Create global database manager instance
db_manager = DatabaseManager() 