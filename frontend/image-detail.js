const API_BASE = "http://127.0.0.1:5000";

// DOM Elements
const statusBanner = document.getElementById("status-banner");
const userNameElement = document.getElementById("user-name");
const logoutButton = document.getElementById("logout-button");

const detailLoading = document.getElementById("detail-loading");
const detailNotFound = document.getElementById("detail-not-found");
const detailLayout = document.getElementById("detail-layout");

const heroImage = document.getElementById("detail-hero-image");
const categoryBadge = document.getElementById("detail-category-badge");
const objectNameEl = document.getElementById("detail-object-name");

const descriptionStatic = document.getElementById("detail-description-static");
const descriptionInput = document.getElementById("detail-description-input");
const categoryStatic = document.getElementById("detail-category-static");
const categoryInput = document.getElementById("detail-category-input");
const tagsStatic = document.getElementById("detail-tags-static");
const tagsInput = document.getElementById("detail-tags-input");
const tagsHint = document.getElementById("detail-tags-hint");
const colorStatic = document.getElementById("detail-color-static");
const colorSwatch = document.getElementById("detail-color-swatch");
const colorName = document.getElementById("detail-color-name");
const colorInput = document.getElementById("detail-color-input");

const filenameEl = document.getElementById("detail-filename");
const createdAtEl = document.getElementById("detail-created-at");
const metadataPanel = document.getElementById("detail-metadata-panel");

const editToggleButton = document.getElementById("edit-toggle-button");
const saveButton = document.getElementById("save-button");
const cancelEditButton = document.getElementById("cancel-edit-button");

// Unknown face elements
const unknownFaceBanner = document.getElementById("unknown-face-banner");
const descriptionPrompt = document.getElementById("description-prompt");
const unknownDescriptionInput = document.getElementById("unknown-description-input");
const saveToDbButton = document.getElementById("save-to-db-button");

// Similar images elements
const similarSection = document.getElementById("detail-similar-section");
const similarGrid = document.getElementById("detail-similar-grid");

// State
let currentImage = null;
let isEditing = false;
let isUnknownFace = false; // whether the current detail is for an unsaved/unknown face
let currentResultData = null; // full result data from sessionStorage

// ============ Utility Functions ============

function showStatus(message, type = "info") {
  statusBanner.textContent = message;
  statusBanner.className = `status-banner is-visible ${type === "error" ? "is-error" : ""} ${type === "success" ? "is-success" : ""}`;
}

function clearStatus() {
  statusBanner.textContent = "";
  statusBanner.className = "status-banner";
}

function getImageIdFromUrl() {
  // Expected path: /image/<image_id>
  const parts = window.location.pathname.split("/").filter(Boolean);
  const idx = parts.indexOf("image");
  if (idx === -1 || !parts[idx + 1]) return null;
  return decodeURIComponent(parts[idx + 1]);
}

