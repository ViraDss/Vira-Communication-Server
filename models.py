from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from enum import Enum

class AlertStatus(str, Enum):
    PENDING = "pending"
    RESPONDED = "responded"
    COMPLETED = "completed"

class Alert(BaseModel):
    alert: str = Field(..., description="Alert description (e.g., 'Casualty - Person Detected')")
    drone_id: str = Field(..., description="ID of the drone that sent the alert")
    alert_location: Tuple[float, float, float] = Field(..., description="Alert location coordinates (x, y, z)")
    image: Optional[str] = Field(None, description="Image data or reference")
    image_received: int = Field(default=0, description="Image received status (0=no image, 1=received)")
    rl_responsed: int = Field(default=0, description="RL response status (0=no response, 1=responded)")
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    timestamp: str = Field(..., description="Alert timestamp in ISO format")

class AlertCreate(BaseModel):
    alert: str
    drone_id: str
    alert_location: Tuple[float, float, float]
    image: Optional[str] = None
    image_received: int = 0
    rl_responsed: int = 0
    score: float
    timestamp: str

class AlertResponse(BaseModel):
    alert_id: str
    rl_responsed: int = 1

class AlertImageUpdate(BaseModel):
    alert_id: str
    image: str
    image_received: int = 1

class AlertImage(BaseModel):
    found: int = Field(..., description="Detection status (1=found, 0=not found)")
    name: str = Field(..., description="Name or identifier of the detected object")
    drone_id: str = Field(default="No Drone", description="ID of the drone that captured the image")
    actual_image: str = Field(..., description="Base64 encoded actual image blob")
    matched_frame: str = Field(..., description="Base64 encoded matched frame blob")
    location: List[float] = Field(default=[0, 0, 0], description="Location coordinates [x, y, z]")
    timestamp: str = Field(..., description="Capture timestamp in ISO format")

class AlertImageCreate(BaseModel):
    found: int
    name: str
    drone_id: str = "No Drone"
    actual_image: str
    matched_frame: str
    location: List[float] = [0, 0, 0]
    timestamp: str

# New models for data processing flow
class ProcessingTask(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    app_id: str = Field(..., description="ID of the application that created the task")
    drone_id: str = Field(..., description="ID of the drone to process the task")
    task_type: str = Field(..., description="Type of processing task (e.g., 'image_analysis', 'object_detection')")
    input_data: Dict[str, Any] = Field(..., description="Input data for processing")
    status: str = Field(default="pending", description="Task status: pending, processing, completed, failed")
    priority: int = Field(default=1, description="Task priority (1=low, 5=high)")
    created_at: str = Field(..., description="Task creation timestamp")
    updated_at: Optional[str] = Field(None, description="Task last update timestamp")

class ProcessingTaskCreate(BaseModel):
    app_id: str
    drone_id: str
    task_type: str
    input_data: Dict[str, Any]
    priority: int = 1

class ProcessingResult(BaseModel):
    task_id: str = Field(..., description="Task identifier")
    drone_id: str = Field(..., description="ID of the drone that processed the task")
    result_data: Dict[str, Any] = Field(..., description="Processed result data")
    processing_time: float = Field(..., description="Processing time in seconds")
    success: bool = Field(..., description="Whether processing was successful")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    timestamp: str = Field(..., description="Result timestamp")

class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]
    client_type: str  # "drone" or "application"

class DroneCommand(BaseModel):
    alert_id: str
    command: str
    parameters: Optional[Dict[str, Any]] = None

class ConnectionInfo(BaseModel):
    client_id: str
    client_type: str
    connected_at: datetime 