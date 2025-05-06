import tensorflow as tf
import numpy as np
import logging
import os

from app.config import MODEL_PATH, MODEL_SHAPE

logger = logging.getLogger("sound-api")

def inspect_model_layers(model_path=MODEL_PATH):
    """
    Inspect each layer of the model and print detailed information
    """
    try:
        logger.info(f"Inspecting model at {model_path}")
        model = tf.keras.models.load_model(model_path)
        
        logger.info("Model summary:")
        model.summary(print_fn=logger.info)
        
        logger.info("\nDetailed layer information:")
        for i, layer in enumerate(model.layers):
            logger.info(f"Layer {i}: {layer.name} ({layer.__class__.__name__})")
            logger.info(f"  Input shape: {layer.input_shape}")
            logger.info(f"  Output shape: {layer.output_shape}")
            
            # For flatten layers, calculate the expected number of input elements
            if isinstance(layer, tf.keras.layers.Flatten):
                if i > 0:  # Make sure there's a previous layer
                    prev_layer = model.layers[i-1]
                    input_shape = prev_layer.output_shape
                    if input_shape and len(input_shape) > 1:
                        # Calculate total elements based on output shape of previous layer
                        total_elements = np.prod(input_shape[1:])  # Skip batch dimension
                        logger.info(f"  Expected input elements for flatten: {total_elements}")
        
        # Check if MODEL_SHAPE in config matches the model's input shape
        input_shape = model.input_shape
        if isinstance(input_shape, list):
            input_shape = input_shape[0]
        
        # This model takes features from MobileNetV2, not direct spectrograms
        logger.info(f"Note: This model expects features from MobileNetV2, not raw spectrograms")
        logger.info(f"Input shape for features: {model.input_shape}")
        logger.info(f"Raw spectrogram shape needed: (224, 224, 3)")
            
        return True
        
    except Exception as e:
        logger.error(f"Error inspecting model: {str(e)}")
        return False

def test_spectrogram_model(model_path=MODEL_PATH):
    """
    Test the model with a properly preprocessed spectrogram to verify compatibility
    """
    try:
        # Load the classifier model
        model = tf.keras.models.load_model(model_path)
        
        # Create MobileNetV2 for feature extraction
        base_model = tf.keras.applications.MobileNetV2(
            weights='imagenet', 
            include_top=False, 
            input_shape=(224, 224, 3)
        )
        
        # Create a dummy spectrogram tensor
        dummy_img = np.zeros((1, 224, 224, 3), dtype=np.float32)
        
        # Preprocess 
        dummy_img_processed = tf.keras.applications.mobilenet.preprocess_input(dummy_img)
        
        # Extract features
        features = base_model.predict(dummy_img_processed)
        
        # Try prediction
        logger.info(f"Testing classifier with features shape: {features.shape}")
        prediction = model.predict(features)
        
        logger.info(f"Prediction shape: {prediction.shape}")
        logger.info(f"Test successful - model accepts features from MobileNetV2")
        return True
        
    except Exception as e:
        logger.error(f"Test failed - model compatibility issue: {str(e)}")
        return False
