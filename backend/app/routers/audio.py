from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.models.sound import PredictionResponse, EvaluationRequest
from app.model import is_model_ready, get_predictions
from app.utils import save_upload_file, cleanup_file, find_audio_file_by_name, move_to_evaluated
from app.database import get_db_session, add_prediction, add_evaluation, get_evaluation_stats, get_latest_predictions, get_db, User
from app.config import ALLOWED_EXTENSIONS, UPLOAD_DIR
from app.auth import get_current_active_user, check_admin_privilege

router = APIRouter(
    prefix="/audio",
    tags=["sound-processing"]
)

logger = logging.getLogger("sound-api")

@router.post("/predict", response_model=PredictionResponse)
async def predict_sound(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session)
) -> Dict[str, Dict[str, float]]:
    """
    Process an uploaded .wav file and return classification predictions
    
    No authentication required for this endpoint.
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
        
        # Find the highest confidence class
        highest_class = max(predictions.items(), key=lambda x: x[1])
        highest_class_name = highest_class[0]
        highest_confidence = highest_class[1]
        
        # Save to database (without user_id as no authentication is required)
        add_prediction(
            db=db,
            user_id=None,
            file_name=file.filename,
            file_path=file_path,
            highest_class=highest_class_name,
            highest_confidence=highest_confidence,
            all_predictions=predictions
        )
        
        # Clean up the file
        cleanup_file(file_path)
        logger.info(f"File managed: {file_path}")
        
        return {"predictions": predictions}
    
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        if os.path.exists(file_path):
            cleanup_file(file_path)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.post("/evaluations")
async def submit_evaluation(
    evaluation: EvaluationRequest,
    db: Session = Depends(get_db_session)
):
    """
    Submit a user evaluation for a sound detection result
    
    This endpoint allows users to provide feedback on detection accuracy
    by marking predictions as successful or unsuccessful.
    No authentication required for this endpoint.
    """
    try:
        # Convert ISO date string to datetime object
        recording_date = datetime.fromisoformat(evaluation.recording_date)
        
        # Add the evaluation to the database without user_id
        eval_result = add_evaluation(
            db=db,
            user_id=None,
            device_id=evaluation.device_id,
            recording_date=recording_date,
            recording_name=evaluation.recording_name,
            detection_class=evaluation.detection_class,
            detection_confidence=evaluation.detection_confidence,
            success=evaluation.success
        )
        
        if not eval_result:
            raise HTTPException(
                status_code=500,
                detail="Failed to save evaluation to database"
            )
        
        # Only move files to the evaluated directory if the evaluation was successful
        file_preserved = False
        if evaluation.success:
            # Try to find and move the audio file to the evaluated files directory
            file_path = find_audio_file_by_name(evaluation.recording_name)
            
            if file_path:
                new_path = move_to_evaluated(file_path, evaluation.recording_name)
                logger.info(f"Successful evaluation audio file moved to: {new_path}")
                file_preserved = True
            
        return {
            "status": "success",
            "message": "Evaluation submitted successfully",
            "file_preserved": file_preserved
        }
        
    except Exception as e:
        logger.error(f"Error submitting evaluation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error submitting evaluation: {str(e)}"
        )

@router.get("/evaluations/stats")
async def get_evaluation_statistics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session)
):
    """
    Get statistics about user evaluations
    
    This endpoint provides aggregated statistics about user evaluations,
    such as total evaluations, success rates, and stats by sound class
    """
    try:
        stats = get_evaluation_stats(db)
        
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

@router.get("/predictions")
async def get_predictions_list(
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session)
):
    """
    Get a list of the latest predictions
    
    This endpoint returns the most recent predictions made by the model,
    up to the specified limit (default 100)
    """
    try:
        predictions = get_latest_predictions(db, limit=limit)
        
        if predictions is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve predictions from database"
            )
            
        return {
            "count": len(predictions),
            "predictions": predictions
        }
        
    except Exception as e:
        logger.error(f"Error retrieving predictions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving predictions: {str(e)}"
        )

@router.get("/file/{file_path:path}")
async def get_audio_file(
    file_path: str,
    current_user: User = Depends(check_admin_privilege)
):
    """
    Get audio file by path (admin only)
    
    This endpoint allows administrators to retrieve audio files for playback.
    """
    try:
        # Make sure the file path is within allowed directories
        full_path = os.path.abspath(file_path)
        if not (full_path.startswith(os.path.abspath(UPLOAD_DIR)) or 
                full_path.startswith(os.path.abspath("evaluated_uploads"))):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this file is forbidden"
            )
        
        if not os.path.exists(full_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
            
        return FileResponse(
            path=full_path, 
            media_type="audio/wav", 
            filename=os.path.basename(full_path)
        )
    except Exception as e:
        logger.error(f"Error retrieving audio file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving audio file: {str(e)}"
        )