from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import threading

from app.config import setup_dirs
from app.model import load_model
from app.database import init_database
from app.routers import general_router, auth_router, audio_router, training_router, alerts_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("sound-api")

# Define lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code (runs before app starts)
    logger.info("Starting up the API...")
    setup_dirs()
    
    # Initialize database
    logger.info("Initializing database...")
    database_initialized = init_database()
    if database_initialized:
        logger.info("Database initialized successfully")
    else:
        logger.warning("Database initialization failed, evaluation features may not work")
    
    # Start model loading in a background thread
    # This allows the API to start serving requests while the model loads
    global model_loading_task
    model_loading_task = threading.Thread(target=load_model_task)
    model_loading_task.daemon = True
    model_loading_task.start()
    
    logger.info("API startup complete - model loading in background")
    
    yield  # This is where FastAPI serves requests
    
    # Shutdown code (runs when app is shutting down)
    logger.info("Shutting down the API...")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Sound Classification API",
    description="API for classifying emergency vehicle sounds and horn sounds",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
model_loading_lock = threading.Lock()
model_loading_task = None

# Background task for model loading
def load_model_task():
    """Background task to load the model"""
    with model_loading_lock:
        try:
            logger.info("Starting background model loading")
            load_model()
            logger.info("Background model loading completed")
        except Exception as e:
            logger.error(f"Background model loading failed: {str(e)}")

# Include all routers
app.include_router(general_router)
app.include_router(auth_router)
app.include_router(audio_router)
app.include_router(training_router)
app.include_router(alerts_router)

# If this module is run directly, start the FastAPI app with Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
