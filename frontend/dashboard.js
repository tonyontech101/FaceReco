const API_BASE = "http://127.0.0.1:5000";

// DOM Elements
const statusBanner = document.getElementById("status-banner");
const userNameElement = document.getElementById("user-name");
const logoutButton = document.getElementById("logout-button");

// Tab Controls
const scanTab = document.getElementById("scan-tab");
const uploadTab = document.getElementById("upload-tab");
const switchToUpload = document.getElementById("switch-to-upload");
const switchToCamera = document.getElementById("switch-to-camera");

// Panels
const actionPanel = document.getElementById("action-panel");
const scanPanel = document.getElementById("scan-panel");
const uploadPanel = document.getElementById("upload-panel");
const resultsPanel = document.getElementById("results-panel");

// Camera Elements
const cameraBox = document.getElementById("camera-box");
const scanVideo = document.getElementById("scan-video");
const scanCanvas = document.getElementById("scan-canvas");
const captureButton = document.getElementById("capture-button");
const cameraStatus = document.getElementById("camera-status");
const cameraStatusIndicator = document.getElementById("camera-status-indicator");
const cameraStatusText = document.getElementById("camera-status-text");
const statusDot = document.querySelector(".status-dot");

// Upload Elements
const uploadBox = document.getElementById("upload-box");
const uploadArea = document.getElementById("upload-area");
const previewArea = document.getElementById("preview-area");
const fileInput = document.getElementById("file-input");
const previewImage = document.getElementById("preview-image");
const previewName = document.getElementById("preview-name");
const previewSize = document.getElementById("preview-size");
const uploadCardFooter = document.getElementById("upload-card-footer");
const changeImageButton = document.getElementById("change-image-button");
const identifyButton = document.getElementById("identify-button");

// Results Elements
const captureTimestamp = document.getElementById("capture-timestamp");
const objectName = document.getElementById("object-name");
const objectDescription = document.getElementById("object-description");
const tagsContainer = document.getElementById("tags-container");
const imageGrid = document.getElementById("image-grid");
const emptyState = document.getElementById("empty-state");
const scanAnotherButton = document.getElementById("scan-another-button");

// Modal Elements
const noMatchModal = document.getElementById("no-match-modal");
const modalPreviewImage = document.getElementById("modal-preview-image");
const modalSimilarityText = document.getElementById("modal-similarity-text");
const noMatchForm = document.getElementById("no-match-form");
const inputObjectName = document.getElementById("input-object-name");
const inputCategory = document.getElementById("input-category");
const inputTags = document.getElementById("input-tags");
const modalError = document.getElementById("modal-error");
const modalCancelButton = document.getElementById("modal-cancel-button");
const modalSaveButton = document.getElementById("modal-save-button");

// State
let cameraStream = null;
let cameraStartPromise = null;
let selectedFile = null;
let selectedImageData = null;
let captureTime = null;
let pendingImageData = null; // Store image data while showing modal

// ============ Utility Functions ============

function showStatus(message, type = "info") {
  statusBanner.textContent = message;
  statusBanner.className = `status-banner is-visible ${type === "error" ? "is-error" : ""} ${type === "success" ? "is-success" : ""}`;
}

function clearStatus() {
  statusBanner.textContent = "";
  statusBanner.className = "status-banner";
}

function showLoading(element) {
  element.classList.add("is-loading");
}

function hideLoading(element) {
  element.classList.remove("is-loading");
}

// ============ Auth Guard ============

function checkAuth() {
  const user = JSON.parse(localStorage.getItem("user") || "null");
  if (!user || !user.name) {
    window.location.href = "/";
    return false;
  }
  userNameElement.textContent = user.name;
  return true;
}

function logout() {
  localStorage.removeItem("user");
  window.location.href = "/";
}

// ============ Tab Switching ============

