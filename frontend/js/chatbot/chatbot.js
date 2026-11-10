(function () {
  const API_URL = "/api/chatbot";

  // Build the UI
  const root = document.createElement("div");
  root.innerHTML = `
    <button id="cb-button" aria-label="Open chat">💬</button>
    <div id="cb-window">
      <div id="cb-header">Shopping Assistant</div>
      <div id="cb-log"></div>
      <form id="cb-form">
        <input id="cb-input" placeholder="Ask about products..." autocomplete="off" />
        <button id="cb-send" type="submit">Send</button>
      </form>
    </div>`;
  document.body.appendChild(root);

  const btn = document.getElementById("cb-button");
  const win = document.getElementById("cb-window");
  const log = document.getElementById("cb-log");
  const form = document.getElementById("cb-form");
  const input = document.getElementById("cb-input");
  btn.addEventListener("click", () => {
    win.classList.toggle("open");
    if (win.classList.contains("open") && !log.children.length) {
      addMsg("bot", "Hi! I can help you find products or check your order. What do you need?");
    }
    input.focus();
  });

  function addMsg(who, text) {
    const div = document.createElement("div");
    div.className = "cb-msg " + (who === "user" ? "cb-user" : "cb-bot");
    div.textContent = text; // textContent prevents HTML injection
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  form.addEventListener("submit", async (e) => {
e.preventDefault();
const text = input.value.trim();
if (!text) return;
input.value = "";
addMsg("user", text);

const botDiv = addMsg("bot", "…");
const sendButton = document.getElementById("cb-send");
sendButton.disabled = true;

try {
  const token = localStorage.getItem("haul_token");   
  const res = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" ,
    ...(token ? { "authorization": `Bearer ${token}` } : {})},
    body: JSON.stringify({ message: text }),
  });

  if (!res.ok) {
    throw new Error(`Chat request failed (${res.status})`);
  }

  const data = await res.json();
  const reply = typeof data.output === "string" ? data.output.trim() : "";
  if (!reply) throw new Error("The chat service returned an empty reply.");
  botDiv.textContent = reply;
} catch (err) {
  console.error("Chat request failed:", err);
  botDiv.textContent = "Sorry, I couldn't load a reply. Please try again.";
} finally {
  sendButton.disabled = false;
}
  });
})();