document.getElementById("redirect-form").addEventListener("submit", function (e) {
    e.preventDefault();
    const value = document.getElementById("redirect-input").value.trim();
    if (value) {
        window.location.href = value;
    }
});