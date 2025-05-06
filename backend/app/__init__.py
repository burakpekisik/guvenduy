# Package initialization file

import tensorflow as tf
import logging
from app.config import MODEL_OPTIMIZATION
from app.configure_tensorflow import configure_tensorflow

# Configure TensorFlow optimizations
logger = logging.getLogger("sound-api")

# This ensures TensorFlow is configured when the app is imported
configure_tensorflow()
