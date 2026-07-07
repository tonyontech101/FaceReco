import base64
import binascii
import os
import re
import time
from io import BytesIO

from flask import Flask, jsonify, request, send_from_directory

from storage import ExcelUserStore, hash_password, verify_password
from offline_vision_service import extract_image_features
from image_storage import ExcelImageStore

try:
    import face_recognition
    import numpy as np
    from PIL import Image
except ImportError:
    face_recognition = None
    np = None
    Image = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
DATA_PATH = os.path.join(ROOT_DIR, "data", "users.xlsx")
IMAGES_DIR = os.path.join(ROOT_DIR, "data", "images")
IMAGE_DB_PATH = os.path.join(ROOT_DIR, "data", "image_database.xlsx")

FACE_MODEL = "face_recognition:dlib-128"
FACE_DISTANCE_THRESHOLD = float(os.getenv("FACE_DISTANCE_THRESHOLD", "0.5"))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
store = ExcelUserStore(DATA_PATH)
image_store = ExcelImageStore(IMAGE_DB_PATH)


def cors_response(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.after_request
def add_cors_headers(response):
    return cors_response(response)


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/signup")
def signup_page():
    return send_from_directory(FRONTEND_DIR, "signup.html")


@app.route("/dashboard")
def dashboard_page():
    return send_from_directory(FRONTEND_DIR, "dashboard.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


@app.route("/api/auth/login", methods=["POST", "OPTIONS"])
def email_login():
    if request.method == "OPTIONS":
        return cors_response(jsonify({}))

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    user = store.get_user_by_email(email)
    if not user or not verify_password(password, user.get("password_hash", "")):
        return jsonify({"error": "Invalid email or password."}), 401

    return jsonify({"ok": True, "user": public_user(user)})


@app.route("/api/auth/signup", methods=["POST", "OPTIONS"])
def signup():
    if request.method == "OPTIONS":
        return cors_response(jsonify({}))

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not name:
        return jsonify({"error": "Enter your full name."}), 400
    if "@" not in email or "." not in email:
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    if store.get_user_by_email(email):
        return jsonify({"error": "An account already exists for that email."}), 409

    user = store.create_user(name=name, email=email, password_hash=hash_password(password))
    return jsonify({"ok": True, "user": public_user(user)}), 201


@app.route("/api/auth/register-demo-user", methods=["POST", "OPTIONS"])
def register_demo_user():
    if request.method == "OPTIONS":
        return cors_response(jsonify({}))

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "demo@example.com").strip().lower()
    password = payload.get("password") or "DemoPass123!"
    name = payload.get("name") or "Demo User"

    if store.get_user_by_email(email):
        return jsonify({"ok": True, "message": "User already exists."})

    store.create_user(name=name, email=email, password_hash=hash_password(password))
    return jsonify({"ok": True, "email": email, "password": password})


@app.route("/api/face/enroll", methods=["POST", "OPTIONS"])
def enroll_face():
    if request.method == "OPTIONS":
        return cors_response(jsonify({}))
    dependency_error = face_dependency_error()
    if dependency_error:
        return jsonify({"error": dependency_error}), 501

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    user = store.get_user_by_email(email)
    if not user:
        return jsonify({"error": "Create the account before enrolling face recognition."}), 404

    try:
        embedding = create_face_embedding(payload.get("image") or "")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    store.save_face_embedding(email=email, embedding=embedding, model_name=FACE_MODEL)
    return jsonify({"ok": True, "message": "Face template saved."})


@app.route("/api/face/login", methods=["POST", "OPTIONS"])
def face_login():
    if request.method == "OPTIONS":
        return cors_response(jsonify({}))
    dependency_error = face_dependency_error()
    if dependency_error:
        return jsonify({"error": dependency_error}), 501

    payload = request.get_json(silent=True) or {}
    enrolled_users = store.users_with_face_embeddings()
    if not enrolled_users:
        return jsonify({"error": "No face recognition templates are enrolled yet."}), 409

    try:
        candidate_embedding = create_face_embedding(payload.get("image") or "")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    best_match = min(
        (
            {
                "user": user,
                "comparison": compare_face_embeddings(user["face_embedding"], candidate_embedding),
            }
            for user in enrolled_users
        ),
        key=lambda match: match["comparison"]["distance"],
    )
    user = best_match["user"]
    comparison = best_match["comparison"]
    if not comparison["match"]:
        return jsonify({
            "error": "Face recognition did not match. Use email and password instead.",
            "distance": comparison["distance"],
            "threshold": FACE_DISTANCE_THRESHOLD,
        }), 401

    return jsonify({
        "ok": True,
        "user": face_login_user(user),
        "distance": comparison["distance"],
        "similarity": comparison["similarity"],
    })


@app.route("/api/vision/identify", methods=["POST", "OPTIONS"])
def identify_object():
    """
    DEPRECATED: This endpoint is kept for backward compatibility only.
    Please use /api/vision/identify-offline instead.
    
    Legacy behavior: Returns mock data in mock mode, redirects to offline in other modes.
    """
    if request.method == "OPTIONS":
        return cors_response(jsonify({}))

    payload = request.get_json(silent=True) or {}
    image_data = payload.get("image") or ""
    mode = payload.get("mode", "mock")

    # Validate image data
    if not image_data.startswith("data:image/"):
        return jsonify({"error": "A valid image is required."}), 400

    try:
        # Basic validation - decode to check format and size
        _, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded, validate=True)
        
        # Check file size (5MB limit)
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > 5:
            return jsonify({"error": f"Image size ({size_mb:.1f}MB) exceeds 5MB limit."}), 400
        
        # Validate format
        image = Image.open(BytesIO(image_bytes)) if Image else None
        if image:
            format_lower = image.format.lower() if image.format else ""
            if format_lower not in ["jpeg", "png", "webp", "jpg"]:
                return jsonify({"error": f"Unsupported format: {image.format}. Use JPEG, PNG, or WebP."}), 400
    except (ValueError, binascii.Error):
        return jsonify({"error": "The image could not be read."}), 400
    except Exception as e:
        return jsonify({"error": "Invalid image file."}), 400

    # Mock mode - return predefined responses
    if mode == "mock":
        mock_response = generate_mock_response()
        return jsonify(mock_response)

    # Any other mode - inform user to use offline endpoint
    return jsonify({
        "error": "This endpoint is deprecated. The system now runs in fully offline mode.",
        "message": "Please use /api/vision/identify-offline endpoint instead.",
        "offline_endpoint": "/api/vision/identify-offline"
    }), 410


