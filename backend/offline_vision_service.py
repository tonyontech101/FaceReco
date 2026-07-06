"""
Offline Vision Service Module
Handles local image feature extraction using MobileNetV2 pre-trained model.
No external API calls - fully offline operation.
"""

import base64
import time
from io import BytesIO
from typing import Optional

import numpy as np
from PIL import Image


# Global model cache - lazy loaded on first use
_model = None
_preprocess_input = None


def _load_model():
    """
    Lazy load MobileNetV2 model and cache in memory.
    Only loads once per application lifecycle.
    """
    global _model, _preprocess_input
    
    if _model is not None:
        return _model
    
    try:
        import tensorflow as tf
        from tensorflow.keras.applications import MobileNetV2
        from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
        
        print("[OfflineVision] Loading MobileNetV2 model...")
        start_time = time.time()
        
        # Load pre-trained MobileNetV2 without top classification layer
        # This gives us the 1280-dimensional feature vector from global average pooling
        _model = MobileNetV2(
            weights='imagenet',
            include_top=False,
            pooling='avg',  # Global average pooling - outputs 1280-dim vector
            input_shape=(224, 224, 3)
        )
        
        _preprocess_input = preprocess_input
        
        elapsed = time.time() - start_time
        print(f"[OfflineVision] Model loaded successfully in {elapsed:.2f}s")
        
        return _model
        
    except ImportError as e:
        raise Exception(
            f"TensorFlow not installed. Run: pip install tensorflow>=2.15.0\n"
            f"Error: {e}"
        )
    except Exception as e:
        raise Exception(f"Failed to load MobileNetV2 model: {e}")


def _preprocess_image(image: Image.Image) -> np.ndarray:
    """
    Preprocess image for MobileNetV2:
    - Resize to 224x224
    - Convert to RGB
    - Normalize pixel values
    
    Args:
        image: PIL Image object
        
    Returns:
        Preprocessed numpy array ready for model input
    """
    # Convert to RGB (handles RGBA, grayscale, etc.)
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Resize to 224x224 (MobileNetV2 input size)
    image = image.resize((224, 224), Image.Resampling.LANCZOS)
    
    # Convert to numpy array
    img_array = np.array(image, dtype=np.float32)
    
    # Add batch dimension: (224, 224, 3) -> (1, 224, 224, 3)
    img_array = np.expand_dims(img_array, axis=0)
    
    # Apply MobileNetV2 preprocessing (normalize to [-1, 1])
    img_array = _preprocess_input(img_array)
    
    return img_array


def extract_image_features(image_base64: str) -> np.ndarray:
    """
    Extract 1280-dimensional feature vector from image using MobileNetV2.
    
    Args:
        image_base64: Base64 encoded image data (with or without data URI prefix)
        
    Returns:
        Numpy array of shape (1280,) containing the feature vector
        
    Raises:
        ValueError: If image is invalid or cannot be processed
        Exception: If model loading or inference fails
    """
    # Load model (lazy loaded, cached after first call)
    model = _load_model()
    
    # Decode base64 image
    try:
        if image_base64.startswith("data:image/"):
            # Remove data URI prefix: "data:image/jpeg;base64,..."
            _, encoded = image_base64.split(",", 1)
        else:
            encoded = image_base64
        
        image_bytes = base64.b64decode(encoded, validate=True)
        
    except (ValueError, Exception) as e:
        raise ValueError(f"Invalid base64 image data: {e}")
    
    # Load and validate image
    try:
        image = Image.open(BytesIO(image_bytes))
        
        # Validate image format
        if image.format and image.format.upper() not in ['JPEG', 'PNG', 'WEBP', 'JPG']:
            raise ValueError(f"Unsupported image format: {image.format}. Use JPEG, PNG, or WebP.")
        
    except Exception as e:
        raise ValueError(f"Cannot open image: {e}")
    
    # Preprocess image
    try:
        preprocessed = _preprocess_image(image)
    except Exception as e:
        raise ValueError(f"Image preprocessing failed: {e}")
    
    # Extract features
    try:
        start_time = time.time()
        features = model.predict(preprocessed, verbose=0)
        elapsed = time.time() - start_time
        
        # features shape: (1, 1280) -> flatten to (1280,)
        feature_vector = features.flatten()
        
        print(f"[OfflineVision] Feature extraction completed in {elapsed*1000:.0f}ms "
              f"(vector dim: {feature_vector.shape[0]})")
        
        return feature_vector
        
    except Exception as e:
        raise Exception(f"Feature extraction failed: {e}")


def extract_image_features_from_file(file_path: str) -> np.ndarray:
    """
    Extract features from an image file on disk.
    Convenience wrapper around extract_image_features.
    
    Args:
        file_path: Path to image file
        
    Returns:
        Numpy array of shape (1280,) containing the feature vector
    """
    try:
        with open(file_path, 'rb') as f:
            image_bytes = f.read()
        
        # Convert to base64
        image_base64 = base64.b64encode(image_bytes).decode('ascii')
        
        return extract_image_features(image_base64)
        
    except FileNotFoundError:
        raise ValueError(f"Image file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Failed to extract features from file: {e}")


def compute_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Compute cosine similarity between two feature vectors.
    
    Args:
        vec1: First feature vector
        vec2: Second feature vector
        
    Returns:
        Similarity score between 0 and 1 (1 = identical, 0 = completely different)
    """
    # Normalize vectors
    vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-10)
    vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-10)
    
    # Compute cosine similarity
    similarity = np.dot(vec1_norm, vec2_norm)
    
    # Clamp to [0, 1] range (should already be in [-1, 1], but make it [0, 1])
    similarity = (similarity + 1) / 2
    
    return float(similarity)
