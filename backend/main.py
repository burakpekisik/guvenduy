from fastapi import FastAPI, UploadFile, HTTPException, File, BackgroundTasks, Form, UploadFile, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
import os
import uuid
import logging
import threading
import asyncio
import json
from pydantic import BaseModel
from datetime import datetime

from app.model import load_model, get_predictions, get_model_input_shape, is_model_ready
from app.utils import save_upload_file, cleanup_file, inspect_model
from app.config import MODEL_PATH, UPLOAD_DIR, ALLOWED_EXTENSIONS, setup_dirs, DEBUG_MODE, BASE_DIR
from app.training import SoundClassificationTrainer
from app.database import init_database, add_evaluation, get_evaluation_stats

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

# Model training request and response models
class TrainingRequest(BaseModel):
    """Request model for training a sound classification model"""
    class_names: List[str]
    output_model_name: Optional[str] = None
    epochs: Optional[int] = 100
    batch_size: Optional[int] = 8

class TrainingResponse(BaseModel):
    """Response model for training status and results"""
    status: str
    task_id: Optional[str] = None
    message: str
    details: Optional[Dict] = None

# Evaluation request model
class EvaluationRequest(BaseModel):
    """Request model for submitting a user evaluation"""
    device_id: str
    recording_date: str  # ISO format date-time string
    recording_name: str
    detection_class: str
    detection_confidence: float
    success: bool  # True for successful prediction, False for unsuccessful

# Training background tasks store
training_tasks = {}

@app.get("/")
async def root():
    return {"message": "Sound Classification API is running", "model_status": "ready" if is_model_ready() else "loading"}

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "model_loaded": is_model_ready(),
    }

@app.get("/model-status")
async def model_status():
    """
    Check the current status of the model
    """
    return {
        "model_ready": is_model_ready(),
        "model_path": MODEL_PATH,
    }

@app.get("/model-info")
async def model_info():
    """
    Get information about the loaded model
    """
    try:
        # Load model if not already loaded
        load_model()
        
        # Get model shape
        input_shape = get_model_input_shape()
        
        # Get detailed model info
        model_details = inspect_model(MODEL_PATH)
        
        return {
            "model_path": MODEL_PATH,
            "input_shape": input_shape,
            "details": model_details
        }
    except Exception as e:
        logger.error(f"Error getting model info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting model info: {str(e)}")

@app.post("/predict/")
async def predict_sound(file: UploadFile = File(...)) -> Dict[str, Dict[str, float]]:
    """
    Process an uploaded .wav file and return classification predictions
    """
    # Check if model is ready
    if not is_model_ready():
        raise HTTPException(
            status_code=503, 
            detail="The model is still loading. Please try again in a moment."
        )
    
    # Check file extension
    if not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400, 
            detail=f"File must be one of the following formats: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    try:
        # Generate a unique filename to avoid collisions
        temp_filename = f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
        file_path = os.path.join(UPLOAD_DIR, temp_filename)
        
        # Save uploaded file
        await save_upload_file(file, file_path)
        logger.info(f"File saved: {file_path}")
        
        # Get predictions
        predictions = get_predictions(file_path)
        logger.info(f"Predictions generated for {file.filename}")
        
        # Clean up the file
        cleanup_file(file_path)
        logger.info(f"File deleted: {file_path}")
        
        return {"predictions": predictions}
    
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        if os.path.exists(file_path):
            cleanup_file(file_path)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.get("/debug-status")
async def debug_status():
    """
    Get the current debug mode status
    """
    return {
        "debug_mode": DEBUG_MODE,
        "upload_dir": UPLOAD_DIR,
        "message": "Debug mode is enabled - uploaded files will be preserved" if DEBUG_MODE else "Debug mode is disabled - uploaded files will be deleted after processing"
    }

@app.post("/train/", response_model=TrainingResponse)
async def train_model(
    background_tasks: BackgroundTasks,
    request: Request,
    class_names: str = Form(...),
    output_model_name: Optional[str] = Form(None),
    epochs: Optional[int] = Form(100),
    batch_size: Optional[int] = Form(8),
    files: List[UploadFile] = File(...),
    labels: str = Form(...)
):
    """
    Train a new sound classification model with provided audio files
    
    - class_names: JSON string with list of class names
    - labels: JSON string with integer label for each file
    - files: List of audio files to train on
    - output_model_name: Optional name for the output model file
    - epochs: Number of training epochs
    - batch_size: Batch size for training
    """
    try:
        # Parse class names from JSON
        try:
            class_names_list = json.loads(class_names)
            if not isinstance(class_names_list, list) or not all(isinstance(name, str) for name in class_names_list):
                raise HTTPException(status_code=400, detail="class_names must be a JSON list of strings")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="class_names must be a valid JSON string")
        
        # Parse labels from JSON
        try:
            labels_list = json.loads(labels)
            if not isinstance(labels_list, list) or not all(isinstance(label, int) for label in labels_list):
                raise HTTPException(status_code=400, detail="labels must be a JSON list of integers")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="labels must be a valid JSON string")
        
        # Check if number of files matches number of labels
        if len(files) != len(labels_list):
            raise HTTPException(
                status_code=400, 
                detail=f"Number of files ({len(files)}) must match number of labels ({len(labels_list)})"
            )
        
        # Validate labels are within range
        if not all(0 <= label < len(class_names_list) for label in labels_list):
            raise HTTPException(
                status_code=400,
                detail=f"Labels must be integers between 0 and {len(class_names_list) - 1}"
            )
            
        # Check file types
        for file in files:
            if not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is not one of the allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
                )
        
        # Save files to temporary directory for processing
        saved_file_paths = []
        for file in files:
            # Generate a unique filename
            temp_filename = f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
            file_path = os.path.join(UPLOAD_DIR, temp_filename)
            
            # Save uploaded file
            await save_upload_file(file, file_path)
            saved_file_paths.append(file_path)
            
        logger.info(f"Saved {len(saved_file_paths)} files for training")
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Initialize task status
        training_tasks[task_id] = {
            "status": "initializing",
            "message": "Preparing model training",
            "details": {
                "num_files": len(saved_file_paths),
                "classes": class_names_list,
                "epochs": epochs,
                "batch_size": batch_size
            }
        }
        
        # Start training in background
        background_tasks.add_task(
            run_training_task,
            task_id,
            saved_file_paths,
            labels_list,
            class_names_list,
            output_model_name,
            epochs,
            batch_size
        )
        
        return {
            "status": "started",
            "task_id": task_id,
            "message": "Model training has been started in the background",
            "details": {
                "num_files": len(saved_file_paths),
                "classes": class_names_list
            }
        }
        
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        logger.error(f"Error starting training: {str(e)}")
        # Clean up any saved files on error
        for file_path in saved_file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error starting training: {str(e)}")

