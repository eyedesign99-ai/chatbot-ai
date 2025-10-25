// script_sse.js

async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (!message) return;

    appendMessage("Bạn", message);
    input.value = "";
    showLoadingIcon(true);

    const url = "https://chatbot-ai-pm0b.onrender.com/chat-stream";

    const evtSource = new EventSourcePolyfill(url, {
        headers: { "Content-Type": "application/json" },
        payload: JSON.stringify({ message }),
        method: "POST"
    });

    const chatBox = document.getElementById("chat-box");
    let currentDiv = document.createElement("div");
    currentDiv.className = "chat-row bot";
    currentDiv.innerHTML = `<div class="chat-bubble bot"><strong>CGI:</strong> <span id="typing-text"></span></div>`;
    chatBox.appendChild(currentDiv);
    const typingSpan = currentDiv.querySelector("#typing-text");

    evtSource.onmessage = (event) => {
        if (event.data === "[DONE]") {
            evtSource.close();
            showLoadingIcon(false);
            return;
        }

        const data = JSON.parse(event.data);

        if (data.token) {
            typingSpan.innerHTML += data.token;
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        if (data.html) {
            const htmlDiv = document.createElement("div");
            htmlDiv.className = "bot-html";
            htmlDiv.innerHTML = data.html;
            chatBox.appendChild(htmlDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        if (data.error) {
            appendMessage("Bot", `⚠️ Lỗi: ${data.error}`);
            showLoadingIcon(false);
            evtSource.close();
        }
    };

    evtSource.onerror = () => {
        appendMessage("Bot", "⚠️ Kết nối bị gián đoạn. Vui lòng thử lại sau.");
        showLoadingIcon(false);
        evtSource.close();
    };
}

function appendMessage(sender, message) {
    const chatBox = document.getElementById("chat-box");
    const div = document.createElement("div");
    div.className = `chat-row ${sender === "Bạn" ? "user" : "bot"}`;
    div.innerHTML = `<div class="chat-bubble ${sender === "Bạn" ? "user" : "bot"}"><strong>${sender}:</strong> ${message}</div>`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// 👇 Sửa phần này
function showLoadingIcon(show) {
    const sendBtn = document.querySelector(".send-btn");
    sendBtn.innerHTML = show
        ? `<img src="/static/icon.png" alt="loading" class="loading-icon">`
        : `<img src="/static/arrow.png" alt="send" width="35" height="35">`;
}
