"""
Quick verification script to test offline image recognition system.
Run this to verify all components are working correctly.
"""

import os
import sys

# Add backend to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

print("=" * 60)
print("Offline Image Recognition - System Verification")
print("=" * 60)

# Test 1: Check dependencies
print("\n[Test 1] Checking dependencies...")
try:
    import tensorflow as tf
    print(f"  ✓ TensorFlow: {tf.__version__}")
except ImportError as e:
    print(f"  ✗ TensorFlow not installed: {e}")
    sys.exit(1)

try:
    import sklearn
    print(f"  ✓ scikit-learn: {sklearn.__version__}")
except ImportError as e:
    print(f"  ✗ scikit-learn not installed: {e}")
    sys.exit(1)

try:
    import numpy as np
    print(f"  ✓ NumPy: {np.__version__}")
except ImportError as e:
    print(f"  ✗ NumPy not installed: {e}")
    sys.exit(1)

try:
    from PIL import Image
    print(f"  ✓ Pillow: {Image.__version__}")
except ImportError as e:
    print(f"  ✗ Pillow not installed: {e}")
    sys.exit(1)

# Test 2: Check offline_vision_service
print("\n[Test 2] Testing offline_vision_service...")
try:
    from offline_vision_service import extract_image_features_from_file
    print("  ✓ Module imported successfully")
except ImportError as e:
    print(f"  ✗ Failed to import: {e}")
    sys.exit(1)

# Test 3: Check image_storage
print("\n[Test 3] Testing image_storage...")
try:
    from image_storage import ExcelImageStore
    DATABASE_PATH = os.path.join(ROOT_DIR, "data", "image_database.xlsx")
    store = ExcelImageStore(DATABASE_PATH)
    store.ensure_workbook()
    print("  ✓ ExcelImageStore initialized")
except Exception as e:
    print(f"  ✗ Failed to initialize: {e}")
    sys.exit(1)

# Test 4: Check if images directory exists
print("\n[Test 4] Checking images directory...")
IMAGES_DIR = os.path.join(ROOT_DIR, "data", "images")
if os.path.exists(IMAGES_DIR):
    image_count = len([f for f in os.listdir(IMAGES_DIR) 
                       if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    print(f"  ✓ Images directory exists with {image_count} images")
else:
    print(f"  ✗ Images directory not found: {IMAGES_DIR}")
    sys.exit(1)

# Test 5: Check database state
print("\n[Test 5] Checking database state...")
try:
    stats = store.get_statistics()
    print(f"  Total images: {stats['total_images']}")
    print(f"  Unique objects: {stats['unique_objects']}")
    print(f"  Categories: {', '.join(stats['categories']) if stats['categories'] else 'None'}")
    
    if stats['total_images'] == 0:
        print("\n  ⚠️  Database is empty. Run: python populate_database.py")
    else:
        print("  ✓ Database populated")
except Exception as e:
    print(f"  ✗ Failed to get statistics: {e}")

# Test 6: Test feature extraction (if images exist)
print("\n[Test 6] Testing feature extraction...")
if image_count > 0:
    try:
        # Get first image
        test_image = None
        for f in os.listdir(IMAGES_DIR):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                test_image = f
                break
        
        if test_image:
            test_path = os.path.join(IMAGES_DIR, test_image)
            print(f"  Testing with: {test_image}")
            
            import time
            start = time.time()
            features = extract_image_features_from_file(test_path)
            elapsed = time.time() - start
            
            print(f"  ✓ Feature extraction successful")
            print(f"    - Vector dimensions: {features.shape[0]}")
            print(f"    - Extraction time: {elapsed*1000:.0f}ms")
            
            if features.shape[0] != 1280:
                print(f"  ✗ Expected 1280 dimensions, got {features.shape[0]}")
        else:
            print("  ⚠️  No test image found")
            
    except Exception as e:
        print(f"  ✗ Feature extraction failed: {e}")
else:
    print("  ⚠️  No images to test with")

# Test 7: Test similarity search (if database populated)
print("\n[Test 7] Testing similarity search...")
if stats['total_images'] > 0:
    try:
        images = store.get_all_images()
        test_embedding = images[0]['embedding']
        
        results = store.search_similar(test_embedding, threshold=0.5, limit=3)
        print(f"  ✓ Similarity search successful")
        print(f"    - Found {len(results)} matches")
        if results:
            print(f"    - Best match: {results[0]['object_name']} ({results[0]['similarity']:.2f})")
    except Exception as e:
        print(f"  ✗ Similarity search failed: {e}")
else:
    print("  ⚠️  Database empty, skipping test")

# Summary
print("\n" + "=" * 60)
print("Verification Summary")
print("=" * 60)

if stats['total_images'] == 0:
    print("\n⚠️  Next Steps:")
    print("  1. Run: python populate_database.py")
    print("  2. Run: python app.py")
    print("  3. Open: http://127.0.0.1:5000/dashboard")
else:
    print("\n✅ System is ready!")
    print("\nTo start the server:")
    print("  python app.py")
    print("\nThen open:")
    print("  http://127.0.0.1:5000/dashboard")

print("\n" + "=" * 60)
