const form = document.getElementById("login-form");
const errorMessage = document.getElementById("login-error");
const successMessage = document.getElementById("login-success");

const registeredEmail = new URLSearchParams(window.location.search).get("email");
if (registeredEmail) {
  document.getElementById("login-email").value = registeredEmail;
  successMessage.textContent = "Account created. Sign in to continue.";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.textContent = "";
  successMessage.textContent = "";

  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  const credentials = `Basic ${btoa(`${email}:${password}`)}`;
  const submitButton = form.querySelector("button[type=submit]");
  submitButton.disabled = true;

  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      credentials: "same-origin",
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.message || `Sign-in failed (${response.status})`);

    window.location.assign("/?login=success");
  } catch (error) {
    errorMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});
