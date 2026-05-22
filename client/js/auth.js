function setInvalid(el, invalid) {
    if (invalid) {
        el.classList.add("invalid");
    } else {
        el.classList.remove("invalid");
    }
}

function validateFields(fields) {
    let ok = true;

    fields.forEach((field) => {
        const el = document.getElementById(field);
        if (!el || !el.value.trim()) {
            setInvalid(el, true);
            ok = false;
        } else {
            setInvalid(el, false);
        }
    });

    return ok;
}

function saveAuthData(tokens, user = null) {
    localStorage.setItem("access", tokens.access);
    localStorage.setItem("refresh", tokens.refresh);

    if (user) {
        localStorage.setItem("user_name", user.first_name || "");
        localStorage.setItem("user_last_name", user.last_name || "");
        localStorage.setItem("user_email", user.email || "");
    }

    window.location.href = "main.html";
}

async function handleLogin() {
    const email = document.getElementById("email");
    const password = document.getElementById("password");

    if (!validateFields(["email", "password"])) return;

    try {
        const res = await postData("/login/", {
            email: email.value.trim(),
            password: password.value
        });

        if (res.tokens) {
            saveAuthData(res.tokens);
        } else {
            alert(res.message || "Login failed");
        }
    } catch (error) {
        alert("Login request failed");
    }
}

async function handleRegister() {
    const fields = ["first_name", "last_name", "email", "password"];

    if (!validateFields(fields)) return;

    try {
        const res = await postData("/register/", {
            first_name: document.getElementById("first_name").value.trim(),
            last_name: document.getElementById("last_name").value.trim(),
            email: document.getElementById("email").value.trim(),
            password: document.getElementById("password").value
        });

        if (res.tokens) {
            saveAuthData(res.tokens, {
                first_name: document.getElementById("first_name").value.trim(),
                last_name: document.getElementById("last_name").value.trim(),
                email: document.getElementById("email").value.trim()
            });
        } else {
            alert(res.message || "Registration failed");
        }
    } catch (error) {
        alert("Register request failed");
    }
}

async function handleGoogleLogin(response) {
    try {
        const res = await postData("/google/", {
            token: response.credential
        });

        if (res.tokens) {
            saveAuthData(res.tokens);
        } else {
            alert(res.message || "Google login failed");
        }
    } catch (error) {
        alert("Google login request failed");
    }
}
