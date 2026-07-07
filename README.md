# Face Recognition Login Interface

A premium responsive login prototype with two sign-in methods:

- Camera-based face recognition using a live webcam capture
- Email and password

After successful login, users are redirected to an **AI-powered image recognition dashboard** that works **completely offline**:
- **Upload** or **scan** images with your camera
- **Identify objects** using local MobileNetV2 model (no internet required)
- **View similar images** from your local database
- **Add new objects** to expand the database over time

The frontend uses HTML, CSS, and vanilla JavaScript. The backend uses Python Flask, `face_recognition`, TensorFlow/Keras with MobileNetV2, and an Excel workbook as the prototype database.

## Requirements

- Python 3.11+
- A webcam or laptop camera for face enrollment and login
- On Windows, Visual C++ Build Tools may be required if `dlib` needs to compile from source

## Project Structure

```text
frontend/
  index.html
  styles.css
  app.js
  signup.html
  signup.js
  dashboard.html
  dashboard.css
  dashboard.js
backend/
  app.py
  storage.py
  offline_vision_service.py
  image_storage.py
  populate_database.py
  init_database.py
  requirements.txt
data/
  users.xlsx
  image_database.xlsx
  images/
```

`data/users.xlsx` and `data/image_database.xlsx` are created automatically when the backend starts.

## Install And Run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If `pip install -r requirements.txt` fails on Windows while building `dlib`, install the prebuilt wheel first and then install the face recognition package without forcing a rebuild:

```powershell
pip install dlib-bin
pip install face_recognition --no-deps
```

**Initialize the image database:**

```powershell
python populate_database.py
```

This will scan all images in `data/images/` and generate feature embeddings using MobileNetV2. First run will download the model (~14MB).

**Start the server:**

```powershell
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

Signup page:

```text
http://127.0.0.1:5000/signup
```

## Create A Demo Email User

After the backend starts, send a request to create a prototype user:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/auth/register-demo-user -ContentType "application/json" -Body '{"email":"demo@example.com","password":"DemoPass123!","name":"Demo User"}'
```

Then sign in with:

```text
demo@example.com
DemoPass123!
```

## Offline Image Recognition Dashboard

After successful login, you will be redirected to the dashboard where you can:

### How It Works

The dashboard uses **MobileNetV2** (pre-trained on ImageNet) to extract 1280-dimensional feature vectors from images. These features are compared against a local database using **cosine similarity** to find matching objects.

**Similarity Threshold:** The system uses a 40% similarity threshold. This accounts for:
- JPEG compression artifacts when images are uploaded
- Slight variations in image preprocessing
- Floating-point precision differences

**Flow:**
1. **Upload or scan** an image
2. **Feature extraction** - MobileNetV2 processes the image (~50-200ms)
3. **Database search** - Compare against all stored images
4. **Match found (≥40% similarity)**:
   - Display object name, category, and tags
   - Show top 3 most similar images with similarity scores
5. **No match (<40% similarity)**:
   - Modal appears asking you to label the object
   - Provide object name, category, and tags
   - Image is saved to database for future matches

### Adding Images to Database

**Option 1: Place images in `data/images/` and run the population script**

```powershell
cd backend
python populate_database.py
```

**Option 2: Upload through the dashboard**

When you upload an image that doesn't match anything in the database, a modal will appear asking you to provide:
- Object name (e.g., "Laptop")
- Category (e.g., "Electronics")
- Tags (e.g., "laptop, computer, device")

The image will be automatically added to the database and available for future matches.

### Database Management

**View database statistics:**

```powershell
python -c "from image_storage import ExcelImageStore; import os; store = ExcelImageStore(os.path.join('..', 'data', 'image_database.xlsx')); print(store.get_statistics())"
```

**Reset database to original state:**

```powershell
python init_database.py
```

**Reset but keep user-uploaded images:**

```powershell
python init_database.py --keep-user-uploads
```

### Performance

- **Model loading**: ~2-5 seconds (first request only, then cached)
- **Feature extraction**: ~50-200ms per image
- **Database search**: ~10-50ms (depends on database size)
- **Total identification time**: Usually <500ms

### Offline Operation

The system works completely offline:
- ✅ No API keys required
- ✅ No internet connection needed (after initial model download)
- ✅ All data stored locally in Excel and filesystem
- ✅ Privacy-focused - images never leave your computer

## Face Recognition Notes

The previous browser-credential flow has been disabled. Face recognition now works by capturing a webcam frame in the browser, sending it to Flask, detecting one face, creating a 128-dimensional face embedding, and saving only that embedding in Excel.

Signup enrollment:

1. Create the account.
2. Start the webcam.
3. Capture one face scan.
4. Save the face template.

Login:

1. Enter email.
2. Start the webcam.
3. Capture one face scan.
4. Compare the new embedding to the saved template.

The matching threshold is controlled by `FACE_DISTANCE_THRESHOLD` in `backend/app.py`. Lower values are stricter; higher values are more permissive.

## Prototype Warning

Excel is fine for a class project or local prototype, but it is not a production authentication database. For production, replace it with PostgreSQL, MySQL, or another transactional database.
