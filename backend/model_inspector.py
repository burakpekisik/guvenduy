import os
import json
import tensorflow as tf
import argparse
from app.config import MODEL_PATH

def inspect_model(model_path):
    """
    Inspect a saved model and print its metadata
    """
    print(f"Loading model from {model_path}...")
    
    try:
        model = tf.keras.models.load_model(model_path)
        
        print("\nModel Summary:")
        model.summary()
        
        print("\nInput Shape:", model.input_shape)
        print("Output Shape:", model.output_shape)
        
        print("\nLayer Details:")
        for i, layer in enumerate(model.layers):
            print(f"Layer {i}: {layer.name} ({layer.__class__.__name__})")
            print(f"  Input Shape: {layer.input_shape}")
            print(f"  Output Shape: {layer.output_shape}")
        
        # Get the expected input shape for MFCC features
        input_shape = model.input_shape
        if isinstance(input_shape, list):
            input_shape = input_shape[0]
        
        # The shape will be (None, height, width, channels)
        if len(input_shape) == 4:
            print(f"\nExpected MFCC Shape for API: ({input_shape[1]}, {input_shape[2]}, {input_shape[3]})")
            print(f"Set this value in app/config.py as MODEL_SHAPE.")
        
        print("\nInspection complete.")
        return True
        
    except Exception as e:
        print(f"Error inspecting model: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect TensorFlow model")
    parser.add_argument("--model", default=MODEL_PATH, help="Path to the saved model file")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.model):
        print(f"Error: Model file not found at {args.model}")
    else:
        inspect_model(args.model)
