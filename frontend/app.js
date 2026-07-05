const API_BASE = "http://127.0.0.1:5000";

const tabs = document.querySelectorAll(".method-tab");
const panels = document.querySelectorAll("[data-panel]");
const switchButtons = document.querySelectorAll("[data-switch-to]");
const statusBanner = document.querySelector("#status-banner");
const supportText = document.querySelector("#support-text");
const startCameraButton = document.querySelector("#start-camera-button");
const faceButton = document.querySelector("#face-login-button");
const faceForm = document.querySelector("#face-panel");
const emailForm = document.querySelector("#email-panel");
const togglePassword = document.querySelector("#toggle-password");
const passwordInput = document.querySelector("#password");
const faceVideo = document.querySelector("#face-video");
const faceCanvas = document.querySelector("#face-canvas");

let cameraStream = null;

function showStatus(message, type = "info") {
  statusBanner.textContent = message;
  statusBanner.className = `status-banner is-visible ${type === "error" ? "is-error" : ""} ${type === "success" ? "is-success" : ""}`;
}

function clearStatus() {
  statusBanner.textContent = "";
  statusBanner.className = "status-banner";
}

function setMode(mode) {
  clearStatus();
  if (mode !== "face") {
    teardownCamera();
  }

  tabs.forEach((tab) => {
    const isActive = tab.dataset.target === mode;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-selected", String(isActive));
  });

  panels.forEach((panel) => {
    const isActive = panel.dataset.panel === mode;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
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
  faceVideo.srcObject = null;
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

async function loginWithFace(image) {
  const response = await fetch(`${API_BASE}/api/face/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image }),
  });
  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.error || "Face recognition failed.");
  }

  return result;
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => setMode(tab.dataset.target));
});

switchButtons.forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.switchTo));
});

togglePassword.addEventListener("click", () => {
  const isHidden = passwordInput.type === "password";
  passwordInput.type = isHidden ? "text" : "password";
  togglePassword.textContent = isHidden ? "Hide" : "Show";
  togglePassword.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
});

startCameraButton.addEventListener("click", async () => {
  startCameraButton.disabled = true;
  showStatus("Requesting camera access...");

  try {
    await setupCamera(faceVideo);
    supportText.textContent = "Camera is ready. Keep one face centered and capture the scan.";
    showStatus("Camera started. Capture your face scan when ready.", "success");
  } catch (error) {
    showStatus(error.message || "Camera access was denied or unavailable.", "error");
  } finally {
    startCameraButton.disabled = false;
  }
});

faceForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  faceButton.disabled = true;
  showStatus("Capturing face scan...");

  try {
    const image = captureFaceFrame(faceVideo, faceCanvas);
    await loginWithFace(image);
    showStatus("Face recognition sign-in successful.", "success");
    teardownCamera();
  } catch (error) {
    showStatus(error.message || "Face recognition failed.", "error");
  } finally {
    faceButton.disabled = false;
  }
});

emailForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(emailForm);
  showStatus("Checking your credentials...");

  try {
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: formData.get("email"),
        password: formData.get("password"),
      }),
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Unable to sign in.");
    }

    showStatus("Email sign-in successful.", "success");
  } catch (error) {
    showStatus(error.message || "Email sign-in failed.", "error");
  }
});

window.addEventListener("beforeunload", teardownCamera);
