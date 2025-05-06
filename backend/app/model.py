import numpy as np
import librosa
import librosa.display
import tensorflow as tf
from tensorflow import keras
import logging
from typing import Dict, Tuple
import os
import threading
import time
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image

from app.config import MODEL_PATH, MODEL_SHAPE, FEATURE_REDUCTION, BASE_DIR

logger = logging.getLogger("sound-api")

# Global variables for the model
model = None
base_model = None
labels = ['background', 'emergency_vehicle', 'horn', 'alarm_clock', 'baby', 'cat', 'dog', 'fire_alarm', 'thunder', 'car_crash', 'explosion', 'gun']
actual_model_shape = None
model_ready = False

def get_model_input_shape():
    """Get the actual input shape from the loaded model - needed for compatibility"""
    global model, base_model, actual_model_shape
    
    if model is None:
        load_model()
    
    if actual_model_shape is None:
        # For our spectrogram-based model, this is the input to MobileNetV2
        actual_model_shape = (224, 224, 3)
        logger.info(f"Using spectrogram input shape: {actual_model_shape}")
    
    return actual_model_shape

def create_spectrogram_from_audio(audio_file):
    """Create a spectrogram image from an audio file"""
    logger.info(f"Creating spectrogram from audio file: {audio_file}")
    
    # Create figure with no margins
    fig = plt.figure(figsize=(3, 3))
    ax = fig.add_subplot(1, 1, 1)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    
    # Load audio
    y, sr = librosa.load(audio_file)
    
    # Generate mel spectrogram
    ms = librosa.feature.melspectrogram(y=y, sr=sr)
    log_ms = librosa.power_to_db(ms, ref=np.max)
    
    # Display spectrogram
    librosa.display.specshow(log_ms, sr=sr)
    
    # Save figure to in-memory file
    buf = BytesIO()
    # Set format to PNG, transparent=False to avoid alpha channel
    fig.savefig(buf, format='png', transparent=False)
    buf.seek(0)
    plt.close(fig)
    
    # Load as PIL Image and resize to 224x224
    img = Image.open(buf)
    
    # Convert to RGB if the image has an alpha channel (RGBA)
    if img.mode == 'RGBA':
        logger.info("Converting RGBA image to RGB")
        img = img.convert('RGB')
    
    img = img.resize((224, 224))
    
    # Convert to numpy array
    img_array = np.array(img)
    
    # Check image shape and ensure it's RGB
    logger.info(f"Image shape before processing: {img_array.shape}")
    if img_array.shape[-1] == 4:  # If still RGBA for some reason
        logger.info("Removing alpha channel from image")
        img_array = img_array[..., :3]  # Drop alpha channel
    
    # Add batch dimension
    img_array = np.expand_dims(img_array, axis=0)
    
    logger.info(f"Spectrogram created with final shape: {img_array.shape}")
    return img_array

def preprocess_input(x):
    """Preprocess input images for MobileNetV2"""
    # Ensure we're using the correct preprocessing function for MobileNetV2
    logger.info(f"Preprocessing input with shape: {x.shape}")
    return tf.keras.applications.mobilenet_v2.preprocess_input(x)

