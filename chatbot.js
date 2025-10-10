fetch("/chatbot", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: message })
})
.then(response => response.json())
.then(data => {
    messages.innerHTML += `<div class="message"><strong>Bot:</strong> ${data.reply}</div>`;

    // ✅ Show dashboard button when chatbot is done
    if (data.reply.toLowerCase().includes("upload your documents") ||
        data.reply.toLowerCase().includes("head to the dashboard")) {
        document.getElementById("dashboardBtn").style.display = "block";
    }
});