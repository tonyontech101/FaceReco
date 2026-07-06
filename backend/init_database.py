"""
Database Initialization Script
Resets and re-initializes the image database with base images.
"""

import os
import sys
from pathlib import Path

# Add backend to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from image_storage import ExcelImageStore
from populate_database import populate_database


# Paths
DATABASE_PATH = os.path.join(ROOT_DIR, "data", "image_database.xlsx")
IMAGES_DIR = os.path.join(ROOT_DIR, "data", "images")


def get_base_images():
    """
    Get list of base/original images (not user-uploaded).
    Base images follow naming pattern: object_number.ext
    """
    base_patterns = [
        "dog_", "cat_", "watch_", "banana_", "ballpen_", 
        "fruit_", "balpen_", "Ballpen_", "Watch_", "Dog_"
    ]
    
    base_images = []
    for file in os.listdir(IMAGES_DIR):
        # Check if filename starts with any base pattern
        if any(file.startswith(pattern) for pattern in base_patterns):
            base_images.append(file)
    
    return base_images


def clear_database(keep_user_uploads=False):
    """
    Clear database and optionally preserve user-uploaded images.
    
    Args:
        keep_user_uploads: If True, preserve images not in base set
    """
    if not os.path.exists(DATABASE_PATH):
        print("[INFO] Database does not exist yet.")
        return [], []
    
    store = ExcelImageStore(DATABASE_PATH)
    
    if not keep_user_uploads:
        # Complete wipe
        print("[INFO] Clearing entire database...")
        store.clear_database()
        return [], []
    
    # Preserve user uploads
    print("[INFO] Preserving user-uploaded images...")
    all_images = store.get_all_images()
    base_images = get_base_images()
    
    # Identify user uploads (not in base set)
    user_uploads = [img for img in all_images if img["filename"] not in base_images]
    user_files = [img["filename"] for img in user_uploads]
    
    print(f"[INFO] Found {len(user_uploads)} user-uploaded images to preserve")
    
    # Clear database
    store.clear_database()
    
    return user_uploads, user_files


def restore_user_uploads(user_uploads):
    """Restore user-uploaded images to database."""
    if not user_uploads:
        return
    
    print(f"\n[INFO] Restoring {len(user_uploads)} user-uploaded images...")
    store = ExcelImageStore(DATABASE_PATH)
    
    for img in user_uploads:
        try:
            store.add_image(
                filename=img["filename"],
                object_name=img["object_name"],
                category=img["category"],
                tags=img["tags"],
                file_path=img["file_path"],
                embedding=img["embedding"]
            )
            print(f"  ✓ Restored: {img['filename']}")
        except Exception as e:
            print(f"  ✗ Failed to restore {img['filename']}: {e}")


def delete_user_upload_files(user_files, base_images):
    """
    Delete user-uploaded image files from disk.
    Only deletes files not in base set.
    """
    if not user_files:
        return
    
    print(f"\n[INFO] Removing {len(user_files)} user-uploaded image files...")
    
    for filename in user_files:
        if filename in base_images:
            # Safety check - don't delete base images
            continue
        
        file_path = os.path.join(IMAGES_DIR, filename)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"  ✓ Removed: {filename}")
        except Exception as e:
            print(f"  ✗ Failed to remove {filename}: {e}")


def init_database(keep_user_uploads=False):
    """
    Initialize database with base images.
    
    Args:
        keep_user_uploads: If True, preserve user-uploaded images
    """
    print("=" * 60)
    print("Image Database Initialization")
    print("=" * 60)
    
    # Confirm action
    if os.path.exists(DATABASE_PATH):
        mode = "preserving user uploads" if keep_user_uploads else "DELETING ALL DATA"
        print(f"\n⚠️  WARNING: This will reset the database ({mode})")
        response = input("Continue? (yes/no): ").strip().lower()
        
        if response not in ["yes", "y"]:
            print("\n[INFO] Initialization cancelled.")
            return
    
    # Clear database and get user uploads
    user_uploads, user_files = clear_database(keep_user_uploads)
    
    if not keep_user_uploads and user_files:
        # Remove user-uploaded files from disk
        base_images = get_base_images()
        delete_user_upload_files(user_files, base_images)
    
    # Populate with base images
    print("\n" + "=" * 60)
    print("Populating Database with Base Images")
    print("=" * 60)
    populate_database(clear_existing=False)
    
    # Restore user uploads if needed
    if keep_user_uploads:
        restore_user_uploads(user_uploads)
    
    # Print final statistics
    print("\n" + "=" * 60)
    print("Initialization Complete")
    print("=" * 60)
    
    store = ExcelImageStore(DATABASE_PATH)
    stats = store.get_statistics()
    
    print(f"\nFinal Database Statistics:")
    print(f"  Total images:      {stats['total_images']}")
    print(f"  Unique objects:    {stats['unique_objects']}")
    print(f"  Unique categories: {stats['unique_categories']}")
    print(f"  Objects: {', '.join(stats['objects'])}")
    print(f"  Categories: {', '.join(stats['categories'])}")
    
    if keep_user_uploads and user_uploads:
        print(f"\n  User uploads preserved: {len(user_uploads)}")
    
    print("\n✓ Database initialization complete!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Initialize image database with base images"
    )
    parser.add_argument(
        "--keep-user-uploads",
        action="store_true",
        help="Preserve user-uploaded images (only reset base images)"
    )
    
    args = parser.parse_args()
    
    init_database(keep_user_uploads=args.keep_user_uploads)