def load_model():
    """Load the sound classification model and MobileNetV2 for feature extraction"""
    global model, base_model, model_ready, actual_model_shape
    
    try:
        logger.info(f"Loading model from {MODEL_PATH}")
        
        # Load MobileNetV2 for feature extraction (same as in notebook)
        logger.info("Loading MobileNetV2 base model for feature extraction")
        base_model = tf.keras.applications.MobileNetV2(
            weights='imagenet', 
            include_top=False, 
            input_shape=(224, 224, 3),
            alpha=0.75  # Same alpha value as used in the notebook
        )
        
        # Load the classifier model
        try:
            model = keras.models.load_model(MODEL_PATH)
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            
            # If loading fails, recreate the model architecture from the notebook
            logger.info("Recreating model architecture from notebook specifications")
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import Dense, Flatten, Dropout, BatchNormalization
            from tensorflow.keras.regularizers import l2
            
            model = Sequential()
            model.add(Flatten(input_shape=(7, 7, 1280)))  # MobileNetV2 feature output shape
            
            # Use the same architecture as in the notebook
            model.add(Dense(512, activation='relu', kernel_regularizer=l2(0.001)))
            model.add(BatchNormalization())
            model.add(Dropout(0.5))
            
            model.add(Dense(256, activation='relu', kernel_regularizer=l2(0.001)))
            model.add(BatchNormalization())
            model.add(Dropout(0.5))
            
            model.add(Dense(12, activation='softmax'))  # 12 classes as in the notebook
            
            # Compile the model
            model.compile(
                optimizer='adam',
                loss='categorical_crossentropy',
                metrics=['accuracy']
            )
            
            # Try to load the weights
            try:
                model.load_weights(MODEL_PATH)
                logger.info("Successfully loaded weights")
            except Exception as weight_error:
                logger.error(f"Error loading weights: {str(weight_error)}")
                logger.warning("Using randomly initialized weights - predictions may not be accurate!")
        
        # Set the actual model shape for the API
        actual_model_shape = (224, 224, 3)  # Input shape for spectrograms
        
        # Run a warm-up inference to initialize the model
        warm_up_model()
        
        model_ready = True
        logger.info("Model is now ready for predictions")
        return model
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        model_ready = False
        raise Exception(f"Failed to load model: {str(e)}")

def warm_up_model():
    """Run a warm-up inference to initialize TF graphs and optimize performance"""
    global model, base_model
    
    try:
        logger.info("Running warm-up inference to prepare model...")
        
        # Create a dummy input with the right shape for MobileNetV2
        dummy_input = np.zeros((1, 224, 224, 3), dtype=np.float32)
        dummy_input = preprocess_input(dummy_input)
        
        # Extract features using MobileNetV2
        features = base_model.predict(dummy_input)
        
        # Run prediction on features
        start_time = time.time()
        _ = model.predict(features)
        elapsed = time.time() - start_time
        
        logger.info(f"Warm-up inference completed in {elapsed:.4f} seconds")
        
        # Run a second time to measure optimized speed
        start_time = time.time()
        features = base_model.predict(dummy_input)
        _ = model.predict(features)
        elapsed = time.time() - start_time
        
        logger.info(f"Optimized inference time: {elapsed:.4f} seconds")
        
    except Exception as e:
        logger.warning(f"Warm-up inference failed: {str(e)}")

def is_model_ready():
    """Check if model is loaded and ready for inference"""
    global model_ready
    return model_ready

def get_predictions(audio_file: str) -> Dict[str, float]:
    """
    Process audio file and return predictions for all classes
    """
    global model, base_model, labels
    
    if model is None or base_model is None:
        load_model()
    
    try:
        logger.info(f"Processing audio file: {audio_file}")
        
        # Create spectrogram from audio file
        img = create_spectrogram_from_audio(audio_file)
        
        # Ensure image is in the right format
        if img.shape[-1] == 4:  # RGBA format
            logger.info("Converting RGBA to RGB")
            img = img[..., :3]  # Drop alpha channel
        
        # Preprocess for MobileNetV2
        img_processed = preprocess_input(img)
        
        # Extract features using MobileNetV2 base model
        features = base_model.predict(img_processed)
        
        # Make prediction using classifier
        predictions = model.predict(features)[0]
        
        # Create dictionary of class predictions
        result = {}
        for i, label in enumerate(labels):
            result[label] = float(predictions[i])
        
        # Log the top prediction
        top_label = labels[np.argmax(predictions)]
        top_score = float(np.max(predictions))
        logger.info(f"Top prediction: {top_label} with score {top_score:.4f}")
        
        return result
        
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        raise Exception(f"Prediction error: {str(e)}")
