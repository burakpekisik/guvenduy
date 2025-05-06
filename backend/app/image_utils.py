import numpy as np
import logging
from PIL import Image
import tensorflow as tf

logger = logging.getLogger("sound-api")

def ensure_rgb(image_array):
    """
    Ensure an image array is RGB (3 channels)
    
    Args:
        image_array: Numpy array of image data
        
    Returns:
        RGB image array
    """
    # Check if array has 4 channels (RGBA)
    if len(image_array.shape) == 3 and image_array.shape[-1] == 4:
        logger.info("Converting RGBA image to RGB")
        return image_array[..., :3]  # Remove alpha channel
    
    # Check if grayscale (1 channel)
    elif len(image_array.shape) == 2 or (len(image_array.shape) == 3 and image_array.shape[-1] == 1):
        logger.info("Converting grayscale image to RGB")
        # Convert to 3-channel by duplicating the single channel
        if len(image_array.shape) == 2:
            image_array = np.expand_dims(image_array, axis=-1)
        return np.repeat(image_array, 3, axis=-1)
    
    return image_array

def resize_image(image_array, target_size=(224, 224)):
    """
    Resize an image array to the target size
    
    Args:
        image_array: Numpy array of image data
        target_size: Tuple (height, width)
        
    Returns:
        Resized image array
    """
    # Convert to PIL Image
    img = Image.fromarray(image_array.astype('uint8'))
    
    # Resize
    img = img.resize(target_size, Image.LANCZOS)
    
    # Convert back to numpy array
    return np.array(img)

def preprocess_for_mobilenet(image_array):
    """
    Preprocess an image for MobileNetV2 input
    
    Args:
        image_array: RGB image as numpy array
        
    Returns:
        Preprocessed image ready for MobileNetV2
    """
    # Ensure image is RGB
    image_array = ensure_rgb(image_array)
    
    # Add batch dimension if not present
    if len(image_array.shape) == 3:
        image_array = np.expand_dims(image_array, axis=0)
    
    # Use MobileNetV2's preprocessing function
    return tf.keras.applications.mobilenet_v2.preprocess_input(image_array)