@app.route("/api/vision/identify-offline", methods=["POST", "OPTIONS"])
def identify_object_offline():
    """
    Offline image identification using local MobileNetV2 model and database.
    Matches uploaded image against local database using cosine similarity.
    """
    if request.method == "OPTIONS":
        return cors_response(jsonify({}))

    payload = request.get_json(silent=True) or {}
    image_data = payload.get("image") or ""

    # Validate image data
    if not image_data.startswith("data:image/"):
        return jsonify({"error": "A valid image is required."}), 400

    try:
        # Basic validation - decode to check format and size
        _, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded, validate=True)
        
        # Check file size (5MB limit)
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > 5:
            return jsonify({"error": f"Image size ({size_mb:.1f}MB) exceeds 5MB limit."}), 400
        
        # Validate format
        image = Image.open(BytesIO(image_bytes)) if Image else None
        if image:
            format_lower = image.format.lower() if image.format else ""
            if format_lower not in ["jpeg", "png", "webp"]:
                return jsonify({"error": f"Unsupported format: {image.format}. Use JPEG, PNG, or WebP."}), 400
    except (ValueError, binascii.Error):
        return jsonify({"error": "The image could not be read."}), 400
    except Exception as e:
        return jsonify({"error": "Invalid image file."}), 400

    # Extract features from uploaded image
    try:
        print(f"[OfflineIdentify] Extracting features from uploaded image...")
        start_time = time.time()
        query_embedding = extract_image_features(image_data)
        extract_time = time.time() - start_time
        print(f"[OfflineIdentify] Feature extraction completed in {extract_time*1000:.0f}ms")
    except Exception as e:
        return jsonify({"error": f"Feature extraction failed: {str(e)}"}), 500

    # Search database for similar images (threshold: 0.4, limit: 10)
    # Lower threshold accounts for JPEG compression and preprocessing variations
    SIMILARITY_THRESHOLD = 0.4
    DISPLAY_LIMIT = 3
    
    try:
        print(f"[OfflineIdentify] Searching database for similar images...")
        search_start = time.time()
        similar_images = image_store.search_similar(
            query_embedding=query_embedding,
            threshold=SIMILARITY_THRESHOLD,
            limit=10  # Get more results initially
        )
        search_time = time.time() - search_start
        print(f"[OfflineIdentify] Database search completed in {search_time*1000:.0f}ms")
        print(f"[OfflineIdentify] Found {len(similar_images)} matches above threshold")
        
    except Exception as e:
        return jsonify({"error": f"Database search failed: {str(e)}"}), 500

    # Check if we have matches above threshold
    if not similar_images or similar_images[0]["similarity"] < SIMILARITY_THRESHOLD:
        # No match found - return no_match flag
        best_similarity = similar_images[0]["similarity"] if similar_images else 0.0
        print(f"[OfflineIdentify] No match found (best similarity: {best_similarity:.3f}, threshold: {SIMILARITY_THRESHOLD})")
        return jsonify({
            "no_match": True,
            "best_similarity": round(best_similarity, 2),
            "threshold": SIMILARITY_THRESHOLD
        })

    # Match found - get object info from best match
    best_match = similar_images[0]
    object_name = best_match["object_name"]
    category = best_match["category"]
    tags = best_match["tags"]
    
    print(f"[OfflineIdentify] Match found: {object_name} (similarity: {best_match['similarity']:.3f})")
    
    # We use all similar images found above the threshold instead of filtering by exact object name.
    # This allows other visually similar images (e.g., "Dog" images when a "Golden Retriever" is identified) to appear.
    same_object_images = similar_images
    
    # If we don't have enough images, search with a lower threshold
    if len(same_object_images) < DISPLAY_LIMIT:
        print(f"[OfflineIdentify] Only found {len(same_object_images)} images, searching with lower threshold...")
        
        # Get more results with lower threshold (0.2 = 20%)
        extended_search = image_store.search_similar(
            query_embedding=query_embedding,
            threshold=0.2,
            limit=20
        )
        
        same_object_images = extended_search
        print(f"[OfflineIdentify] Extended search found {len(same_object_images)} visually similar images")
    
    # Limit to top 3 for display
    display_images = same_object_images[:DISPLAY_LIMIT]
    
    if len(display_images) > 1:
        print(f"[OfflineIdentify] Showing {len(display_images)} {object_name} images:")
        for i, img in enumerate(display_images, 1):
            print(f"  {i}. {img['filename']} ({img['similarity']:.3f})")
    else:
        print(f"[OfflineIdentify] Only 1 {object_name} image available in database")

    # Format response
    response = {
        "object": {
            "name": object_name,
            "category": category,
            "tags": tags,
            "description": f"A {object_name} identified from your local database."
        },
        "similar_images": [
            {
                "image_id": img["image_id"],
                "filename": img["filename"],
                "url": f"/api/images/{img['filename']}",
                "thumbnail": f"/api/images/{img['filename']}",
                "title": f"{img['object_name']} - {img['filename']}",
                "source": "Local Database",
                "similarity": round(img["similarity"], 2)
            }
            for img in display_images
        ]
    }

    total_time = time.time() - start_time
    print(f"[OfflineIdentify] Total processing time: {total_time*1000:.0f}ms")

    return jsonify(response)


