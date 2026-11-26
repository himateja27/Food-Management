const form = document.getElementById("register-form");
const errorMessage = document.getElementById("register-error");
const successMessage = document.getElementById("register-success");
const returnLink = document.getElementById("return-to-login");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.textContent = "";
  successMessage.textContent = "";
  const password = document.getElementById("register-password").value;
  const confirmation = document.getElementById("register-confirm").value;
  if (password !== confirmation) {
    errorMessage.textContent = "Passwords do not match.";
    return;
  }
  const submitButton = form.querySelector("button[type=submit]");
  submitButton.disabled = true;
  try {
    const response = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        full_name: document.getElementById("register-name").value.trim(),
        email: document.getElementById("register-email").value.trim(),
        password,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.message || `Registration failed (${response.status})`);
    form.reset();
    successMessage.textContent = `Account created for ${payload.email}. Sign in to continue.`;
    returnLink.href = `/login?email=${encodeURIComponent(payload.email)}`;
    returnLink.classList.remove("hidden");
  } catch (error) {
    errorMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});
