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

const editToggleButton = document.getElementById("edit-toggle-button");
const saveButton = document.getElementById("save-button");
const cancelEditButton = document.getElementById("cancel-edit-button");

// State
let currentImage = null;
let isEditing = false;

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

  try {
    const response = await fetch(`${API_BASE}/api/images/detail/${encodeURIComponent(imageId)}`);
    const result = await response.json();

    if (response.status === 404) {
      detailLoading.hidden = true;
      detailNotFound.hidden = false;
      return;
    }

    if (!response.ok) {
      throw new Error(result.error || "Unable to load image details.");
    }

    renderImage(result.image);
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