function switchTab(target) {
  clearStatus();
  
  // Update tab states
  [scanTab, uploadTab].forEach(tab => {
    const isActive = tab.dataset.target === target;
    tab.classList.toggle("is-active", isActive);
  });

  // Update panel visibility
  if (target === "scan") {
    scanPanel.classList.add("is-active");
    scanPanel.hidden = false;
    uploadPanel.classList.remove("is-active");
    uploadPanel.hidden = true;
    startCamera();
  } else {
    uploadPanel.classList.add("is-active");
    uploadPanel.hidden = false;
    scanPanel.classList.remove("is-active");
    scanPanel.hidden = true;
    stopCamera();
  }
}

// ============ Camera Functions ============

function setScanState(state) {
  cameraBox.dataset.scanState = state;
  captureButton.disabled = state !== "ready";
  
  // Update status indicator
  if (statusDot) {
    statusDot.dataset.status = state;
  }
  
  // Update status text
  const statusMessages = {
    idle: "Starting...",
    starting: "Requesting access...",
    ready: "Ready",
    capturing: "Capturing...",
    frozen: "Captured",
    error: "Error"
  };
  
  if (cameraStatusText) {
    cameraStatusText.textContent = statusMessages[state] || "Unknown";
  }
}

async function setupCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("This browser does not support camera access.");
  }

  stopCamera();
  const stream = await navigator.mediaDevices.getUserMedia({
    video: {
      facingMode: "environment", // Prefer back camera on mobile
      width: { ideal: 1280 },
      height: { ideal: 720 },
    },
    audio: false,
  });

  cameraStream = stream;
  scanVideo.srcObject = stream;
  await scanVideo.play();
  return stream;
}

function stopCamera() {
  if (!cameraStream) return;
  
  cameraStream.getTracks().forEach(track => track.stop());
  cameraStream = null;
  scanVideo.srcObject = null;
  scanCanvas.hidden = true;
  setScanState("idle");
}

async function startCamera() {
  if (cameraStream) {
    setScanState("ready");
    cameraStatus.textContent = "Camera is ready. Position the object clearly in frame.";
    return cameraStream;
  }

  if (cameraStartPromise) {
    return cameraStartPromise;
  }

  setScanState("starting");
  showStatus("Requesting camera access...");
  cameraStatus.textContent = "Starting camera. Your browser may ask for permission.";

  cameraStartPromise = setupCamera()
    .then(stream => {
      if (scanPanel.hidden) {
        stopCamera();
        return stream;
      }

      setScanState("ready");
      cameraStatus.textContent = "Camera is ready. Position the object clearly in frame.";
      showStatus("Camera ready. Capture when ready.", "success");
      return stream;
    })
    .catch(error => {
      if (scanPanel.hidden) {
        setScanState("idle");
        return null;
      }

      setScanState("error");
      cameraStatus.textContent = "Camera access is needed for scanning.";
      showStatus(error.message || "Camera access was denied or unavailable.", "error");
      throw error;
    })
    .finally(() => {
      cameraStartPromise = null;
    });

  return cameraStartPromise;
}

function captureFrame() {
  if (!cameraStream || scanVideo.readyState < 2) {
    throw new Error("Wait for the camera preview before capturing.");
  }

  const width = scanVideo.videoWidth || 640;
  const height = scanVideo.videoHeight || 480;
  scanCanvas.width = width;
  scanCanvas.height = height;

  const context = scanCanvas.getContext("2d");
  context.drawImage(scanVideo, 0, 0, width, height);
  
  // Store capture time
  captureTime = new Date();
  
  // Freeze the camera view by showing canvas
  setScanState("frozen");
  scanCanvas.hidden = false;
  
  return scanCanvas.toDataURL("image/jpeg", 0.9);
}

async function handleCapture() {
  if (!cameraStream) {
    await startCamera().catch(() => null);
    if (!cameraStream) return;
  }

  captureButton.disabled = true;
  setScanState("capturing");
  showStatus("Capturing image...");

  try {
    const imageData = captureFrame();
    await identifyObject(imageData);
    stopCamera();
  } catch (error) {
    setScanState(cameraStream ? "ready" : "error");
    showStatus(error.message || "Capture failed.", "error");
    captureButton.disabled = false;
  }
}

