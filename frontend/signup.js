const API_BASE = "http://127.0.0.1:5000";

const signupForm = document.querySelector("#signup-form");
const signupButton = document.querySelector("#signup-button");
const statusBanner = document.querySelector("#status-banner");
const togglePassword = document.querySelector("#toggle-password");
const passwordInput = document.querySelector("#password");
const confirmPasswordInput = document.querySelector("#confirm-password");
const setupFaceInput = document.querySelector("#setup-face");
const cameraBox = document.querySelector("#signup-camera-box");
const cameraActions = document.querySelector("#signup-camera-actions");
const startCameraButton = document.querySelector("#start-camera-button");
const captureFaceButton = document.querySelector("#capture-face-button");
const signupVideo = document.querySelector("#signup-video");
const signupCanvas = document.querySelector("#signup-canvas");

let cameraStream = null;
let enrolledEmail = "";

function showStatus(message, type = "info") {
  statusBanner.textContent = message;
  statusBanner.className = `status-banner is-visible ${type === "error" ? "is-error" : ""} ${type === "success" ? "is-success" : ""}`;
}

async function setupCamera(videoElement) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("This browser does not support camera access.");
  }

  teardownCamera();
  const stream = await navigator.mediaDevices.getUserMedia({
    video: {
      facingMode: "user",
      width: { ideal: 640 },
      height: { ideal: 480 },
    },
    audio: false,
  });

  cameraStream = stream;
  videoElement.srcObject = stream;
  await videoElement.play();
  return stream;
}

function teardownCamera() {
  if (!cameraStream) {
    return;
  }

  cameraStream.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  signupVideo.srcObject = null;
}

function captureFaceFrame(videoElement, canvasElement) {
  if (!cameraStream || videoElement.readyState < 2) {
    throw new Error("Start the camera before capturing your face scan.");
  }

  const width = videoElement.videoWidth || 640;
  const height = videoElement.videoHeight || 480;
  canvasElement.width = width;
  canvasElement.height = height;

  const context = canvasElement.getContext("2d");
  context.drawImage(videoElement, 0, 0, width, height);
  return canvasElement.toDataURL("image/jpeg", 0.9);
}

async function enrollFace(email, image) {
  const response = await fetch(`${API_BASE}/api/face/enroll`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, image }),
  });
  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.error || "Face enrollment failed.");
  }

  return result;
}

function showEnrollmentStep(email) {
  enrolledEmail = email;
  signupButton.hidden = true;
  cameraBox.hidden = false;
  cameraActions.hidden = false;
  signupForm.querySelectorAll("input").forEach((input) => {
    input.disabled = true;
  });
}

togglePassword.addEventListener("click", () => {
  const isHidden = passwordInput.type === "password";
  passwordInput.type = isHidden ? "text" : "password";
  confirmPasswordInput.type = isHidden ? "text" : "password";
  togglePassword.textContent = isHidden ? "Hide" : "Show";
  togglePassword.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
});

startCameraButton.addEventListener("click", async () => {
  startCameraButton.disabled = true;
  showStatus("Requesting camera access...");

  try {
    await setupCamera(signupVideo);
    showStatus("Camera started. Keep one face centered and capture the enrollment scan.", "success");
  } catch (error) {
    showStatus(error.message || "Camera access was denied or unavailable.", "error");
  } finally {
    startCameraButton.disabled = false;
  }
});

captureFaceButton.addEventListener("click", async () => {
  captureFaceButton.disabled = true;
  showStatus("Capturing face template...");

  try {
    const image = captureFaceFrame(signupVideo, signupCanvas);
    await enrollFace(enrolledEmail, image);
    showStatus("Account created and face recognition is ready. You can sign in now.", "success");
    teardownCamera();
  } catch (error) {
    showStatus(error.message || "Face enrollment failed.", "error");
  } finally {
    captureFaceButton.disabled = false;
  }
});

signupForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(signupForm);
  const name = String(formData.get("name") || "").trim();
  const email = String(formData.get("email") || "").trim().toLowerCase();
  const password = String(formData.get("password") || "");
  const confirmPassword = String(formData.get("confirm-password") || "");

  if (password !== confirmPassword) {
    showStatus("Passwords do not match.", "error");
    return;
  }

  signupButton.disabled = true;
  showStatus("Creating your account...");

  try {
    const response = await fetch(`${API_BASE}/api/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Unable to create your account.");
    }

    if (setupFaceInput.checked) {
      showEnrollmentStep(email);
      showStatus("Account created. Start the camera to enroll face recognition.", "success");
      return;
    }

    showStatus("Account created. You can sign in now.", "success");
  } catch (error) {
    showStatus(error.message || "Signup failed.", "error");
    signupButton.disabled = false;
  }
});

window.addEventListener("beforeunload", teardownCamera);
