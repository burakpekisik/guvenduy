import os
import logging

# Paths and directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "audio_classifier_03052025.h5")
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")

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

# Setup directories
def setup_dirs():
    """Create necessary directories"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logging.info(f"Upload directory created at {UPLOAD_DIR}")
    
    # Log debug mode status
    logger = logging.getLogger("sound-api")
    if DEBUG_MODE:
        logger.info(f"Debug mode enabled (detected from flag file) - uploaded sound files will be preserved")
