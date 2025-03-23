/**
 * GraphSpace v2 Main JavaScript File
 */

// Initialize on document ready
$(document).ready(function () {
  console.log("GraphSpace v2 initialized");

  // Initialize tooltips
  const tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
  );
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // Initialize popovers
  const popoverTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="popover"]')
  );
  popoverTriggerList.map(function (popoverTriggerEl) {
    return new bootstrap.Popover(popoverTriggerEl);
  });

  // Add auth token to all AJAX requests
  const token = localStorage.getItem("auth_token");

  // Global AJAX setup
  $.ajaxSetup({
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      // Authentication disabled for hackathon
      // Authorization: token ? `Bearer ${token}` : null,
    },
    error: function (xhr, status, error) {
      if (xhr.status === 401) {
        // Unauthorized - but don't redirect for hackathon
        console.error(
          "Authentication error, but continuing anyway for hackathon"
        );
      } else if (xhr.status === 404) {
        console.error("Resource not found:", error);
      } else if (xhr.status >= 500) {
        console.error("Server error:", error);
        // Show error toast if available
        if (typeof showToast === "function") {
          showToast(
            "error",
            "Server Error",
            "An unexpected error occurred. Please try again later."
          );
        }
      }
    },
  });

  // Add logout functionality to navbar if present
  $("#logout-button").on("click", function (e) {
    e.preventDefault();
    if (typeof window.logout === "function") {
      window.logout();
    } else {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("user");
      sessionStorage.removeItem("user");
      window.location.href = "/login";
    }
  });

  // Format dates with the time ago format
  formatTimeAgo();
});

/**
 * Format dates with the time ago format
 */
function formatTimeAgo() {
  $(".timeago").each(function () {
    const dateStr = $(this).attr("datetime");
    if (!dateStr) return;

    const date = new Date(dateStr);
    $(this).text(getTimeAgo(date));
  });
}

/**
 * Get a human-readable string of how long ago a date was
 *
 * @param {Date} date - The date to check
 * @returns {string} Human-readable string
 */
function getTimeAgo(date) {
  const now = new Date();
  const diffSeconds = Math.floor((now - date) / 1000);

  if (diffSeconds < 60) {
    return "just now";
  } else if (diffSeconds < 3600) {
    const minutes = Math.floor(diffSeconds / 60);
    return `${minutes} minute${minutes > 1 ? "s" : ""} ago`;
  } else if (diffSeconds < 86400) {
    const hours = Math.floor(diffSeconds / 3600);
    return `${hours} hour${hours > 1 ? "s" : ""} ago`;
  } else if (diffSeconds < 2592000) {
    // 30 days
    const days = Math.floor(diffSeconds / 86400);
    return `${days} day${days > 1 ? "s" : ""} ago`;
  } else if (diffSeconds < 31536000) {
    // 365 days
    const months = Math.floor(diffSeconds / 2592000);
    return `${months} month${months > 1 ? "s" : ""} ago`;
  } else {
    const years = Math.floor(diffSeconds / 31536000);
    return `${years} year${years > 1 ? "s" : ""} ago`;
  }
}

/**
 * Show a toast notification
 *
 * @param {string} type - Type of toast (success, error, warning, info)
 * @param {string} title - Toast title
 * @param {string} message - Toast message
 */
function showToast(type, title, message) {
  // Check if toast container exists, if not create it
  let toastContainer = document.getElementById("toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toast-container";
    toastContainer.className = "position-fixed bottom-0 end-0 p-3";
    document.body.appendChild(toastContainer);
  }

  // Set toast color based on type
  let bgClass = "bg-primary";
  let icon = "info-circle";

  switch (type) {
    case "success":
      bgClass = "bg-success";
      icon = "check-circle";
      break;
    case "error":
      bgClass = "bg-danger";
      icon = "exclamation-circle";
      break;
    case "warning":
      bgClass = "bg-warning";
      icon = "exclamation-triangle";
      break;
    case "info":
      bgClass = "bg-info";
      icon = "info-circle";
      break;
  }

  // Create toast element
  const toastId = "toast-" + Date.now();
  const toastHtml = `
        <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header ${bgClass} text-white">
                <i class="fas fa-${icon} me-2"></i>
                <strong class="me-auto">${title}</strong>
                <small>Now</small>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;

  // Append toast to container
  toastContainer.innerHTML += toastHtml;

  // Initialize and show toast
  const toastElement = document.getElementById(toastId);
  const toast = new bootstrap.Toast(toastElement, {
    autohide: true,
    delay: 5000,
  });
  toast.show();

  // Remove toast from DOM after it's hidden
  toastElement.addEventListener("hidden.bs.toast", function () {
    toastElement.remove();
  });
}

/**
 * Format a date string to a localized format
 *
 * @param {string} dateStr - ISO date string
 * @param {boolean} includeTime - Whether to include time in the format
 * @returns {string} Formatted date string
 */
function formatDate(dateStr, includeTime = false) {
  if (!dateStr) return "";

  const date = new Date(dateStr);

  if (includeTime) {
    return date.toLocaleString();
  } else {
    return date.toLocaleDateString();
  }
}

/**
 * Check if a string is a valid URL
 *
 * @param {string} str - String to check
 * @returns {boolean} Whether the string is a valid URL
 */
function isValidUrl(str) {
  try {
    new URL(str);
    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Truncate a string to a specified length
 *
 * @param {string} str - String to truncate
 * @param {number} length - Maximum length
 * @returns {string} Truncated string
 */
function truncateString(str, length = 100) {
  if (!str) return "";
  if (str.length <= length) return str;
  return str.substring(0, length) + "...";
}

/**
 * Handle file upload with preview
 *
 * @param {string} inputId - File input element ID
 * @param {string} previewId - Preview element ID
 * @param {function} callback - Callback function after successful upload
 */
function handleFileUpload(inputId, previewId, callback) {
  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);

  if (!input || !preview) return;

  input.addEventListener("change", function () {
    const file = this.files[0];
    if (!file) return;

    // Display file information
    preview.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-file me-2"></i>
                <strong>${file.name}</strong> (${formatFileSize(file.size)})
            </div>
        `;

    if (typeof callback === "function") {
      callback(file);
    }
  });
}

/**
 * Format file size in a human-readable format
 *
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted file size
 */
function formatFileSize(bytes) {
  if (bytes < 1024) {
    return bytes + " B";
  } else if (bytes < 1024 * 1024) {
    return (bytes / 1024).toFixed(1) + " KB";
  } else if (bytes < 1024 * 1024 * 1024) {
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  } else {
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
  }
}
