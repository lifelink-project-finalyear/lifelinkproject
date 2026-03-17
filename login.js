// ===============================
// LOGIN FUNCTION
// ===============================
async function loginUser() {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value.trim();

  // Basic validation
  if (!email || !password) {
    alert("Please enter email and password");
    return;
  }

  try {
    const response = await fetch("http://localhost:3000/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        email: email,
        password: password
      })
    });

    const data = await response.json();

    if (!response.ok) {
      alert(data.message || "Login failed");
      return;
    }

    // ✅ Save logged-in user email in browser
    localStorage.setItem("userEmail", email);

    alert("Login successful");

    // ✅ Redirect to symptoms page
    window.location.href = "symptoms.html";

  } catch (error) {
    console.error("Login Error:", error);
    alert("Server connection failed");
  }
}

// ===============================
// LOGOUT FUNCTION (OPTIONAL)
// ===============================
function logoutUser() {
  localStorage.removeItem("userEmail");
  window.location.href = "login.html";
}
