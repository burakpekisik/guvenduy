import librosa
import numpy as np
import logging
import matplotlib
# Force matplotlib to use 'Agg' backend to avoid issues in server environments
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image

logger = logging.getLogger("sound-api")

def load_audio_file(file_path, duration=None, sr=None):
    """Load an audio file using librosa"""
    try:
        logger.info(f"Loading audio file: {file_path}")
        y, sr = librosa.load(file_path, duration=duration, sr=sr)
        return y, sr
    except Exception as e:
        logger.error(f"Error loading audio file: {str(e)}")
        raise e

def create_spectrogram(y, sr, return_pil=False):
    """Create a spectrogram from audio data"""
    try:
        # Create a figure with a specific figure size
        fig = plt.figure(figsize=(3, 3), dpi=100)
        ax = fig.add_subplot(1, 1, 1)
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        
        # Remove axis
        ax.axis('off')
        
        # Generate mel spectrogram
        ms = librosa.feature.melspectrogram(y=y, sr=sr)
        log_ms = librosa.power_to_db(ms, ref=np.max)
        
        # Display spectrogram
        librosa.display.specshow(log_ms, sr=sr, ax=ax)
        
        # Save figure to in-memory file
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', 
                    pad_inches=0, transparent=False)
        plt.close(fig)
        buf.seek(0)
        
        # Return as PIL Image or numpy array
        img = Image.open(buf)
        
        # Ensure the image is in RGB mode
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        if return_pil:
            return img
        else:
            img_array = np.array(img)
            return img_array
    except Exception as e:
        logger.error(f"Error creating spectrogram: {str(e)}")
        raise e

def extract_audio_features(file_path):
    """Extract audio features for machine learning"""
    try:
        y, sr = load_audio_file(file_path)
        
        # Extract common features
        features = {
            'duration': librosa.get_duration(y=y, sr=sr),
            'zero_crossing_rate': np.mean(librosa.feature.zero_crossing_rate(y)),
            'spectral_centroid': np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)),
            'spectral_bandwidth': np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)),
        }
        
        return features
    except Exception as e:
        logger.error(f"Error extracting audio features: {str(e)}")
        raise e