@app.route("/api/images/<filename>", methods=["GET"])
def serve_image(filename):
    """
    Serve images from data/images/ directory.
    Includes security checks to prevent path traversal.
    """
    # Security: validate filename (no path traversal)
    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 404
    
    # Check if file exists
    file_path = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "Image not found"}), 404
    
    # Serve file with appropriate MIME type
    return send_from_directory(IMAGES_DIR, filename)


@app.route("/api/vision/save-new-image", methods=["POST", "OPTIONS"])
def save_new_image():
    """
    Save a new image to the database when no match is found.
    User provides object_name, category, and tags.
    """
    if request.method == "OPTIONS":
        return cors_response(jsonify({}))

    payload = request.get_json(silent=True) or {}
    image_data = payload.get("image") or ""
    object_name = (payload.get("object_name") or "").strip()
    category = (payload.get("category") or "").strip()
    tags_input = payload.get("tags") or []

    # Validate inputs
    if not image_data.startswith("data:image/"):
        return jsonify({"error": "A valid image is required."}), 400
    
    if not object_name:
        return jsonify({"error": "Object name is required."}), 400
    
    if not category:
        return jsonify({"error": "Category is required."}), 400
    
    if not tags_input or not isinstance(tags_input, list):
        return jsonify({"error": "Tags must be a non-empty array."}), 400
    
    # Validate lengths
    if len(object_name) > 100:
        return jsonify({"error": "Object name too long (max 100 characters)."}), 400
    
    if len(category) > 50:
        return jsonify({"error": "Category too long (max 50 characters)."}), 400
    
    if len(tags_input) > 20:
        return jsonify({"error": "Too many tags (max 20)."}), 400

    # Validate image
    try:
        _, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded, validate=True)
        
        # Check file size (5MB limit)
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > 5:
            return jsonify({"error": f"Image size ({size_mb:.1f}MB) exceeds 5MB limit."}), 400
        
        # Validate format
        image = Image.open(BytesIO(image_bytes))
        format_lower = image.format.lower() if image.format else ""
        if format_lower not in ["jpeg", "png", "webp", "jpg"]:
            return jsonify({"error": f"Unsupported format: {image.format}. Use JPEG, PNG, or WebP."}), 400
        
    except (ValueError, binascii.Error):
        return jsonify({"error": "The image could not be read."}), 400
    except Exception as e:
        return jsonify({"error": f"Invalid image file: {str(e)}"}), 400

    # Generate unique filename
    # Sanitize object name: lowercase, replace spaces with underscores, remove special chars
    sanitized_name = re.sub(r'[^a-z0-9_]', '', object_name.lower().replace(' ', '_'))
    timestamp = int(time.time())
    filename = f"{sanitized_name}_{timestamp}.jpg"
    
    print(f"[SaveNewImage] Saving new image: {filename}")
    print(f"[SaveNewImage] Object: {object_name}, Category: {category}")

    # Save image file to disk
    try:
        file_path = os.path.join(IMAGES_DIR, filename)
        
        # Convert to RGB and save as JPEG
        image = image.convert('RGB')
        image.save(file_path, 'JPEG', quality=90)
        
        print(f"[SaveNewImage] Image saved to: {file_path}")
        
    except Exception as e:
        return jsonify({"error": f"Failed to save image file: {str(e)}"}), 500

    # Extract features
    try:
        print(f"[SaveNewImage] Extracting features...")
        embedding = extract_image_features(image_data)
        print(f"[SaveNewImage] Feature extraction completed")
        
    except Exception as e:
        # Clean up saved file on error
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": f"Feature extraction failed: {str(e)}"}), 500

    # Save to database
    try:
        relative_path = f"images/{filename}"
        image_record = image_store.add_image(
            filename=filename,
            object_name=object_name,
            category=category,
            tags=tags_input,
            file_path=relative_path,
            embedding=embedding
        )
        
        print(f"[SaveNewImage] Image added to database with ID: {image_record['image_id']}")
        
    except Exception as e:
        # Clean up saved file on error
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": f"Database save failed: {str(e)}"}), 500

    # Return success response
    return jsonify({
        "ok": True,
        "image_id": image_record["image_id"],
        "filename": filename,
        "message": "Image successfully added to database."
    })


