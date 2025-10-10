function sendMessage() {
  const input = document.getElementById("userInput").value;
  fetch("/chatbot", {
    method: "POST",
    body: JSON.stringify({ message: input }),
    headers: { "Content-Type": "application/json" }
  })
  .then(res => res.json())
  .then(data => {
    document.getElementById("messages").innerHTML += `<p>User: ${input}</p><p>Bot: ${data.reply}</p>`;
    document.getElementById("userInput").value = "";
  });
}