function formatDate(isoString) {
  if (!isoString) return "Unknown";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  const options = {
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  };
  return date.toLocaleString("en-US", options);
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

// ============ Rendering ============

// Extract a hex color (#rgb or #rrggbb) from a color string, if present
function extractHex(colorString) {
  if (!colorString) return null;
  const match = colorString.match(/#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/);
  return match ? match[0] : null;
}

function renderColorStatic(colorString) {
  const value = (colorString || "").trim();
  if (!value) {
    colorName.textContent = "Not specified";
    colorSwatch.style.background = "var(--line)";
    return;
  }

  const hex = extractHex(value);
  // Display name = the string without the hex portion, falling back to the raw value
  const label = value.replace(/#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/, "").trim() || value;
  colorName.textContent = label;
  colorSwatch.style.background = hex || "var(--line)";
}

function renderTagsStatic(tags) {
  tagsStatic.innerHTML = "";
  if (tags && tags.length > 0) {
    tags.forEach((tag) => {
      const tagElement = document.createElement("span");
      tagElement.className = "tag";
      tagElement.textContent = tag;
      tagsStatic.appendChild(tagElement);
    });
  } else {
    const noTags = document.createElement("span");
    noTags.className = "tag";
    noTags.textContent = "no tags";
    noTags.style.opacity = "0.5";
    tagsStatic.appendChild(noTags);
  }
}

function renderImage(image) {
  currentImage = image;

  // Prefer the image the user actually captured/uploaded on the dashboard (passed
  // via sessionStorage), falling back to the matched database image.
  let capturedImage = null;
  try {
    capturedImage = sessionStorage.getItem(`capturedImage:${image.image_id}`);
  } catch (e) {
    capturedImage = null;
  }
  heroImage.src = capturedImage || image.image_url || `/api/images/${image.filename}`;
  heroImage.alt = image.object_name || "Image";

  categoryBadge.textContent = image.category || "Uncategorized";
  objectNameEl.textContent = image.object_name || "Unknown Object";

  descriptionStatic.textContent = image.description || "No description available.";
  descriptionInput.value = image.description || "";

  categoryStatic.textContent = image.category || "Uncategorized";
  categoryInput.value = image.category || "";

  renderColorStatic(image.color);
  colorInput.value = image.color || "";

  renderTagsStatic(image.tags);
  tagsInput.value = (image.tags || []).join(", ");

  filenameEl.textContent = image.filename || "Unknown";
  createdAtEl.textContent = formatDate(image.created_at);

  detailLoading.hidden = true;
  detailNotFound.hidden = true;
  detailLayout.hidden = false;
}

/**
 * Render an unknown face result from sessionStorage data.
 * This is called when the image_id is "face_unknown" or similar non-DB IDs.
 */
function renderUnknownFace(resultData, imageId) {
  isUnknownFace = true;
  const obj = resultData.object;

  // Build a pseudo-image object for rendering
  const pseudoImage = {
    image_id: imageId,
    object_name: obj.name || "Unknown Person",
    category: obj.category || "Person",
    tags: obj.tags || [],
    description: obj.description || "No description available.",
    color: obj.color || "",
    filename: "Not saved",
    created_at: new Date().toISOString(),
  };

  renderImage(pseudoImage);

  // Show unknown face specific UI
  unknownFaceBanner.hidden = false;
  descriptionPrompt.hidden = false;
  saveToDbButton.hidden = false;

  // Pre-fill the description prompt with the auto-generated description
  if (obj.description) {
    unknownDescriptionInput.value = obj.description;
  }

  // Hide the edit button and metadata panel (not relevant for unsaved images)
  editToggleButton.hidden = true;
  metadataPanel.hidden = true;

  // Render similar images if available
  if (resultData.similar_images && resultData.similar_images.length > 0) {
    renderSimilarImages(resultData.similar_images);
  }
}

/**
 * Render a matched face profile that doesn't have a database record.
 * Shows the profile info (name, description, tags) normally — WITHOUT
 * the "Unknown Face Detected" banner or description prompt.
 */
function renderMatchedProfileFallback(resultData, imageId) {
  const obj = resultData.object;

  // Build a pseudo-image object for rendering
  const pseudoImage = {
    image_id: imageId,
    object_name: obj.name || "Unknown",
    category: obj.category || "Person",
    tags: obj.tags || [],
    description: obj.description || "No description available.",
    color: obj.color || "",
    filename: "Face Profile",
    created_at: new Date().toISOString(),
  };

  renderImage(pseudoImage);

  // Hide edit button and metadata panel (no DB record to edit)
  editToggleButton.hidden = true;
  metadataPanel.hidden = true;

  // Render similar images if available
  if (resultData.similar_images && resultData.similar_images.length > 0) {
    renderSimilarImages(resultData.similar_images);
  }
}

/**
 * Render similar images grid.
 * Used both for unknown faces (from sessionStorage) and for regular detail pages.
 */
function renderSimilarImages(images) {
  if (!images || images.length === 0) {
    similarSection.hidden = true;
    return;
  }

  similarGrid.innerHTML = "";
  const featuredImages = images.slice(0, 3);

  featuredImages.forEach((img) => {
    const card = document.createElement("div");
    card.className = "image-card";

    // Make cards clickable if they have a valid image_id
    if (img.image_id) {
      card.classList.add("image-card-clickable");
      card.setAttribute("role", "link");
      card.setAttribute("tabindex", "0");
      card.setAttribute("title", "Click to view details");

      card.addEventListener("click", () => {
        window.location.href = `/image/${encodeURIComponent(img.image_id)}`;
      });
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          window.location.href = `/image/${encodeURIComponent(img.image_id)}`;
        }
      });
    }

    // Format similarity score as percentage
    const similarityPercent = img.similarity
      ? Math.round(img.similarity * 100)
      : null;
    const similarityBadge = similarityPercent
      ? `<span class="similarity-badge">${similarityPercent}% similar</span>`
      : "";

    card.innerHTML = `
      <img src="${img.thumbnail || img.url}" 
           alt="${img.title || "Similar image"}" 
           loading="lazy"
           onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22150%22%3E%3Crect fill=%22%23f8f5ef%22 width=%22200%22 height=%22150%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22%23746f67%22 font-family=%22sans-serif%22%3EImage unavailable%3C/text%3E%3C/svg%3E'">
      ${similarityBadge}
      <div class="image-card-info">
        <p class="image-card-title">${img.title || "Similar Image"}</p>
        <p class="image-card-source">${img.source || "Local Database"}</p>
      </div>
      ${img.image_id ? '<div class="image-card-overlay"><span class="image-card-view-label">View Details \u2192</span></div>' : ""}
    `;
    similarGrid.appendChild(card);
  });

  similarSection.hidden = false;
}

