import base64
import binascii
import os
from io import BytesIO

from flask import Flask, jsonify, request, send_from_directory

from storage import ExcelUserStore, hash_password, verify_password

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

FACE_MODEL = "face_recognition:dlib-128"
FACE_DISTANCE_THRESHOLD = float(os.getenv("FACE_DISTANCE_THRESHOLD", "0.5"))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
store = ExcelUserStore(DATA_PATH)


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
    store.ensure_workbook()
    app.run(host="127.0.0.1", port=5000, debug=True)
