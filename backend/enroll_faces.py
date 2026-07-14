import os
import sys
import json

# Add backend to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

import face_recognition

IMAGES_DIR = os.path.join(ROOT_DIR, "data", "images")
PROFILES_PATH = os.path.join(SCRIPT_DIR, "face_profiles.json")

# Special profiles with metadata and custom descriptions
SPECIAL_PROFILES = [
    {
        "name": "Melvin",
        "filenames": ["melvin.jpg"],
        "tags": ["black", "pantukan"],
        "description": "Melvin is from Pantukan, known as one of the most dangerous places in Davao de Oro due to the frequent shooting incidents in the area. Melvin's skin color is notably dark."
    },
    {
        "name": "Pocs",
        "filenames": ["pocs.jpg"],
        "tags": ["mankilam", "molester"],
        "description": "Pocs is from Mankilam but originally from the rural area of Maco. He is smart, but he has a thing for gay people."
    },
    {
        "name": "Nagao",
        "filenames": ["nagao.jpg", "nagao_2.jpg"],
        "tags": ["checter", "maragusan"],
        "description": "Nagao is from Maragusan and owns a motorcycle with his signature on it. He is also known as the biggest cheater in history."
    }
]

def main():
    profiles_data = []

    for p in SPECIAL_PROFILES:
        print(f"Processing {p['name']}...")
        embeddings = []
        for filename in p["filenames"]:
            file_path = os.path.join(IMAGES_DIR, filename)
            if not os.path.exists(file_path):
                print(f"  [ERROR] File {filename} not found at {file_path}")
                continue
            
            try:
                # Load image
                image = face_recognition.load_image_file(file_path)
                # Try different detection models/parameters to find the face
                face_locations = face_recognition.face_locations(image)
                if not face_locations:
                    print(f"  [WARNING] No face found in {filename} with default HOG. Trying with upsampling...")
                    face_locations = face_recognition.face_locations(image, number_of_times_to_upsample=2)
                if not face_locations:
                    print(f"  [WARNING] No face found with upsampling. Trying CNN model...")
                    face_locations = face_recognition.face_locations(image, model="cnn")
                
                if not face_locations:
                    print(f"  [ERROR] No face detected in {filename}")
                    continue
                
                # Get encoding
                encodings = face_recognition.face_encodings(image, known_face_locations=face_locations)
                if encodings:
                    embeddings.append(encodings[0].tolist())
                    print(f"  Successfully encoded {filename}")
                else:
                    print(f"  [ERROR] Could not extract encoding for {filename}")
            except Exception as e:
                print(f"  [ERROR] Failed to process {filename}: {e}")

        if not embeddings:
            print(f"  [ERROR] No face embeddings found for {p['name']}. Skipping profile creation.")
            continue

        # Save single or multiple embeddings
        profile = {
            "name": p["name"],
            "filenames": p["filenames"],
            "tags": p["tags"],
            "description": p["description"],
            "face_only": True
        }
        if len(embeddings) == 1:
            profile["embedding"] = embeddings[0]
        else:
            profile["embeddings"] = embeddings
        
        profiles_data.append(profile)

    if profiles_data:
        with open(PROFILES_PATH, "w") as f:
            json.dump({"profiles": profiles_data}, f, indent=2)
        print(f"\nSaved {len(profiles_data)} profiles to {PROFILES_PATH}")
    else:
        print("\nNo profiles were successfully created.")

if __name__ == "__main__":
    main()