function setEditingMode(editing) {
  isEditing = editing;

  descriptionStatic.hidden = editing;
  descriptionInput.hidden = !editing;
  categoryStatic.hidden = editing;
  categoryInput.hidden = !editing;
  colorStatic.hidden = editing;
  colorInput.hidden = !editing;
  tagsStatic.hidden = editing;
  tagsInput.hidden = !editing;
  tagsHint.hidden = !editing;

  editToggleButton.hidden = editing;
  saveButton.hidden = !editing;
  cancelEditButton.hidden = !editing;
}

function resetInputsFromCurrentImage() {
  if (!currentImage) return;
  descriptionInput.value = currentImage.description || "";
  categoryInput.value = currentImage.category || "";
  colorInput.value = currentImage.color || "";
  tagsInput.value = (currentImage.tags || []).join(", ");
}

// ============ API Functions ============

async function loadImageDetail(imageId) {
  detailLoading.hidden = false;
  detailNotFound.hidden = true;
  detailLayout.hidden = true;
  clearStatus();

  // Check if we have sessionStorage data for this image (unknown face or dashboard result)
  let resultData = null;
  try {
    const stored = sessionStorage.getItem(`resultData:${imageId}`);
    if (stored) {
      resultData = JSON.parse(stored);
    }
  } catch (e) {
    resultData = null;
  }

  // If this is an unknown face (no real DB record), render from sessionStorage
  if (imageId === "face_unknown" && resultData) {
    currentResultData = resultData;
    renderUnknownFace(resultData, imageId);
    return;
  }

  // Try to load from the API (normal DB image)
  try {
    const response = await fetch(`${API_BASE}/api/images/detail/${encodeURIComponent(imageId)}`);
    const result = await response.json();

    if (response.status === 404) {
      // If API returns 404 but we have sessionStorage data, use it as fallback
      if (resultData) {
        currentResultData = resultData;
        // Check if this is a truly unknown face (unrecognized) vs a matched
        // face profile that simply doesn't have a database record.
        const isActuallyUnknown = resultData.object &&
          (resultData.object.name === "Unknown Person" ||
           resultData.object.image_id === "face_unknown");

        if (isActuallyUnknown) {
          renderUnknownFace(resultData, imageId);
        } else {
          // Matched face profile — render normally from sessionStorage
          renderMatchedProfileFallback(resultData, imageId);
        }
        return;
      }
      detailLoading.hidden = true;
      detailNotFound.hidden = false;
      return;
    }

    if (!response.ok) {
      throw new Error(result.error || "Unable to load image details.");
    }

    renderImage(result.image);

    // If we have result data from sessionStorage with similar images, show them
    if (resultData && resultData.similar_images) {
      renderSimilarImages(resultData.similar_images);
    }
  } catch (error) {
    detailLoading.hidden = true;
    if (error.message && (error.message.includes("Failed to fetch") || error.message.includes("NetworkError"))) {
      showStatus("Network error. Please check your connection and try again.", "error");
    } else {
      showStatus(error.message || "Unable to load image details.", "error");
    }
  }
}

