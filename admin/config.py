import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# API Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")

# App Configuration
APP_TITLE = "Sound Classification Admin Panel"
APP_ICON = "🔊"

# Authentication
TOKEN_EXPIRY_MINUTES = 60

# Performance Settings
# Bu ayarlar streamlit'in .streamlit/config.toml dosyasına da eklenebilir
STREAMLIT_SERVER_MAX_UPLOAD_SIZE = 200
STREAMLIT_BROWSER_GATHER_USAGE_STATS = False
STREAMLIT_SERVER_ENABLE_STATIC_SERVING = True
STREAMLIT_CACHE_RESOURCE_CLEAR_ON_EXCEPTION = False