import asyncio
import logging
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import json
from typing import List, Dict, Any
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends

from config import Config
from database import db_manager
from websocket_manager import websocket_manager
from models import AlertCreate, AlertResponse, AlertImageUpdate, AlertImageCreate, ProcessingTaskCreate
from client_registry import client_registry, get_registry_stats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Drone Alert Management System...")
    
    # Connect to database
    try:
        await db_manager.connect()
        
        # Fix database schema if needed
        try:
            await db_manager.fix_database_schema()
        except Exception as e:
            logger.warning(f"Database schema fix failed (non-critical): {e}")
            
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        # Continue without database for now
    

    
    # MongoDB Change → change_stream_callback() → serialize_datetime() → broadcast_to_applications() → Connected Apps Receive Update

    # Start change stream to watch for alert updates (non-blocking)
    async def change_stream_callback(change_event: Dict[str, Any]):
        """Callback function for database change stream events"""
        try:
            # Serialize the change event to make it JSON compatible
            serialized_change = {}
            
            # Handle the change event structure
            if 'operationType' in change_event:
                serialized_change['operationType'] = change_event['operationType']
            
            if 'documentKey' in change_event:
                # Convert ObjectId to string
                if '_id' in change_event['documentKey']:
                    serialized_change['documentKey'] = {
                        '_id': str(change_event['documentKey']['_id'])
                    }
            
            if 'fullDocument' in change_event:
                # Serialize the full document
                from websocket_manager import serialize_datetime
                serialized_change['fullDocument'] = serialize_datetime(change_event['fullDocument'])
            
            if 'updateDescription' in change_event:
                serialized_change['updateDescription'] = change_event['updateDescription']
            
            # Add timestamp
            serialized_change['timestamp'] = datetime.utcnow().isoformat()
            
            # Broadcast the serialized change to all connected applications
            await websocket_manager.broadcast_to_applications({
                "type": "alert_update",
                "change": serialized_change,
                "timestamp": serialized_change['timestamp']
            })
        except Exception as e:
            logger.error(f"Error in change stream callback: {e}")
    
    # Start change stream in background task
    if db_manager.is_connected:
        import asyncio
        asyncio.create_task(db_manager.start_change_stream(change_stream_callback))
        logger.info("Change stream started in background")
    
    logger.info("System started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Drone Alert Management System...")
    await db_manager.disconnect()
    logger.info("System shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Drone Alert Management System",
    description="Real-time drone alert management with WebSocket communication and MongoDB Change Streams",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory if it doesn't exist
os.makedirs(Config.UPLOAD_DIR, exist_ok=True)

# Mount static files for uploaded images
app.mount("/uploads", StaticFiles(directory=Config.UPLOAD_DIR), name="uploads")

@app.get("/dashboard/")
async def dashboard():
    """Serve the dashboard"""
    from fastapi.responses import FileResponse
    return FileResponse("dashboard/index.html")

# Mount dashboard static files
app.mount("/dashboard", StaticFiles(directory="dashboard"), name="dashboard")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Drone Alert Management System",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "dashboard": "/dashboard/",
            "api_docs": "/docs",
            "health": "/health",
            "alerts": "/api/alerts",
            "stats": "/api/stats"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database_connected": db_manager.is_connected,
        "websocket_stats": websocket_manager.get_connection_stats()
    }

@app.websocket("/ws/drone/{drone_id}")
async def websocket_drone_endpoint(websocket: WebSocket, drone_id: str):
    """WebSocket endpoint for drone connections"""
    client_id = None
    try:
        # Connect the drone
        client_id = await websocket_manager.connect(websocket, "drone", drone_id)
        
        if not client_id:
            return
        
        logger.info(f"Drone {drone_id} connected via WebSocket")
        
        # Handle incoming messages
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Handle the message
                await websocket_manager.handle_websocket_message(client_id, message_data)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received from drone {drone_id}")
                continue
            except Exception as e:
                logger.error(f"Error handling message from drone {drone_id}: {e}")
                continue
                
    except WebSocketDisconnect:
        logger.info(f"Drone {drone_id} disconnected")
    except Exception as e:
        logger.error(f"Error in drone WebSocket connection: {e}")
    finally:
        if client_id:
            await websocket_manager.disconnect(client_id)

