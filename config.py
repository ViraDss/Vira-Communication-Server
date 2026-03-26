import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # MongoDB Configuration
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://aamp898989:dronesurvillance@cluster0.cftmhkh.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "drone_alerts_db")
    ALERTS_COLLECTION = "alerts"
    ALERT_IMAGES_COLLECTION = "alertImage"
    
    # Server Configuration
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    
    # Production settings
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    
    # WebSocket Configuration
    WS_PING_INTERVAL = 20
    WS_PING_TIMEOUT = 20
    
    # File Upload Configuration
    UPLOAD_DIR = "uploads"
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30 