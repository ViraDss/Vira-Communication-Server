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

    #Fireabase Credentials
    FIREBASE_API = os.getenv("FIREBASE_API", "AIzaSyDJ1jNTRR7DsC4EeMlVYdp9GNdG-iZEfnk")
    FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN","vira-dd365.firebaseapp.com")
    FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL","https://vira-dd365-default-rtdb.firebaseio.com")
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID","vira-dd365")
    FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET","vira-dd365.appspot.com")
    FIREBASE_MESSAGING_SENDER_ID = os.getenv("FIREBASE_MESSAGING_SENDER_ID","1084416444892")
    FIREBASE_APP_ID = os.getenv("FIREBASE_APP_ID","1:1084416444892:web:9c8b0e7a3c5f1e4d9b8c9")
    