def generate_mock_response():
    """Generate realistic mock data for object identification"""
    import random
    
    mock_objects = [
        {
            "name": "Golden Retriever",
            "description": "A friendly and intelligent dog breed known for its golden-colored coat. Golden Retrievers are popular family pets, originally bred for retrieving waterfowl during hunting. They are loyal, gentle, and great with children.",
            "tags": ["dog", "pet", "golden retriever", "animal", "mammal", "canine"]
        },
        {
            "name": "Coffee Mug",
            "description": "A ceramic drinking vessel typically used for hot beverages like coffee or tea. This style features a classic cylindrical shape with a handle for comfortable grip. Often used in homes and offices.",
            "tags": ["mug", "coffee", "cup", "kitchen", "ceramic", "beverage"]
        },
        {
            "name": "Laptop Computer",
            "description": "A portable personal computer with an integrated screen and keyboard. Modern laptops are essential tools for work, education, and entertainment, offering computing power in a mobile form factor.",
            "tags": ["laptop", "computer", "technology", "electronics", "device", "portable"]
        },
        {
            "name": "Houseplant",
            "description": "An indoor plant commonly kept for decorative purposes and air purification. Houseplants add natural beauty to living spaces and can improve indoor air quality. This appears to be a variety with broad green leaves.",
            "tags": ["plant", "houseplant", "indoor", "green", "nature", "decoration"]
        }
    ]
    
    # Randomly select one object
    obj = random.choice(mock_objects)
    
    # Generate mock similar images
    similar_images = [
        {
            "url": f"https://picsum.photos/seed/{random.randint(1000, 9999)}/800/600",
            "thumbnail": f"https://picsum.photos/seed/{random.randint(1000, 9999)}/200/150",
            "title": f"{obj['name']} - Example {i+1}",
            "source": random.choice(["example.com", "photos.com", "images.net", "pictures.org"])
        }
        for i in range(6)
    ]
    
    return {
        "object": obj,
        "similar_images": similar_images
    }


