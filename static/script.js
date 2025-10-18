async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (!message) return;

    appendMessage("Bạn", message);
    input.value = "";

    showLoadingIcon(true);

    const response = await fetch("/chat", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    });

    const data = await response.json();

    typeResponse("Bot", data.response);

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

    const typingSpan = document.createElement("span");
    typingSpan.setAttribute("id", "typing-text");

    // Tách phần text và phần HTML (sau cùng)
    const parts = message.split(/(<img.*?>|<a.*?<\/a>|<p.*?<\/p>)/gi);
    const textPart = parts[0];
    const htmlParts = parts.slice(1).join("");

    bubble.innerHTML = `<strong>${displayName}:</strong> `;
    bubble.appendChild(typingSpan);
    div.appendChild(bubble);
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;

    let index = 0;
    const interval = setInterval(() => {
        if (index < textPart.length) {
            typingSpan.innerHTML += textPart.charAt(index);
            box.scrollTop = box.scrollHeight;
            index++;
        } else {
            clearInterval(interval);
            if (htmlParts) {
                const temp = document.createElement("div");
                temp.innerHTML = htmlParts;
                const imgs = temp.querySelectorAll("img");

                imgs.forEach(img => {
                    img.classList.add("fade-in");
                    img.onload = () => {
                        img.classList.add("show");
                    };
                });

                bubble.appendChild(temp);
                box.scrollTop = box.scrollHeight;
            }
        }
    }, 10);
}