// ============ Upload Functions ============

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function validateFile(file) {
  const validTypes = ["image/jpeg", "image/png", "image/webp"];
  const maxSize = 5 * 1024 * 1024; // 5MB

  if (!validTypes.includes(file.type)) {
    throw new Error("Invalid file type. Please upload JPEG, PNG, or WebP images.");
  }

  if (file.size > maxSize) {
    throw new Error(`File size (${formatFileSize(file.size)}) exceeds 5MB limit.`);
  }
}

function handleFileSelect(file) {
  clearStatus();

  try {
    validateFile(file);
    selectedFile = file;

    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImage.src = e.target.result;
      previewName.textContent = file.name;
      previewSize.textContent = formatFileSize(file.size);
      
      uploadArea.hidden = true;
      previewArea.hidden = false;
      
      // Show identify and change buttons in footer
      changeImageButton.hidden = false;
      identifyButton.hidden = false;

      // Store image data for API call
      selectedImageData = e.target.result;
    };
    reader.readAsDataURL(file);
  } catch (error) {
    showStatus(error.message, "error");
  }
}

function resetUploadState() {
  selectedFile = null;
  selectedImageData = null;
  previewImage.src = "";
  uploadArea.hidden = false;
  previewArea.hidden = true;
  changeImageButton.hidden = true;
  identifyButton.hidden = true;
  fileInput.value = "";
}

// ============ API Functions ============