async function saveChanges() {
  if (!currentImage) return;

  const description = descriptionInput.value.trim();
  const category = categoryInput.value.trim();
  const color = colorInput.value.trim();
  const tags = tagsInput.value
    .split(",")
    .map((t) => t.trim())
    .filter((t) => t.length > 0);

  if (!category) {
    showStatus("Category cannot be empty.", "error");
    categoryInput.focus();
    return;
  }

  saveButton.disabled = true;
  saveButton.textContent = "Saving...";
  clearStatus();

  try {
    const response = await fetch(`${API_BASE}/api/images/detail/${encodeURIComponent(currentImage.image_id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description, category, color, tags }),
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Failed to save changes.");
    }

    renderImage(result.image);
    setEditingMode(false);
    showStatus("Changes saved successfully.", "success");
  } catch (error) {
    if (error.message && (error.message.includes("Failed to fetch") || error.message.includes("NetworkError"))) {
      showStatus("Network error. Please check your connection and try again.", "error");
    } else {
      showStatus(error.message || "Failed to save changes.", "error");
    }
  } finally {
    saveButton.disabled = false;
    saveButton.textContent = "Save Changes";
  }
}

/**
 * Save an unknown face to the database.
 * Collects the user-provided description from the prompt, along with
 * auto-generated tags and category, and sends to save-new-image endpoint.
 */
async function saveUnknownToDatabase() {
  if (!currentImage) return;

  // Get the user-provided description (from the prompt textarea)
  const userDescription = unknownDescriptionInput.value.trim();
  const description = userDescription || currentImage.description || "";

  const objectName = currentImage.object_name || "Unknown Person";
  const category = currentImage.category || "Person";
  const tags = currentImage.tags || ["person"];

  // Get the captured image from sessionStorage
  let capturedImage = null;
  try {
    capturedImage = sessionStorage.getItem(`capturedImage:${currentImage.image_id}`);
  } catch (e) {
    capturedImage = null;
  }

  if (!capturedImage) {
    showStatus("No image data available to save. Please go back and capture again.", "error");
    return;
  }

  saveToDbButton.disabled = true;
  saveToDbButton.textContent = "Saving...";
  clearStatus();

  try {
    const response = await fetch(`${API_BASE}/api/vision/save-new-image`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image: capturedImage,
        object_name: objectName,
        category: category,
        tags: tags,
      }),
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Failed to save image.");
    }

    // Success! Update the page to reflect the saved state
    showStatus(`Successfully saved "${objectName}" to the database!`, "success");

    // Clean up sessionStorage for the old unknown key
    try {
      sessionStorage.removeItem(`capturedImage:${currentImage.image_id}`);
      sessionStorage.removeItem(`resultData:${currentImage.image_id}`);

      // Store the captured image under the new real ID
      if (result.image_id) {
        sessionStorage.setItem(`capturedImage:${result.image_id}`, capturedImage);
      }
    } catch (e) {
      // Ignore sessionStorage errors
    }

    // If the user provided a description, also update it via PUT
    if (description && result.image_id) {
      try {
        await fetch(`${API_BASE}/api/images/detail/${encodeURIComponent(result.image_id)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ description, category, tags }),
        });
      } catch (e) {
        // Non-critical — the image was saved, description update can be retried
      }
    }

    // Navigate to the real detail page for the newly saved image
    if (result.image_id) {
      window.location.href = `/image/${encodeURIComponent(result.image_id)}`;
    }
  } catch (error) {
    if (error.message && (error.message.includes("Failed to fetch") || error.message.includes("NetworkError"))) {
      showStatus("Network error. Please check your connection and try again.", "error");
    } else {
      showStatus(error.message || "Failed to save image.", "error");
    }
  } finally {
    saveToDbButton.disabled = false;
    saveToDbButton.textContent = "Save to Database";
  }
}

// ============ Event Listeners ============

logoutButton.addEventListener("click", logout);

editToggleButton.addEventListener("click", () => {
  setEditingMode(true);
});

cancelEditButton.addEventListener("click", () => {
  resetInputsFromCurrentImage();
  setEditingMode(false);
  clearStatus();
});

saveButton.addEventListener("click", saveChanges);

// Save to Database button (for unknown faces)
if (saveToDbButton) {
  saveToDbButton.addEventListener("click", saveUnknownToDatabase);
}

// ============ Initialization ============

if (!checkAuth()) {
  // User not authenticated, redirect handled by checkAuth
} else {
  const imageId = getImageIdFromUrl();
  if (!imageId) {
    detailLoading.hidden = true;
    detailNotFound.hidden = false;
  } else {
    loadImageDetail(imageId);
  }
}
