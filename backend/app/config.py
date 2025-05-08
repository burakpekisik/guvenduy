import os
import logging
import secrets

# Paths and directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "audio_classifier_03052025.h5")
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")
EVALUATED_FILES_DIR = os.path.join(BASE_DIR, "evaluated_uploads")

# File management settings
MAX_AUDIO_FILES = 100  # Maximum number of audio files to keep in the uploads directory

# Debug mode flag check - first check for flag file (created by run.py)
DEBUG_FLAG_FILE = os.path.join(BASE_DIR, ".debug_mode")
DEBUG_MODE = os.path.exists(DEBUG_FLAG_FILE)

# Model parameters
FEATURE_REDUCTION = True
MODEL_SHAPE = (224, 224, 3)  # Input for spectrograms, not raw MFCCs

# Performance optimization settings
MODEL_OPTIMIZATION = {
    "preload_at_startup": True,     # Preload model at application startup
    "enable_gpu_memory_growth": True,  # Allow TF to grow GPU memory as needed
    "mixed_precision": True,        # Use mixed precision for faster computation
    "xla_acceleration": False,      # Disable XLA acceleration to avoid TF version compatibility issues
    "gpu_memory_limit_mb": None     # Limit GPU memory usage (None = no limit)
}

# API settings
ALLOWED_EXTENSIONS = (".wav",)

# Database settings
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "guvenduy")

# SQLAlchemy database URL
DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

# Authentication settings
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))  # Generate random key if not provided
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# User privilege levels
class UserPrivilege:
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

# Setup directories
def setup_dirs():
    """Create necessary directories"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logging.info(f"Upload directory created at {UPLOAD_DIR}")
    
    # Create directory for evaluated files
    os.makedirs(EVALUATED_FILES_DIR, exist_ok=True)
    logging.info(f"Evaluated files directory created at {EVALUATED_FILES_DIR}")
    
    # Log debug mode status
    logger = logging.getLogger("sound-api")
    if DEBUG_MODE:
        logger.info(f"Debug mode enabled (detected from flag file) - uploaded sound files will be preserved")