@app.route("/api/auth/webauthn/<path:_unused>", methods=["GET", "POST", "OPTIONS"])
def webauthn_disabled(_unused):
    if request.method == "OPTIONS":
        return cors_response(jsonify({}))
    return jsonify({"error": "WebAuthn/passkey authentication has been replaced by camera-based face recognition."}), 410


def public_user(user):
    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
    }


def face_login_user(user):
    return {
        "user_id": user["user_id"],
        "name": user["name"],
    }


def face_dependency_error():
    if face_recognition is None or np is None or Image is None:
        return "Install face_recognition, numpy, and Pillow to enable camera-based face recognition."
    return None


def create_face_embedding(image_data_url):
    image_array = decode_image_data_url(image_data_url)
    face_locations = face_recognition.face_locations(image_array, model="hog")
    if not face_locations:
        raise ValueError("No face was detected. Center your face in the frame and try again.")
    if len(face_locations) > 1:
        raise ValueError("More than one face was detected. Only one person should be in frame.")

    # face_recognition aligns faces internally from facial landmarks before creating its 128D template.
    encodings = face_recognition.face_encodings(image_array, known_face_locations=face_locations, num_jitters=1)
    if not encodings:
        raise ValueError("A face was detected, but an embedding could not be created. Try better lighting.")

    return [float(value) for value in encodings[0]]


def decode_image_data_url(image_data_url):
    if not image_data_url.startswith("data:image/"):
        raise ValueError("A camera image is required.")

    try:
        _, encoded = image_data_url.split(",", 1)
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("The camera image could not be read.")

    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise ValueError("The camera image is not a valid image file.")

    return np.array(image)


def compare_face_embeddings(saved_embedding, candidate_embedding):
    saved = np.array(saved_embedding, dtype=np.float64)
    candidate = np.array(candidate_embedding, dtype=np.float64)
    distance = float(np.linalg.norm(saved - candidate))
    similarity = max(0.0, 1.0 - distance)

    return {
        "match": distance <= FACE_DISTANCE_THRESHOLD,
        "distance": round(distance, 4),
        "similarity": round(similarity, 4),
    }


if __name__ == "__main__":
    try:
        store.ensure_workbook()
        image_store.ensure_workbook()
    except PermissionError as e:
        print("\n" + "=" * 60)
        print("ERROR: Cannot access database file")
        print("=" * 60)
        print(f"\n{e}")
        print("\nThis usually happens when the Excel file is open in another program.")
        print("\nPlease:")
        print("  1. Close Microsoft Excel (or any program viewing the .xlsx files)")
        print("  2. Make sure these files are not open:")
        print(f"     - {DATA_PATH}")
        print(f"     - {IMAGE_DB_PATH}")
        print("  3. Try running the server again")
        print("\n" + "=" * 60)
        import sys
        sys.exit(1)
    except Exception as e:
        print(f"\nError initializing databases: {e}")
        import sys
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Server Starting")
    print("=" * 60)
    print(f"User database: {DATA_PATH}")
    print(f"Image database: {IMAGE_DB_PATH}")
    print("\nServer running at: http://127.0.0.1:5000")
    print("Dashboard: http://127.0.0.1:5000/dashboard")
    print("=" * 60 + "\n")
    
    app.run(host="127.0.0.1", port=5000, debug=True)
