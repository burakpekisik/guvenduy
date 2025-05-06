import os
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import librosa
import librosa.display
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from io import BytesIO
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.layers import Dropout, BatchNormalization, Dense, Flatten
from tensorflow.keras.regularizers import l2
from tensorflow.keras.models import Sequential
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

from app.config import BASE_DIR

# Configure logging
logger = logging.getLogger("sound-api")

class SoundClassificationTrainer:
    """
    Class to handle the training of sound classification models,
    based on the CNN approach used in the notebook.
    """
    
    def __init__(self, classes, temp_dir=None, model_output_path=None):
        """
        Initialize the trainer with class names
        
        Args:
            classes: List of class names
            temp_dir: Directory to store temporary files (spectrograms)
            model_output_path: Path to save the trained model
        """
        self.classes = classes
        self.num_classes = len(classes)
        self.temp_dir = temp_dir or os.path.join(BASE_DIR, "temp_train")
        self.model_output_path = model_output_path or os.path.join(BASE_DIR, f"sound_classifier_{self.num_classes}cls.h5")
        
        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Training dataset
        self.x_train = []
        self.y_train = []
        self.x_test = []
        self.y_test = []
        
        # Models
        self.base_model = None
        self.model = None
        self.train_features = None
        self.test_features = None
        
    def split_audio_file(self, audio_file, max_duration=5.0):
        """Split an audio file into chunks of max_duration seconds"""
        try:
            y, sr = librosa.load(audio_file)
            duration = librosa.get_duration(y=y, sr=sr)
            
            # If duration is less than or equal to max_duration, return as is
            if duration <= max_duration:
                return [(y, sr)]
                
            chunks = []
            samples_per_chunk = int(max_duration * sr)
            
            # Split the audio into chunks
            for i in range(0, len(y), samples_per_chunk):
                chunk = y[i:i + samples_per_chunk]
                # Only keep the chunk if it's the full length (discard shorter ones)
                if len(chunk) == samples_per_chunk:
                    chunks.append((chunk, sr))
                    
            return chunks
        except Exception as e:
            logger.error(f"Error splitting audio file {audio_file}: {e}")
            return []
    
    def create_spectrogram(self, audio_data, sr):
        """Create a spectrogram from audio data"""
        try:
            # Create a figure with a specific figure size
            plt.switch_backend('agg')
            fig = plt.figure(figsize=(4, 4))
            ax = fig.add_subplot(1, 1, 1)
            fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
            
            # Remove axis
            ax.set_axis_off()
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            
            # Generate mel spectrogram
            ms = librosa.feature.melspectrogram(y=audio_data, sr=sr)
            log_ms = librosa.power_to_db(ms, ref=np.max)
            
            # Display spectrogram
            librosa.display.specshow(log_ms, sr=sr, ax=ax, x_axis=None, y_axis=None)
            
            # Save figure to in-memory file
            buf = BytesIO()
            fig.savefig(buf, dpi=150, format='png', bbox_inches='tight', pad_inches=0, transparent=False)
            plt.close(fig)
            buf.seek(0)
            
            # Convert to PIL Image and resize to 224x224
            img = Image.open(buf)
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            img = img.resize((224, 224))
            
            # Convert to numpy array
            img_array = np.array(img)
            
            return img_array
        except Exception as e:
            logger.error(f"Error creating spectrogram: {e}")
            return None
    
    def process_audio_file(self, audio_file, label):
        """
        Process an audio file to create spectrograms, returns images and labels
        
        Args:
            audio_file: Path to the audio file
            label: Class label (integer)
            
        Returns:
            List of (image, label) pairs
        """
        try:
            chunks = self.split_audio_file(audio_file)
            results = []
            
            for chunk_y, chunk_sr in chunks:
                img_array = self.create_spectrogram(chunk_y, chunk_sr)
                if img_array is not None:
                    results.append((img_array, label))
                    
            return results
        except Exception as e:
            logger.error(f"Error processing audio file {audio_file}: {e}")
            return []
    
    def process_audio_files(self, audio_files, labels, max_workers=4):
        """
        Process multiple audio files in parallel
        
        Args:
            audio_files: List of audio file paths
            labels: List of labels corresponding to each file
            max_workers: Number of parallel workers
            
        Returns:
            List of processed images and labels
        """
        all_images = []
        all_labels = []
        
        if not audio_files:
            logger.warning("No audio files provided for processing")
            return all_images, all_labels
        
        logger.info(f"Processing {len(audio_files)} audio files...")
        
        try:
            # Process files in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit processing tasks
                future_to_file = {
                    executor.submit(self.process_audio_file, file, label): (file, label)
                    for file, label in zip(audio_files, labels)
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_file):
                    file, label = future_to_file[future]
                    try:
                        results = future.result()
                        for img, lbl in results:
                            all_images.append(img)
                            all_labels.append(lbl)
                    except Exception as e:
                        logger.error(f"Error processing {file}: {e}")
            
            logger.info(f"Created {len(all_images)} spectrograms from {len(audio_files)} audio files")
        except Exception as e:
            logger.error(f"Error in parallel processing: {e}")
        
        return all_images, all_labels
    
    def prepare_training_data(self, audio_files, labels):
        """
        Prepare training data from audio files
        
        Args:
            audio_files: List of audio file paths
            labels: List of labels for each file (integer indices)
            
        Returns:
            Success status (boolean)
        """
        try:
            # Process all audio files to get spectrograms
            images, labels = self.process_audio_files(audio_files, labels)
            
            if not images:
                logger.error("No valid spectrograms generated from audio files")
                return False
            
            # Split into training and test sets
            self.x_train, self.x_test, self.y_train, self.y_test = train_test_split(
                images, labels, stratify=labels, test_size=0.3, random_state=42
            )
            
            # Normalize pixel values
            self.x_train = np.array(self.x_train)
            self.x_test = np.array(self.x_test)
            
            # Convert labels to one-hot encoding
            self.y_train = to_categorical(self.y_train, num_classes=self.num_classes)
            self.y_test = to_categorical(self.y_test, num_classes=self.num_classes)
            
            logger.info(f"Training data prepared: {len(self.x_train)} training samples, {len(self.x_test)} test samples")
            return True
        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return False
    
    def extract_features(self, batch_size=8):
        """
        Extract features using MobileNetV2
        
        Args:
            batch_size: Batch size for feature extraction
            
        Returns:
            Success status (boolean)
        """
        try:
            # Load base model for feature extraction
            logger.info("Loading MobileNetV2 for feature extraction...")
            self.base_model = MobileNetV2(
                weights='imagenet', 
                include_top=False, 
                input_shape=(224, 224, 3),
                alpha=0.75
            )
            
            # Preprocess input data
            x_train_processed = preprocess_input(self.x_train)
            x_test_processed = preprocess_input(self.x_test)
            
            # Extract features in batches to avoid memory issues
            logger.info(f"Extracting features for {len(x_train_processed)} training samples...")
            self.train_features = np.zeros((len(x_train_processed), 7, 7, 1280))
            for i in range(0, len(x_train_processed), batch_size):
                end = min(i + batch_size, len(x_train_processed))
                batch = x_train_processed[i:end]
                self.train_features[i:end] = self.base_model.predict(batch, batch_size=batch_size)
                if (i + batch_size) % 100 == 0 or end == len(x_train_processed):
                    logger.info(f"Processed {end}/{len(x_train_processed)} - {end/len(x_train_processed)*100:.1f}%")
            
            logger.info(f"Extracting features for {len(x_test_processed)} test samples...")
            self.test_features = np.zeros((len(x_test_processed), 7, 7, 1280))
            for i in range(0, len(x_test_processed), batch_size):
                end = min(i + batch_size, len(x_test_processed))
                batch = x_test_processed[i:end]
                self.test_features[i:end] = self.base_model.predict(batch, batch_size=batch_size)
                if (i + batch_size) % 100 == 0 or end == len(x_test_processed):
                    logger.info(f"Processed {end}/{len(x_test_processed)} - {end/len(x_test_processed)*100:.1f}%")
            
            # Clear memory
            tf.keras.backend.clear_session()
            
            logger.info("Feature extraction completed")
            return True
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return False
    
    def build_model(self):
        """
        Build classification model
        
        Returns:
            The compiled model
        """
        try:
            logger.info("Building classifier model...")
            
            # Create sequential model
            self.model = Sequential()
            self.model.add(Flatten(input_shape=self.train_features.shape[1:]))
            
            # Add layers with dropout and batch normalization
            self.model.add(Dense(512, activation='relu', kernel_regularizer=l2(0.001)))
            self.model.add(BatchNormalization())
            self.model.add(Dropout(0.5))
            
            self.model.add(Dense(256, activation='relu', kernel_regularizer=l2(0.001)))
            self.model.add(BatchNormalization())
            self.model.add(Dropout(0.5))
            
            self.model.add(Dense(self.num_classes, activation='softmax'))
            
            # Compile model
            self.model.compile(
                optimizer='adam',
                loss='categorical_crossentropy',
                metrics=['accuracy']
            )
            
            logger.info("Model built successfully")
            return self.model
        except Exception as e:
            logger.error(f"Error building model: {e}")
            return None
    
    def train_model(self, epochs=150, batch_size=8):
        """
        Train the model
        
        Args:
            epochs: Maximum number of epochs
            batch_size: Batch size for training
            
        Returns:
            Training history
        """
        try:
            if self.model is None:
                self.build_model()
                
            logger.info(f"Training model with {len(self.train_features)} samples...")
            
            # Callbacks for training
            early_stopping = EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True
            )
            
            reduce_lr = ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.2,
                patience=5,
                min_lr=0.00001
            )
            
            # Train the model
            history = self.model.fit(
                self.train_features, self.y_train,
                validation_data=(self.test_features, self.y_test),
                batch_size=batch_size,
                epochs=epochs,
                callbacks=[early_stopping, reduce_lr],
                verbose=1
            )
            
            # Save the model
            self.model.save(self.model_output_path)
            logger.info(f"Model saved to {self.model_output_path}")
            
            # Evaluate the model
            evaluation = self.model.evaluate(self.test_features, self.y_test)
            logger.info(f"Test loss: {evaluation[0]}, Test accuracy: {evaluation[1]}")
            
            return history
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return None
    
    def generate_training_report(self, history):
        """
        Generate a training report with metrics and plots
        
        Args:
            history: Training history from model.fit()
            
        Returns:
            Dictionary with report data
        """
        try:
            if history is None:
                return {"error": "No training history provided"}
            
            # Get accuracy and loss values
            train_acc = history.history['accuracy']
            val_acc = history.history['val_accuracy']
            train_loss = history.history['loss']
            val_loss = history.history['val_loss']
            
            # Final metrics
            final_epoch = len(train_acc)
            final_train_acc = train_acc[-1]
            final_val_acc = val_acc[-1]
            
            # Test accuracy from evaluation
            test_loss, test_acc = self.model.evaluate(self.test_features, self.y_test, verbose=0)
            
            # Get confusion matrix data
            y_pred = self.model.predict(self.test_features)
            y_pred_classes = np.argmax(y_pred, axis=1)
            y_true_classes = np.argmax(self.y_test, axis=1)
            
            # Create report
            report = {
                "classes": self.classes,
                "num_training_samples": len(self.x_train),
                "num_test_samples": len(self.x_test),
                "num_epochs": final_epoch,
                "training_accuracy": float(final_train_acc),
                "validation_accuracy": float(final_val_acc),
                "test_accuracy": float(test_acc),
                "model_path": self.model_output_path
            }
            
            logger.info(f"Training report generated with test accuracy: {test_acc:.4f}")
            return report
        except Exception as e:
            logger.error(f"Error generating training report: {e}")
            return {"error": str(e)}