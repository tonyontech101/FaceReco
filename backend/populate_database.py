"""
Database Population Script
Scans data/images/ directory and populates the database with embeddings
for all existing images.
"""

import os
import re
import sys
from pathlib import Path

# Add backend to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from image_storage import ExcelImageStore, generate_description
from offline_vision_service import extract_image_features_from_file


# Paths
IMAGES_DIR = os.path.join(ROOT_DIR, "data", "images")
DATABASE_PATH = os.path.join(ROOT_DIR, "data", "image_database.xlsx")


# Category mapping based on object names
CATEGORY_MAP = {
    "dog": "Animal",
    "cat": "Animal",
    "bird": "Animal",
    "fish": "Animal",
    "horse": "Animal",
    "watch": "Accessory",
    "clock": "Accessory",
    "glasses": "Accessory",
    "sunglasses": "Accessory",
    "fruit": "Food",
    "banana": "Food",
    "apple": "Food",
    "orange": "Food",
    "vegetable": "Food",
    "ballpen": "Stationery",
    "pen": "Stationery",
    "pencil": "Stationery",
    "notebook": "Stationery",
    "laptop": "Electronics",
    "computer": "Electronics",
    "phone": "Electronics",
    "tablet": "Electronics",
    "car": "Vehicle",
    "bike": "Vehicle",
    "motorcycle": "Vehicle",
    "truck": "Vehicle",
}


def extract_object_name_from_filename(filename: str) -> str:
    """
    Extract object name from filename.
    Examples:
        "dog_1.jpg" -> "dog"
        "Watch_1.webp" -> "watch"
        "fruit_banana_2.jpg" -> "banana"
    """
    # Remove extension
    name = os.path.splitext(filename)[0]
    
    # Remove numbers and underscores from end
    name = re.sub(r'_\d+$', '', name)
    
    # Split by underscore and get the last meaningful part
    parts = name.split('_')
    
    # If we have "fruit_banana", prefer "banana"
    if len(parts) > 1 and parts[0].lower() in ['fruit', 'animal', 'object']:
        object_name = parts[-1]
    else:
        # Use the first part
        object_name = parts[0]
    
    # Capitalize first letter
    return object_name.capitalize()


def determine_category(object_name: str) -> str:
    """
    Determine category based on object name.
    
    Args:
        object_name: Object name (e.g., "Dog", "Watch")
        
    Returns:
        Category name (e.g., "Animal", "Accessory")
    """
    object_lower = object_name.lower()
    
    # Check exact match
    if object_lower in CATEGORY_MAP:
        return CATEGORY_MAP[object_lower]
    
    # Check partial match
    for key, category in CATEGORY_MAP.items():
        if key in object_lower or object_lower in key:
            return CATEGORY_MAP[key]
    
    # Default category
    return "Other"


def generate_tags(object_name: str, category: str) -> list:
    """
    Generate tags based on object name and category.
    
    Args:
        object_name: Object name (e.g., "Dog")
        category: Category (e.g., "Animal")
        
    Returns:
        List of tags
    """
    tags = []
    
    # Add object name (lowercase)
    tags.append(object_name.lower())
    
    # Add category (lowercase)
    if category and category != "Other":
        tags.append(category.lower())
    
    # Add common synonyms/related terms
    object_lower = object_name.lower()
    
    if object_lower == "dog":
        tags.extend(["pet", "canine", "puppy"])
    elif object_lower == "cat":
        tags.extend(["pet", "feline", "kitten"])
    elif object_lower == "watch":
        tags.extend(["timepiece", "wristwatch", "clock"])
    elif object_lower == "banana":
        tags.extend(["fruit", "yellow", "tropical"])
    elif object_lower == "ballpen":
        tags.extend(["pen", "writing", "office"])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    
    return unique_tags


def populate_database(clear_existing: bool = False):
    """
    Populate database with all images from data/images/ directory.
    
    Args:
        clear_existing: If True, clear existing database before populating
    """
    print("=" * 60)
    print("Image Database Population Script")
    print("=" * 60)
    
    # Initialize storage
    store = ExcelImageStore(DATABASE_PATH)
    
    if clear_existing:
        print("\n[INFO] Clearing existing database...")
        store.clear_database()
    else:
        store.ensure_workbook()
    
    # Get existing images to avoid duplicates
    existing_images = store.get_all_images()
    existing_filenames = {img["filename"] for img in existing_images}
    
    print(f"\n[INFO] Scanning {IMAGES_DIR}...")
    
    # Find all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    image_files = []
    
    for file in os.listdir(IMAGES_DIR):
        ext = os.path.splitext(file)[1].lower()
        if ext in image_extensions:
            image_files.append(file)
    
    if not image_files:
        print(f"[WARNING] No images found in {IMAGES_DIR}")
        return
    
    print(f"[INFO] Found {len(image_files)} images")
    
    if existing_filenames:
        print(f"[INFO] Database already contains {len(existing_filenames)} images")
    
    # Process each image
    processed = 0
    skipped = 0
    errors = 0
    
    for i, filename in enumerate(image_files, 1):
        # Skip if already in database
        if filename in existing_filenames:
            print(f"[{i}/{len(image_files)}] Skipping {filename} (already in database)")
            skipped += 1
            continue
        
        print(f"\n[{i}/{len(image_files)}] Processing {filename}...")
        
        try:
            # Full path to image
            file_path = os.path.join(IMAGES_DIR, filename)
            
            # Extract object name from filename
            object_name = extract_object_name_from_filename(filename)
            print(f"  - Object: {object_name}")
            
            # Determine category
            category = determine_category(object_name)
            print(f"  - Category: {category}")
            
            # Generate tags
            tags = generate_tags(object_name, category)
            print(f"  - Tags: {', '.join(tags)}")

            # Generate description
            description = generate_description(object_name, category, tags)
            print(f"  - Description: {description}")
            
            # Extract features
            print(f"  - Extracting features...")
            embedding = extract_image_features_from_file(file_path)
            print(f"  - Feature vector: {embedding.shape[0]} dimensions")
            
            # Save to database
            relative_path = f"images/{filename}"
            store.add_image(
                filename=filename,
                object_name=object_name,
                category=category,
                tags=tags,
                file_path=relative_path,
                embedding=embedding,
                description=description
            )
            
            print(f"  v Successfully added to database")
            processed += 1
            
        except Exception as e:
            print(f"  x Error processing {filename}: {e}")
            errors += 1
    
    # Print summary
    print("\n" + "=" * 60)
    print("Population Summary")
    print("=" * 60)
    print(f"Total images found:    {len(image_files)}")
    print(f"Successfully processed: {processed}")
    print(f"Skipped (existing):     {skipped}")
    print(f"Errors:                 {errors}")
    
    # Print database statistics
    stats = store.get_statistics()
    print(f"\nDatabase Statistics:")
    print(f"  Total images:      {stats['total_images']}")
    print(f"  Unique objects:    {stats['unique_objects']}")
    print(f"  Unique categories: {stats['unique_categories']}")
    print(f"  Objects: {', '.join(stats['objects'])}")
    print(f"  Categories: {', '.join(stats['categories'])}")
    
    print("\nv Database population complete!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Populate image database with embeddings")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing database before populating"
    )
    
    args = parser.parse_args()
    
    populate_database(clear_existing=args.clear)
