from fastapi import APIRouter, HTTPException, File, Form, UploadFile, BackgroundTasks, Request, Depends, status
from sqlalchemy.orm import Session
import os
import uuid
import logging
import json
from typing import Dict, List, Optional

from app.models.training import TrainingRequest, TrainingResponse
from app.config import BASE_DIR, ALLOWED_EXTENSIONS, UPLOAD_DIR
from app.utils import save_upload_file
from app.training import SoundClassificationTrainer
from app.database import get_db_session, get_db, User
from app.auth import check_admin_privilege

router = APIRouter(
    prefix="/training",
    tags=["model-training"]
)

logger = logging.getLogger("sound-api")

# Training background tasks store
training_tasks = {}

@router.post("/", response_model=TrainingResponse)
async def train_model(
    background_tasks: BackgroundTasks,
    request: Request,
    class_names: str = Form(...),
    output_model_name: Optional[str] = Form(None),
    epochs: Optional[int] = Form(100),
    batch_size: Optional[int] = Form(8),
    files: List[UploadFile] = File(...),
    labels: str = Form(...),
    current_user: User = Depends(check_admin_privilege),
    db: Session = Depends(get_db_session)
):
    """
    Train a new sound classification model with provided audio files (Admin only)
    
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

@router.get("/{task_id}", response_model=TrainingResponse)
async def get_training_status(
    task_id: str,
    current_user: User = Depends(check_admin_privilege)
):
    """
    Get the status of a training task (Admin only)
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