async function identifyObject(imageData) {
  showLoading(actionPanel);
  clearStatus();
  showStatus("Analyzing image...");

  try {
    // Use offline endpoint for local image recognition
    const response = await fetch(`${API_BASE}/api/vision/identify-offline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        image: imageData
      })
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Unable to identify object.");
    }

    // Check if no match was found (similarity < 50%)
    if (result.no_match) {
      showNoMatchModal(imageData, result.best_similarity);
      return;
    }

    // Check if object was successfully identified
    if (!result.object || !result.object.name) {
      throw new Error("Unable to identify object. Try a clearer image or different object.");
    }

    displayResults(result);
  } catch (error) {
    if (error.message.includes("Failed to fetch") || error.message.includes("NetworkError")) {
      showStatus("Network error. Please check your connection and try again.", "error");
    } else {
      showStatus(error.message || "Identification failed. Please try again.", "error");
    }
  } finally {
    hideLoading(actionPanel);
  }
}

// ============ Results Display ============

function displayResults(data) {
  const { object, similar_images } = data;

  // Display hero image (captured/uploaded image)
  const heroImage = document.getElementById("hero-image");
  if (selectedImageData) {
    heroImage.src = selectedImageData;
  } else if (scanCanvas.width > 0) {
    // Use the frozen canvas frame
    heroImage.src = scanCanvas.toDataURL("image/jpeg", 0.9);
  }
  
  // Display capture timestamp
  if (captureTime && captureTimestamp) {
    const options = { 
      month: 'long', 
      day: 'numeric', 
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    };
    const formattedDate = captureTime.toLocaleDateString('en-US', options);
    const formattedTime = captureTime.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    captureTimestamp.textContent = `Captured on ${formattedDate.split(',')[0]}, ${captureTime.getFullYear()} • ${formattedTime}`;
  }

  // Display object info
  objectName.textContent = object.name || "Unknown Object";
  objectDescription.textContent = object.description || "No description available.";

  // Display tags
  tagsContainer.innerHTML = "";
  if (object.tags && object.tags.length > 0) {
    object.tags.forEach(tag => {
      const tagElement = document.createElement("span");
      tagElement.className = "tag";
      tagElement.textContent = tag;
      tagsContainer.appendChild(tagElement);
    });
  } else {
    const noTags = document.createElement("span");
    noTags.className = "tag";
    noTags.textContent = "no tags";
    noTags.style.opacity = "0.5";
    tagsContainer.appendChild(noTags);
  }

  // Display similar images (limit to 3 for featured layout)
  imageGrid.innerHTML = "";
  if (similar_images && similar_images.length > 0) {
    const featuredImages = similar_images.slice(0, 3); // Limit to 3 images
    featuredImages.forEach(img => {
      const card = document.createElement("div");
      card.className = "image-card";
      
      // Format similarity score as percentage
      const similarityPercent = img.similarity ? Math.round(img.similarity * 100) : null;
      const similarityBadge = similarityPercent ? 
        `<span class="similarity-badge">${similarityPercent}% similar</span>` : '';
      
      card.innerHTML = `
        <img src="${img.thumbnail || img.url}" 
             alt="${img.title || 'Similar image'}" 
             loading="lazy"
             onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22150%22%3E%3Crect fill=%22%23f8f5ef%22 width=%22200%22 height=%22150%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22%23746f67%22 font-family=%22sans-serif%22%3EImage unavailable%3C/text%3E%3C/svg%3E'">
        ${similarityBadge}
        <div class="image-card-info">
          <p class="image-card-title">${img.title || 'Similar Image'}</p>
          <p class="image-card-source">${img.source || 'Local Database'}</p>
        </div>
      `;
      imageGrid.appendChild(card);
    });
  } else {
    // Show empty state for similar images
    const emptyStateDiv = document.createElement("div");
    emptyStateDiv.className = "empty-state";
    emptyStateDiv.innerHTML = `
      <div class="empty-placeholder">
        <svg class="empty-icon" aria-hidden="true"><use href="#icon-image"></use></svg>
        <p class="empty-text">No similar images found yet.</p>
        <p class="empty-hint">Capture another image to compare.</p>
      </div>
    `;
    imageGrid.appendChild(emptyStateDiv);
  }

  // Show results, hide action panel
  actionPanel.hidden = true;
  resultsPanel.hidden = false;
  
  // Clear the analyzing status and show success
  setTimeout(() => {
    showStatus("Object identified successfully!", "success");
  }, 100);
}

function resetToActionPanel() {
  resultsPanel.hidden = true;
  actionPanel.hidden = false;
  clearStatus();
  
  // Reset upload state
  resetUploadState();
  
  // Reset camera state if on scan tab
  if (!scanPanel.hidden) {
    scanCanvas.hidden = true;
    startCamera();
  }
}

// ============ No Match Modal Functions ============

function showNoMatchModal(imageData, bestSimilarity) {
  pendingImageData = imageData;
  
  // Show preview image
  modalPreviewImage.src = imageData;
  
  // Show similarity score
  const similarityPercent = Math.round(bestSimilarity * 100);
  modalSimilarityText.textContent = `Best match: ${similarityPercent}% similar (below 40% threshold)`;
  
  // Clear form
  noMatchForm.reset();
  modalError.hidden = true;
  
  // Show modal
  noMatchModal.hidden = false;
  
  // Hide loading and clear status
  hideLoading(actionPanel);
  clearStatus();
}

function hideNoMatchModal() {
  noMatchModal.hidden = true;
  pendingImageData = null;
  noMatchForm.reset();
  modalError.hidden = true;
}

function showModalError(message) {
  modalError.textContent = message;
  modalError.hidden = false;
}

function hideModalError() {
  modalError.hidden = true;
}

async function handleModalSave() {
  // Validate inputs
  const objectName = inputObjectName.value.trim();
  const category = inputCategory.value.trim();
  const tagsInput = inputTags.value.trim();
  
  hideModalError();
  
  if (!objectName) {
    showModalError("Object name is required.");
    inputObjectName.focus();
    return;
  }
  
  if (!category) {
    showModalError("Category is required.");
    inputCategory.focus();
    return;
  }
  
  if (!tagsInput) {
    showModalError("Tags are required.");
    inputTags.focus();
    return;
  }
  
  // Parse tags (comma-separated)
  const tags = tagsInput.split(',').map(t => t.trim()).filter(t => t.length > 0);
  
  if (tags.length === 0) {
    showModalError("Please provide at least one tag.");
    inputTags.focus();
    return;
  }
  
  if (tags.length > 20) {
    showModalError("Too many tags (maximum 20).");
    inputTags.focus();
    return;
  }
  
  // Disable save button
  modalSaveButton.disabled = true;
  modalSaveButton.textContent = "Saving...";
  
  try {
    // Call save-new-image endpoint
    const response = await fetch(`${API_BASE}/api/vision/save-new-image`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image: pendingImageData,
        object_name: objectName,
        category: category,
        tags: tags
      })
    });
    
    const result = await response.json();
    
    if (!response.ok) {
      throw new Error(result.error || "Failed to save image.");
    }
    
    // Success - hide modal and show success message
    hideNoMatchModal();
    showStatus(`Successfully added "${objectName}" to the database!`, "success");
    
    // Display the newly added image as a result
    displayNewImageResult(objectName, category, tags, result.filename);
    
  } catch (error) {
    showModalError(error.message || "Failed to save image. Please try again.");
  } finally {
    modalSaveButton.disabled = false;
    modalSaveButton.textContent = "Save to Database";
  }
}

function displayNewImageResult(objectName, category, tags, filename) {
  // Create a result object for the newly added image
  const result = {
    object: {
      name: objectName,
      category: category,
      tags: tags,
      description: `A ${objectName} that you just added to the database.`
    },
    similar_images: [
      {
        filename: filename,
        url: `/api/images/${filename}`,
        thumbnail: `/api/images/${filename}`,
        title: `${objectName} - ${filename}`,
        source: "Local Database",
        similarity: 1.0
      }
    ]
  };
  
  displayResults(result);
}

function handleModalCancel() {
  hideNoMatchModal();
  resetToActionPanel();
}

// ============ Event Listeners ============

// Auth
logoutButton.addEventListener("click", logout);

// Tabs
scanTab.addEventListener("click", () => switchTab("scan"));
uploadTab.addEventListener("click", () => switchTab("upload"));

// Switch buttons in card footers
if (switchToUpload) {
  switchToUpload.addEventListener("click", () => switchTab("upload"));
}
if (switchToCamera) {
  switchToCamera.addEventListener("click", () => switchTab("scan"));
}

// Camera
captureButton.addEventListener("click", handleCapture);

// Upload - Click to browse
uploadArea.addEventListener("click", () => fileInput.click());

// Upload - File input change
fileInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) handleFileSelect(file);
});

// Upload - Drag and drop
uploadArea.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadArea.style.borderColor = "var(--accent)";
  uploadArea.style.background = "var(--surface-strong)";
});

uploadArea.addEventListener("dragleave", () => {
  uploadArea.style.borderColor = "";
  uploadArea.style.background = "";
});

uploadArea.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadArea.style.borderColor = "";
  uploadArea.style.background = "";
  
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});

// Upload - Change image
changeImageButton.addEventListener("click", resetUploadState);

// Upload - Identify
identifyButton.addEventListener("click", () => {
  if (selectedImageData) {
    identifyObject(selectedImageData);
  }
});

// Results - Scan Another
scanAnotherButton.addEventListener("click", resetToActionPanel);

// Modal - Save
modalSaveButton.addEventListener("click", handleModalSave);

// Modal - Cancel
modalCancelButton.addEventListener("click", handleModalCancel);

// Modal - Close on overlay click
noMatchModal.addEventListener("click", (e) => {
  if (e.target === noMatchModal || e.target.classList.contains("modal-overlay")) {
    handleModalCancel();
  }
});

// Modal - Close on Escape key
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !noMatchModal.hidden) {
    handleModalCancel();
  }
});

// Cleanup on page unload
window.addEventListener("beforeunload", stopCamera);

// ============ Initialization ============

if (!checkAuth()) {
  // User not authenticated, redirect handled by checkAuth
} else {
  // Start camera if on scan tab
  startCamera().catch(() => null);
}
