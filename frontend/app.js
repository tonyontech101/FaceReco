const API_BASE = "http://127.0.0.1:5000";

const tabs = document.querySelectorAll(".method-tab");
const panels = document.querySelectorAll("[data-panel]");
const switchButtons = document.querySelectorAll("[data-switch-to]");
const statusBanner = document.querySelector("#status-banner");
const supportText = document.querySelector("#support-text");
const faceButton = document.querySelector("#face-login-button");
const faceForm = document.querySelector("#face-panel");
const emailForm = document.querySelector("#email-panel");
const togglePassword = document.querySelector("#toggle-password");
const passwordInput = document.querySelector("#password");
const cameraBox = document.querySelector(".camera-box");
const faceVideo = document.querySelector("#face-video");
const faceCanvas = document.querySelector("#face-canvas");

let cameraStream = null;
let cameraStartPromise = null;

function showStatus(message, type = "info") {
  statusBanner.textContent = message;
  statusBanner.className = `status-banner is-visible ${type === "error" ? "is-error" : ""} ${type === "success" ? "is-success" : ""}`;
}

function clearStatus() {
  statusBanner.textContent = "";
  statusBanner.className = "status-banner";
}

function setScanningState(state) {
  cameraBox.dataset.scanState = state;
  faceButton.disabled = state !== "ready";
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

  if (mode === "face") {
    startFaceScan().catch(() => null);
  }
}

async function setupCamera(videoElement) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("This browser does not support camera access.");
  }

  teardownCamera();
  const stream = await navigator.mediaDevices.getUserMedia({
    video: {
      facingMode: "user",
      width: { ideal: 960 },
      height: { ideal: 720 },
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
  setScanningState("idle");
}

async function startFaceScan() {
  if (cameraStream) {
    setScanningState("ready");
    supportText.textContent = "Camera is ready. Keep one face centered and capture the scan.";
    return cameraStream;
  }

  if (cameraStartPromise) {
    return cameraStartPromise;
  }

  setScanningState("starting");
  showStatus("Requesting camera access...");
  supportText.textContent = "Starting camera. Your browser may ask for permission.";

  cameraStartPromise = setupCamera(faceVideo)
    .then((stream) => {
      if (faceForm.hidden) {
        teardownCamera();
        return stream;
      }

      setScanningState("ready");
      supportText.textContent = "Camera is ready. Keep one face centered and capture the scan.";
      showStatus("Camera ready. Capture your face scan when ready.", "success");
      return stream;
    })
    .catch((error) => {
      if (faceForm.hidden) {
        setScanningState("idle");
        return null;
      }

      setScanningState("error");
      supportText.textContent = "Camera access is needed for face recognition.";
      showStatus(error.message || "Camera access was denied or unavailable.", "error");
      throw error;
    })
    .finally(() => {
      cameraStartPromise = null;
    });

  return cameraStartPromise;
}

function captureFaceFrame(videoElement, canvasElement) {
  if (!cameraStream || videoElement.readyState < 2) {
    throw new Error("Wait for the camera preview before capturing your face scan.");
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

faceForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!cameraStream) {
    await startFaceScan().catch(() => null);
    if (!cameraStream) {
      return;
    }
  }

  faceButton.disabled = true;
  setScanningState("capturing");
  showStatus("Capturing face scan...");

  let signedIn = false;
  try {
    const image = captureFaceFrame(faceVideo, faceCanvas);
    await loginWithFace(image);
    signedIn = true;
    showStatus("Face recognition sign-in successful.", "success");
    teardownCamera();
  } catch (error) {
    setScanningState(cameraStream ? "ready" : "error");
    showStatus(error.message || "Face recognition failed.", "error");
  } finally {
    if (!signedIn && cameraStream) {
      faceButton.disabled = false;
    }
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

setScanningState("idle");
if (!faceForm.hidden) {
  startFaceScan().catch(() => null);
}