@app.get("/train/{task_id}", response_model=TrainingResponse)
async def get_training_status(task_id: str):
    """
    Get the status of a training task
    """
    if task_id not in training_tasks:
        raise HTTPException(status_code=404, detail=f"Training task {task_id} not found")
    
    task = training_tasks[task_id]
    return {
        "status": task["status"],
        "task_id": task_id,
        "message": task["message"],
        "details": task.get("details")
    }

async def run_training_task(task_id, audio_files, class_indices, class_names, output_model_name=None, epochs=100, batch_size=8):
    """Background task for model training"""
    try:
        logger.info(f"Starting training task {task_id} with {len(audio_files)} audio files for {len(class_names)} classes")
        training_tasks[task_id]["status"] = "processing"
        
        # Create the trainer with the provided class names
        model_path = output_model_name if output_model_name else f"sound_classifier_{uuid.uuid4()}.h5"
        model_path = os.path.join(BASE_DIR, model_path)
        trainer = SoundClassificationTrainer(class_names, model_output_path=model_path)
        
        # Prepare training data
        success = trainer.prepare_training_data(audio_files, class_indices)
        if not success:
            training_tasks[task_id]["status"] = "failed"
            training_tasks[task_id]["message"] = "Failed to prepare training data"
            return
        
        # Extract features using MobileNetV2
        success = trainer.extract_features(batch_size=batch_size)
        if not success:
            training_tasks[task_id]["status"] = "failed"
            training_tasks[task_id]["message"] = "Failed to extract features from spectrograms"
            return
        
        # Build and train the model
        trainer.build_model()
        history = trainer.train_model(epochs=epochs, batch_size=batch_size)
        
        if history is None:
            training_tasks[task_id]["status"] = "failed"
            training_tasks[task_id]["message"] = "Model training failed"
            return
        
        # Generate training report
        report = trainer.generate_training_report(history)
        
        # Update task status
        training_tasks[task_id]["status"] = "completed"
        training_tasks[task_id]["message"] = "Model training completed successfully"
        training_tasks[task_id]["details"] = report
        
        logger.info(f"Training task {task_id} completed successfully. Model saved to {model_path}")
        
    except Exception as e:
        logger.error(f"Error in training task {task_id}: {str(e)}")
        training_tasks[task_id]["status"] = "failed"
        training_tasks[task_id]["message"] = f"Training failed: {str(e)}"

@app.post("/evaluations/")
async def submit_evaluation(evaluation: EvaluationRequest):
    """
    Submit a user evaluation for a sound detection result
    
    This endpoint allows mobile app users to provide feedback on detection accuracy
    by marking predictions as successful or unsuccessful
    """
    try:
        # Convert ISO date string to datetime object
        recording_date = datetime.fromisoformat(evaluation.recording_date)
        
        # Add the evaluation to the database
        success = add_evaluation(
            device_id=evaluation.device_id,
            recording_date=recording_date,
            recording_name=evaluation.recording_name,
            detection_class=evaluation.detection_class,
            detection_confidence=evaluation.detection_confidence,
            success=evaluation.success
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to save evaluation to database"
            )
            
        return {
            "status": "success",
            "message": "Evaluation submitted successfully"
        }
        
    except Exception as e:
        logger.error(f"Error submitting evaluation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error submitting evaluation: {str(e)}"
        )

@app.get("/evaluations/stats")
async def get_evaluation_statistics():
    """
    Get statistics about user evaluations
    
    This endpoint provides aggregated statistics about user evaluations,
    such as total evaluations, success rates, and stats by sound class
    """
    try:
        stats = get_evaluation_stats()
        
        if stats is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve evaluation statistics"
            )
            
        return stats
        
    except Exception as e:
        logger.error(f"Error retrieving evaluation statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving evaluation statistics: {str(e)}"
        )
