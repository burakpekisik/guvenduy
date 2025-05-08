from fastapi import APIRouter, HTTPException, Depends
import logging
from app.model import is_model_ready, load_model, get_model_input_shape
from app.utils import inspect_model
from app.config import MODEL_PATH, DEBUG_MODE, UPLOAD_DIR

router = APIRouter(tags=["general"])

logger = logging.getLogger("sound-api")

@router.get("/")
async def root():
    return {"message": "Sound Classification API is running", "model_status": "ready" if is_model_ready() else "loading"}

@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "model_loaded": is_model_ready(),
    }

@router.get("/model-status")
async def model_status():
    """
    Check the current status of the model
    """
    return {
        "model_ready": is_model_ready(),
        "model_path": MODEL_PATH,
    }

@router.get("/model-info")
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

@router.get("/debug-status")
async def debug_status():
    """
    Get the current debug mode status
    """
    return {
        "debug_mode": DEBUG_MODE,
        "upload_dir": UPLOAD_DIR,
        "message": "Debug mode is enabled - uploaded files will be preserved" if DEBUG_MODE else "Debug mode is disabled - uploaded files will be deleted after processing"
    }