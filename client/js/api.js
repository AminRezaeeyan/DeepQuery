const API_BASE = "http://localhost:8000/auth";

async function postData(endpoint, data) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    });

    const result = await res.json();

    if (!res.ok) {
        console.error("API error:", result);
        throw result;
    }

    return result;
}
