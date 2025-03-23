/**
 * Authentication functions for GraphSpace
 */

$(document).ready(function () {
  // Check if user is already logged in
  const token = localStorage.getItem("auth_token");
  if (token && window.location.pathname === "/login") {
    // Redirect to home if already logged in
    window.location.href = "/";
  }

  // Toggle between login and register forms
  $("#show-register").on("click", function (e) {
    e.preventDefault();
    $("#register-card").removeClass("d-none");
    $(".card:first").addClass("d-none");
  });

  $("#show-login").on("click", function (e) {
    e.preventDefault();
    $("#register-card").addClass("d-none");
    $(".card:first").removeClass("d-none");
  });

  // Login form submission
  $("#login-form").on("submit", function (e) {
    e.preventDefault();

    const username = $("#username").val();
    const password = $("#password").val();
    const rememberMe = $("#remember-me").is(":checked");

    $("#login-button").html(
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Logging in...'
    );
    $("#login-button").prop("disabled", true);
    $("#login-error").addClass("d-none");

    // Send login request
    $.ajax({
      url: "/api/auth/login",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({
        username: username,
        password: password,
      }),
      success: function (response) {
        if (response.success) {
          // Store token in localStorage
          localStorage.setItem("auth_token", response.token);

          // Store user info if remember me is checked
          if (rememberMe) {
            localStorage.setItem("user", JSON.stringify(response.user));
          } else {
            sessionStorage.setItem("user", JSON.stringify(response.user));
          }

          // Update auth header for future requests
          $.ajaxSetup({
            headers: {
              Authorization: `Bearer ${response.token}`,
            },
          });

          // Redirect to the originally requested page or home
          const redirectUrl = sessionStorage.getItem("redirectUrl") || "/";
          sessionStorage.removeItem("redirectUrl"); // Clear stored URL
          window.location.href = redirectUrl;
        } else {
          showLoginError(response.error || "Login failed");
        }
      },
      error: function (xhr) {
        let errorMessage = "Login failed";
        if (xhr.responseJSON && xhr.responseJSON.error) {
          errorMessage = xhr.responseJSON.error;
        }
        showLoginError(errorMessage);
      },
      complete: function () {
        $("#login-button").html("Login");
        $("#login-button").prop("disabled", false);
      },
    });
  });

  // Register form submission
  $("#register-form").on("submit", function (e) {
    e.preventDefault();

    const username = $("#reg-username").val();
    const password = $("#reg-password").val();
    const confirmPassword = $("#reg-confirm-password").val();

    // Validate passwords match
    if (password !== confirmPassword) {
      $("#register-error").text("Passwords do not match").removeClass("d-none");
      return;
    }

    $("#register-button").html(
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Registering...'
    );
    $("#register-button").prop("disabled", true);
    $("#register-error").addClass("d-none");

    // Send register request
    $.ajax({
      url: "/api/auth/register",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({
        username: username,
        password: password,
      }),
      success: function (response) {
        if (response.success) {
          // Show success message
          $("#register-success").removeClass("d-none");
          $("#register-form")[0].reset();

          // Auto login with the provided token
          localStorage.setItem("auth_token", response.token);
          localStorage.setItem("user", JSON.stringify(response.user));

          // Redirect to the originally requested page or home after a short delay
          setTimeout(function () {
            const redirectUrl = sessionStorage.getItem("redirectUrl") || "/";
            sessionStorage.removeItem("redirectUrl"); // Clear stored URL
            window.location.href = redirectUrl;
          }, 2000);
        } else {
          $("#register-error")
            .text(response.error || "Registration failed")
            .removeClass("d-none");
        }
      },
      error: function (xhr) {
        let errorMessage = "Registration failed";
        if (xhr.responseJSON && xhr.responseJSON.error) {
          errorMessage = xhr.responseJSON.error;
        }
        $("#register-error").text(errorMessage).removeClass("d-none");
      },
      complete: function () {
        $("#register-button").html("Register");
        $("#register-button").prop("disabled", false);
      },
    });
  });

  // Helper function to show login error
  function showLoginError(message) {
    $("#login-error").text(message).removeClass("d-none");
  }
});

// Add logout function to window object so it can be called from anywhere
window.logout = function () {
  localStorage.removeItem("auth_token");
  localStorage.removeItem("user");
  sessionStorage.removeItem("user");
  window.location.href = "/login";
};
