import uvicorn
import os
import tensorflow as tf
import logging
import argparse
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("sound-api-runner")

# Use a temp file to communicate debug mode to child processes when reload=True
DEBUG_FLAG_FILE = os.path.join(os.path.dirname(__file__), ".debug_mode")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Sound Classification API Server")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode (keep uploaded sound files)")
    args = parser.parse_args()
    
    # Save debug flag to file for child processes when using reload=True
    if args.debug:
        with open(DEBUG_FLAG_FILE, 'w') as f:
            f.write("1")
        logger.info(f"Debug flag saved to {DEBUG_FLAG_FILE}")
    else:
        # Remove debug flag file if it exists
        if os.path.exists(DEBUG_FLAG_FILE):
            os.remove(DEBUG_FLAG_FILE)
    
    # Import and set config settings
    from app.config import DEBUG_MODE
    import app.config as config
    
    # Set debug mode from command line argument
    config.DEBUG_MODE = args.debug
    if args.debug:
        logger.info("Debug mode enabled - uploaded sound files will be preserved")
    
    # Import TF configuration from app
    from app import configure_tensorflow
    
    # Set TF log level to reduce noise
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=info, 2=warning, 3=error
    
    logger.info("Starting Sound Classification API...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
