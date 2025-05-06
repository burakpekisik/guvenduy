import os
import shutil
from fastapi import UploadFile
import logging
import tensorflow as tf
import json

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
    Remove a temporary file unless debug mode is enabled
    """
    from app.config import DEBUG_MODE
    
    try:
        if os.path.exists(file_path):
            if DEBUG_MODE:
                logger.info(f"Debug mode enabled - keeping file: {file_path}")
            else:
                os.remove(file_path)
                logger.info(f"Successfully removed temporary file: {file_path}")
    except Exception as e:
        logger.error(f"Error handling file {file_path}: {str(e)}")

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