@app.websocket("/ws/application/{app_id}")
async def websocket_application_endpoint(websocket: WebSocket, app_id: str):
    """WebSocket endpoint for application connections"""
    client_id = None
    try:
        # Connect the application
        client_id = await websocket_manager.connect(websocket, "application", app_id)
        
        if not client_id:
            return
        
        logger.info(f"Application {app_id} connected via WebSocket")
        
        # Send current alerts to the new application
        try:
            alerts = await db_manager.get_all_alerts(limit=50)
            if alerts:
                # Ensure alerts are properly serialized
                from websocket_manager import serialize_datetime
                serialized_alerts = serialize_datetime(alerts)
                
                initial_data_message = {
                    "type": "initial_alerts",
                    "alerts": serialized_alerts,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket_manager.send_personal_message(client_id, initial_data_message)
        except Exception as e:
            logger.error(f"Error sending initial alerts to application {app_id}: {e}")
        
        # Handle incoming messages
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Handle the message
                await websocket_manager.handle_websocket_message(client_id, message_data)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received from application {app_id}")
                continue
            except Exception as e:
                logger.error(f"Error handling message from application {app_id}: {e}")
                continue
                
    except WebSocketDisconnect:
        logger.info(f"Application {app_id} disconnected")
    except Exception as e:
        logger.error(f"Error in application WebSocket connection: {e}")
    finally:
        if client_id:
            await websocket_manager.disconnect(client_id)

# REST API endpoints for additional functionality
@app.get("/api/alerts")
async def get_alerts(limit: int = 100):
    """Get all alerts via REST API"""
    try:
        alerts = await db_manager.get_all_alerts(limit=limit)
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/alerts/{alert_id}")
async def get_alert(alert_id: str):
    """Get a specific alert by ID"""
    try:
        alert = await db_manager.get_alert(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return alert
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/alerts")
async def create_alert(alert: AlertCreate):
    """Create a new alert via REST API"""
    try:
        alert_data = alert.dict()
        alert_id = await db_manager.insert_alert(alert_data)
        return {"alert_id": alert_id, "message": "Alert created successfully"}
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/api/alerts/{alert_id}/response")
async def update_alert_response(alert_id: str, response: AlertResponse):
    """Update alert response via REST API"""
    try:
        update_data = {
            'rl_responsed': response.rl_responsed,
            'status': 'responded'
        }
        
        success = await db_manager.update_alert(alert_id, update_data)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"message": "Alert response updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert response: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/api/alerts/{alert_id}/image")
async def update_alert_image(alert_id: str, image_update: AlertImageUpdate):
    """Update alert image via REST API"""
    try:
        update_data = {
            'image_received': image_update.image_received,
            'image': image_update.image,
            'status': 'completed'
        }
        
        success = await db_manager.update_alert(alert_id, update_data)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"message": "Alert image updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert image: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/debug/env")
async def debug_environment():
    """Debug endpoint to show environment variables (for troubleshooting)"""
    import os
    return {
        "MONGODB_URI_set": bool(os.getenv('MONGODB_URI')),
        "DATABASE_NAME_set": bool(os.getenv('DATABASE_NAME')),
        "HOST_set": bool(os.getenv('HOST')),
        "PORT_set": bool(os.getenv('PORT')),
        "ENVIRONMENT_set": bool(os.getenv('ENVIRONMENT')),
        "DEBUG_set": bool(os.getenv('DEBUG')),
        "database_connected": db_manager.is_connected,
        "mongodb_uri_length": len(os.getenv('MONGODB_URI', '')) if os.getenv('MONGODB_URI') else 0,
        "database_name": os.getenv('DATABASE_NAME', 'NOT_SET'),
        "host": os.getenv('HOST', 'NOT_SET'),
        "port": os.getenv('PORT', 'NOT_SET')
    }

# Alert Image Endpoints
@app.post("/api/alert-images")
async def create_alert_image(alert_image: AlertImageCreate):
    """Create a new alert image via REST API"""
    try:
        alert_image_data = alert_image.dict()
        alert_image_id = await db_manager.create_alert_image(alert_image_data)
        return {"alert_image_id": alert_image_id, "message": "Alert image created successfully"}
    except Exception as e:
        logger.error(f"Error creating alert image: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/alert-images/{alert_image_id}")
