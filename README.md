# Face Recognition Login Interface

A premium responsive login prototype with two sign-in methods:

- Camera-based face recognition using a live webcam capture
- Email and password

The frontend uses HTML, CSS, and vanilla JavaScript. The backend uses Python Flask, `face_recognition`, and an Excel workbook as the prototype user database.

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
backend/
  app.py
  storage.py
  requirements.txt
data/
  users.xlsx
```

`data/users.xlsx` is created automatically when the backend starts.

## Install And Run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

If `pip install -r requirements.txt` fails on Windows while building `dlib`, install the prebuilt wheel first and then install the face recognition package without forcing a rebuild:

```powershell
pip install dlib-bin
pip install face_recognition --no-deps
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
