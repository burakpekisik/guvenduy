import tensorflow as tf
import logging
import os

from app.config import MODEL_OPTIMIZATION

logger = logging.getLogger("sound-api")

# Configure TensorFlow on import
def configure_tensorflow():
    try:
        # Ensure GPU is visible
        physical_devices = tf.config.list_physical_devices('GPU')
        if physical_devices:
            logger.info(f"GPU detected: {len(physical_devices)} GPU(s) available")
            for i, device in enumerate(physical_devices):
                logger.info(f"GPU {i}: {device}")
            
            # Enable memory growth for GPUs to avoid allocating all memory at once
            if MODEL_OPTIMIZATION.get("enable_gpu_memory_growth", True):
                for gpu in physical_devices:
                    try:
                        tf.config.experimental.set_memory_growth(gpu, True)
                        logger.info(f"GPU memory growth enabled for GPU: {gpu}")
                    except RuntimeError as e:
                        logger.error(f"Error setting memory growth: {e}")
            
            # Optionally limit GPU memory
            if MODEL_OPTIMIZATION.get("gpu_memory_limit_mb"):
                try:
                    limit_mb = MODEL_OPTIMIZATION.get("gpu_memory_limit_mb")
                    tf.config.set_logical_device_configuration(
                        physical_devices[0],
                        [tf.config.LogicalDeviceConfiguration(memory_limit=limit_mb)]
                    )
                    logger.info(f"GPU memory limited to {limit_mb}MB")
                except Exception as e:
                    logger.warning(f"Could not set memory limit: {e}")
            
            # Enable mixed precision for faster training
            if MODEL_OPTIMIZATION.get("mixed_precision", True):
                try:
                    policy = tf.keras.mixed_precision.Policy('mixed_float16')
                    tf.keras.mixed_precision.set_global_policy(policy)
                    logger.info("Mixed precision policy set to mixed_float16")
                except Exception as e:
                    logger.warning(f"Could not set mixed precision: {e}")
            
            # Enable XLA JIT compilation
            if MODEL_OPTIMIZATION.get("xla_acceleration", True):
                try:
                    tf.config.optimizer.set_jit(True)
                    logger.info("XLA JIT compilation enabled")
                except Exception as e:
                    logger.warning(f"Could not enable XLA acceleration: {e}")
            
            # Force TensorFlow to use cuDNN for improved performance
            os.environ['TF_USE_CUDNN'] = '1'
            os.environ['TF_CUDNN_DETERMINISTIC'] = '0'  # For better performance
            
            # Reduce memory fragmentation
            os.environ['TF_GPU_ALLOCATOR'] = 'cuda_malloc_async'
        else:
            logger.warning("No GPUs detected, running on CPU only")
            
        # Disable eager execution for graph optimization (optional)
        # tf.compat.v1.disable_eager_execution()
    
        # Set TF log level
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=info, 2=warning, 3=error
        
        logger.info("TensorFlow optimizations configured successfully")
        return True
    except Exception as e:
        logger.error(f"Error configuring TensorFlow: {e}")
        return False

# Automatically configure when module is imported
configure_tensorflow()
