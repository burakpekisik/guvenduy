import os
import shutil
from fastapi import UploadFile
import logging
import tensorflow as tf
import json
import glob
from datetime import datetime
import time

logger = logging.getLogger("sound-api")

async def save_upload_file(upload_file: UploadFile, destination: str) -> None:
    """
    Save an upload file to the specified destination
    """
    try:
        with open(destination, "wb") as buffer:
            # Read file in chunks to handle large files efficiently
            chunk_size = 1024 * 1024  # 1MB chunks
            while chunk := await upload_file.read(chunk_size):
                buffer.write(chunk)
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise e

def cleanup_file(file_path: str) -> None:
    """
    Remove a temporary file unless debug mode is enabled.
    In non-debug mode, manage files to keep the last MAX_AUDIO_FILES.
    """
    from app.config import DEBUG_MODE, UPLOAD_DIR, MAX_AUDIO_FILES
    
    try:
        if os.path.exists(file_path):
            if DEBUG_MODE:
                logger.info(f"Debug mode enabled - keeping file: {file_path}")
            else:
                # Instead of removing, manage the file collection
                manage_audio_files(file_path)
                logger.info(f"Successfully managed audio file: {file_path}")
    except Exception as e:
        logger.error(f"Error handling file {file_path}: {str(e)}")

def manage_audio_files(new_file_path: str) -> None:
    """
    Manage audio files collection to keep only the last MAX_AUDIO_FILES.
    When the limit is reached, remove the oldest files first.
    """
    from app.config import UPLOAD_DIR, MAX_AUDIO_FILES
    
    try:
        audio_files = glob.glob(os.path.join(UPLOAD_DIR, "*.wav"))
        
        # Count current files (excluding the new file if it's already in the list)
        current_count = len(audio_files)
        
        if current_count >= MAX_AUDIO_FILES:
            # Sort files by creation time (oldest first)
            audio_files.sort(key=lambda x: os.path.getctime(x))
            
            # Calculate how many files to delete
            files_to_delete = current_count - MAX_AUDIO_FILES + 1  # +1 for the new file
            
            # Delete oldest files
            for i in range(files_to_delete):
                if i < len(audio_files):
                    try:
                        os.remove(audio_files[i])
                        logger.info(f"Removed oldest audio file: {audio_files[i]}")
                    except Exception as e:
                        logger.error(f"Failed to remove old file {audio_files[i]}: {str(e)}")
    except Exception as e:
        logger.error(f"Error managing audio files: {str(e)}")

def move_to_evaluated(file_path: str, recording_name: str) -> str:
    """
    Move an audio file to the evaluated files directory
    Returns the new file path
    """
    from app.config import EVALUATED_FILES_DIR
    
    try:
        if not os.path.exists(file_path):
            logger.warning(f"Attempted to move non-existent file to evaluated directory: {file_path}")
            return None
        
        # Create a timestamped filename to avoid collisions
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        _, ext = os.path.splitext(file_path)
        
        # Create a new filename combining the recording name and timestamp
        safe_name = "".join(c for c in recording_name if c.isalnum() or c in "._- ")
        new_filename = f"{safe_name}_{timestamp}{ext}"
        
        # Full path to the new file location
        new_file_path = os.path.join(EVALUATED_FILES_DIR, new_filename)
        
        # Move the file
        shutil.copy2(file_path, new_file_path)
        logger.info(f"Moved evaluated file from {file_path} to {new_file_path}")
        
        return new_file_path
    except Exception as e:
        logger.error(f"Error moving file to evaluated directory: {str(e)}")
        return None

def find_audio_file_by_name(recording_name: str) -> str:
    """
    Find an audio file in the uploads directory by its recording name
    Returns the file path if found, None otherwise
    """
    from app.config import UPLOAD_DIR
    
    try:
        # Get all audio files in the uploads directory
        audio_files = glob.glob(os.path.join(UPLOAD_DIR, "*.wav"))
        
        # Try to find a filename that contains the recording name
        safe_name = "".join(c for c in recording_name if c.isalnum() or c in "._- ")
        
        for file_path in audio_files:
            if safe_name in os.path.basename(file_path):
                return file_path
        
        # If not found by name, return the most recently created file
        # (This is a fallback assuming the evaluation is for the most recent upload)
        if audio_files:
            most_recent = max(audio_files, key=os.path.getctime)
            logger.info(f"Could not find file by name '{recording_name}', using most recent: {most_recent}")
            return most_recent
        
        return None
    except Exception as e:
        logger.error(f"Error finding audio file by name: {str(e)}")
        return None

def inspect_model(model_path):
    """
    Inspect a saved model and return its metadata
    """
    try:
        model = tf.keras.models.load_model(model_path)
        
        # Get model information
        model_info = {
            "input_shape": str(model.input_shape),
            "output_shape": str(model.output_shape),
            "layers": []
        }
        
        # Get layer information
        for layer in model.layers:
            layer_info = {
                "name": layer.name,
                "type": layer.__class__.__name__,
                "input_shape": str(layer.input_shape),
                "output_shape": str(layer.output_shape)
            }
            model_info["layers"].append(layer_info)
        
        return model_info
    except Exception as e:
        logger.error(f"Error inspecting model: {str(e)}")
        return {"error": str(e)}
