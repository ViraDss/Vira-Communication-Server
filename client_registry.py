#!/usr/bin/env python3
"""
Client Registry System
Tracks all drones and applications that connect to the server
Provides automatic registration and manual management capabilities
"""

import json
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class ClientInfo:
    """Information about a connected client"""
    client_id: str
    client_type: str  # "drone" or "application"
    name: Optional[str] = None
    description: Optional[str] = None
    capabilities: List[str] = None
    location: Optional[Dict[str, float]] = None
    status: str = "offline"  # "online", "offline", "maintenance"
    first_connected: str = ""
    last_connected: str = ""
    total_connections: int = 0
    is_authorized: bool = True
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.metadata is None:
            self.metadata = {}

class ClientRegistry:
    """Manages registration and tracking of drones and applications"""
    
    def __init__(self, registry_file: str = "client_registry.json"):
        self.registry_file = registry_file
        self.clients: Dict[str, ClientInfo] = {}
        self.online_clients: Dict[str, ClientInfo] = {}
        
        # Load existing registry
        self.load_registry()
        
    def load_registry(self):
        """Load client registry from file"""
        try:
            if os.path.exists(self.registry_file):
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for client_id, client_data in data.items():
                    self.clients[client_id] = ClientInfo(**client_data)
                    
                logger.info(f"Loaded {len(self.clients)} clients from registry")
            else:
                logger.info("No existing registry file found, starting fresh")
                
        except Exception as e:
            logger.error(f"Error loading client registry: {e}")
            self.clients = {}
    
    def save_registry(self):
        """Save client registry to file"""
        try:
            # Convert ClientInfo objects to dictionaries
            registry_data = {}
            for client_id, client_info in self.clients.items():
                registry_data[client_id] = asdict(client_info)
            
            # Write to file with backup
            backup_file = f"{self.registry_file}.backup"
            if os.path.exists(self.registry_file):
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                os.rename(self.registry_file, backup_file)
            
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(registry_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Saved {len(self.clients)} clients to registry")
            
        except Exception as e:
            logger.error(f"Error saving client registry: {e}")
    
    def register_client(self, client_id: str, client_type: str, **kwargs) -> ClientInfo:
        """Register a new client or update existing one"""
        current_time = datetime.utcnow().isoformat()
        
        if client_id in self.clients:
            # Update existing client
            client_info = self.clients[client_id]
            client_info.last_connected = current_time
            client_info.total_connections += 1
            client_info.status = "online"
            
            # Update any provided fields
            for key, value in kwargs.items():
                if hasattr(client_info, key):
                    setattr(client_info, key, value)
                    
            logger.info(f"Updated existing {client_type} client: {client_id}")
        else:
            # Create new client
            client_info = ClientInfo(
                client_id=client_id,
                client_type=client_type,
                first_connected=current_time,
                last_connected=current_time,
                total_connections=1,
                status="online",
                **kwargs
            )
            
            # Set default name if not provided
            if not client_info.name:
                client_info.name = f"{client_type.title()} {client_id}"
            
            # Set default capabilities based on type
            if not client_info.capabilities:
                if client_type == "drone":
                    client_info.capabilities = ["alerts", "imaging", "navigation"]
                elif client_type == "application":
                    client_info.capabilities = ["monitoring", "analysis", "response"]
            
            self.clients[client_id] = client_info
            logger.info(f"Registered new {client_type} client: {client_id}")
        
        # Add to online clients
        self.online_clients[client_id] = client_info
        
        # Save registry
        self.save_registry()
        
        return client_info
    
    def unregister_client(self, client_id: str):
        """Mark client as offline"""
        if client_id in self.clients:
            self.clients[client_id].status = "offline"
            self.clients[client_id].last_connected = datetime.utcnow().isoformat()
            
        if client_id in self.online_clients:
            del self.online_clients[client_id]
            
        self.save_registry()
        logger.info(f"Client marked as offline: {client_id}")
    
    def get_client(self, client_id: str) -> Optional[ClientInfo]:
        """Get client information"""
        return self.clients.get(client_id)
    
    def get_clients_by_type(self, client_type: str) -> List[ClientInfo]:
        """Get all clients of a specific type"""
        return [client for client in self.clients.values() if client.client_type == client_type]
    
    def get_online_clients(self) -> Dict[str, ClientInfo]:
        """Get all currently online clients"""
        return self.online_clients.copy()
    
    def get_online_clients_by_type(self, client_type: str) -> List[ClientInfo]:
        """Get online clients of a specific type"""
        return [client for client in self.online_clients.values() if client.client_type == client_type]
    
    def update_client(self, client_id: str, **updates) -> bool:
        """Update client information"""
        if client_id not in self.clients:
            return False
        
        client_info = self.clients[client_id]
        for key, value in updates.items():
            if hasattr(client_info, key):
                setattr(client_info, key, value)
        
        self.save_registry()
        return True
    
    def authorize_client(self, client_id: str, authorized: bool = True):
        """Authorize or deauthorize a client"""
        if client_id in self.clients:
            self.clients[client_id].is_authorized = authorized
            self.save_registry()
            logger.info(f"Client {client_id} {'authorized' if authorized else 'deauthorized'}")
    
    def remove_client(self, client_id: str) -> bool:
        """Completely remove a client from registry"""
        removed = False
        if client_id in self.clients:
            del self.clients[client_id]
            removed = True
        
        if client_id in self.online_clients:
            del self.online_clients[client_id]
        
        if removed:
            self.save_registry()
            logger.info(f"Client removed from registry: {client_id}")
        
        return removed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        drones = self.get_clients_by_type("drone")
        applications = self.get_clients_by_type("application")
        
        online_drones = self.get_online_clients_by_type("drone")
        online_applications = self.get_online_clients_by_type("application")
        
        return {
            "total_clients": len(self.clients),
            "total_drones": len(drones),
            "total_applications": len(applications),
            "online_clients": len(self.online_clients),
            "online_drones": len(online_drones),
            "online_applications": len(online_applications),
            "authorized_clients": len([c for c in self.clients.values() if c.is_authorized]),
            "registry_file": self.registry_file,
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def export_clients(self, file_path: str = None) -> str:
        """Export client data to a formatted JSON file"""
        if not file_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"clients_export_{timestamp}.json"
        
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "stats": self.get_stats(),
            "clients": {}
        }
        
        for client_id, client_info in self.clients.items():
            export_data["clients"][client_id] = asdict(client_info)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(self.clients)} clients to {file_path}")
        return file_path
    
    def import_clients(self, file_path: str) -> int:
        """Import clients from a JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            imported_count = 0
            clients_data = data.get("clients", {})
            
            for client_id, client_data in clients_data.items():
                self.clients[client_id] = ClientInfo(**client_data)
                imported_count += 1
            
            self.save_registry()
            logger.info(f"Imported {imported_count} clients from {file_path}")
            return imported_count
            
        except Exception as e:
            logger.error(f"Error importing clients: {e}")
            return 0

# Global registry instance
client_registry = ClientRegistry()

# Utility functions for easy access
def register_client(client_id: str, client_type: str, **kwargs) -> ClientInfo:
    """Register a client with the global registry"""
    return client_registry.register_client(client_id, client_type, **kwargs)

def unregister_client(client_id: str):
    """Unregister a client from the global registry"""
    client_registry.unregister_client(client_id)

def get_client_info(client_id: str) -> Optional[ClientInfo]:
    """Get client information from the global registry"""
    return client_registry.get_client(client_id)

def get_registry_stats() -> Dict[str, Any]:
    """Get statistics from the global registry"""
    return client_registry.get_stats()

def is_client_authorized(client_id: str) -> bool:
    """Check if a client is authorized"""
    client_info = client_registry.get_client(client_id)
    return client_info.is_authorized if client_info else True  # Allow new clients by default
