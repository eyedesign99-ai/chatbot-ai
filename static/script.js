async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (!message) return;

    appendMessage("Bạn", message);
    input.value = "";

    showLoadingIcon(true);

    const response = await fetch("https://chatbot-ai-pm0b.onrender.com/chat", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    });

    const data = await response.json();

    typeResponse("Bot", `${data.response || ''}${data.hinh_html || ''}`);

    showLoadingIcon(false);
}

function appendMessage(sender, message) {
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    let displayName = (sender === "Bot") ? "CGI" : sender;
    let isUser = (sender === "Bạn");
    div.classList.add("chat-row");
    div.innerHTML = isUser
        ? `<div class="chat-bubble user"><strong>${displayName}:</strong> ${message}</div>`
        : `<div class="chat-bubble bot"><strong>${displayName}:</strong> ${message}</div>`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function showLoadingIcon(show) {
    const sendBtn = document.querySelector(".send-btn");
    sendBtn.innerHTML = show
        ? `<img src="/static/icon.png" alt="loading" class="loading-icon">`
        : `<svg xmlns="http://www.w3.org/2000/svg" width="35" height="35" fill="white" viewBox="0 0 24 24">
                <path d="M4 12l1.41 1.41L11 7.83V20h2V7.83l5.59 5.58L20 12l-8-8-8 8z"/>
           </svg>`;
}

function typeResponse(sender, message) {
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    let displayName = (sender === "Bot") ? "CGI" : sender;
    div.classList.add("chat-row");

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble bot";

    // ✅ Phân tách phần text mô tả và phần HTML sản phẩm
    const splitIndex = message.indexOf("<div");
    const textPart = splitIndex > -1 ? message.substring(0, splitIndex) : message;
    const htmlPart = splitIndex > -1 ? message.substring(splitIndex) : "";

    // ✅ Hiển thị phần text trước
    bubble.innerHTML = `<strong>${displayName}:</strong> <span id="typing-text"></span>`;
    div.appendChild(bubble);
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;

    let i = 0;
    const typingSpan = bubble.querySelector("#typing-text");

    const interval = setInterval(() => {
        if (i < textPart.length) {
            typingSpan.innerHTML += textPart.charAt(i);
            i++;
        } else {
            clearInterval(interval);
            // ✅ Chèn phần HTML (sản phẩm)
            if (htmlPart) {
                const tempDiv = document.createElement("div");
                tempDiv.innerHTML = htmlPart;
                bubble.insertAdjacentElement("afterend", tempDiv); // ✅ đặt ngoài bubble
                box.scrollTop = box.scrollHeight;
            }
        }
    }, 10);
}