async def get_alert_image(alert_image_id: str):
    """Get a specific alert image by ID via REST API"""
    try:
        alert_image = await db_manager.get_alert_image(alert_image_id)
        if not alert_image:
            raise HTTPException(status_code=404, detail="Alert image not found")
        return alert_image
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alert image {alert_image_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/alert-images/{alert_image_id}")
async def delete_alert_image(alert_image_id: str):
    """Delete an alert image by ID via REST API"""
    try:
        success = await db_manager.delete_alert_image(alert_image_id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert image not found")
        return {"message": "Alert image deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert image {alert_image_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Client Registry Management Endpoints
@app.get("/api/clients")
async def get_all_clients():
    """Get all registered clients"""
    try:
        clients = {}
        for client_id, client_info in client_registry.clients.items():
            clients[client_id] = {
                "client_id": client_info.client_id,
                "client_type": client_info.client_type,
                "name": client_info.name,
                "description": client_info.description,
                "capabilities": client_info.capabilities,
                "location": client_info.location,
                "status": client_info.status,
                "first_connected": client_info.first_connected,
                "last_connected": client_info.last_connected,
                "total_connections": client_info.total_connections,
                "is_authorized": client_info.is_authorized,
                "metadata": client_info.metadata
            }
        return {"clients": clients, "count": len(clients)}
    except Exception as e:
        logger.error(f"Error getting clients: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/clients/{client_id}")
async def get_client_info(client_id: str):
    """Get information about a specific client"""
    try:
        client_info = client_registry.get_client(client_id)
        if not client_info:
            raise HTTPException(status_code=404, detail="Client not found")
        
        return {
            "client_id": client_info.client_id,
            "client_type": client_info.client_type,
            "name": client_info.name,
            "description": client_info.description,
            "capabilities": client_info.capabilities,
            "location": client_info.location,
            "status": client_info.status,
            "first_connected": client_info.first_connected,
            "last_connected": client_info.last_connected,
            "total_connections": client_info.total_connections,
            "is_authorized": client_info.is_authorized,
            "metadata": client_info.metadata
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting client {client_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/clients/type/{client_type}")
async def get_clients_by_type(client_type: str):
    """Get all clients of a specific type (drone or application)"""
    try:
        if client_type not in ["drone", "application"]:
            raise HTTPException(status_code=400, detail="Invalid client type. Must be 'drone' or 'application'")
        
        clients = client_registry.get_clients_by_type(client_type)
        client_data = []
        
        for client_info in clients:
            client_data.append({
                "client_id": client_info.client_id,
                "client_type": client_info.client_type,
                "name": client_info.name,
                "description": client_info.description,
                "capabilities": client_info.capabilities,
                "location": client_info.location,
                "status": client_info.status,
                "first_connected": client_info.first_connected,
                "last_connected": client_info.last_connected,
                "total_connections": client_info.total_connections,
                "is_authorized": client_info.is_authorized,
                "metadata": client_info.metadata
            })
        
        return {"clients": client_data, "count": len(client_data), "client_type": client_type}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting clients by type {client_type}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/clients/online")
async def get_online_clients():
    """Get all currently online clients"""
    try:
        online_clients = client_registry.get_online_clients()
        client_data = {}
        
        for client_id, client_info in online_clients.items():
            client_data[client_id] = {
                "client_id": client_info.client_id,
                "client_type": client_info.client_type,
                "name": client_info.name,
                "description": client_info.description,
                "capabilities": client_info.capabilities,
                "location": client_info.location,
                "status": client_info.status,
                "first_connected": client_info.first_connected,
                "last_connected": client_info.last_connected,
                "total_connections": client_info.total_connections,
                "is_authorized": client_info.is_authorized,
                "metadata": client_info.metadata
            }
        
        return {"clients": client_data, "count": len(client_data)}
    except Exception as e:
        logger.error(f"Error getting online clients: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/api/clients/{client_id}/authorize")
async def authorize_client(client_id: str, authorized: bool = True):
    """Authorize or deauthorize a client"""
    try:
        client_info = client_registry.get_client(client_id)
        if not client_info:
            raise HTTPException(status_code=404, detail="Client not found")
        
        client_registry.authorize_client(client_id, authorized)
        status = "authorized" if authorized else "deauthorized"
        return {"message": f"Client {client_id} has been {status}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error authorizing client {client_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/clients/{client_id}")
async def remove_client(client_id: str):
    """Remove a client from the registry"""
    try:
        if client_registry.remove_client(client_id):
            return {"message": f"Client {client_id} has been removed from registry"}
        else:
            raise HTTPException(status_code=404, detail="Client not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing client {client_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True,
        log_level="info"
    ) 