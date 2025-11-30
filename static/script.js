function wireEnterToSend() {
    const input = document.getElementById("user-input");
    if (!input) return;
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            sendMessage();
        }
    });
}

async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (!message) return;

    appendMessage("Bạn", message);
    input.value = "";
    showLoadingIcon(true);

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message })
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();
        typeResponse("Bot", data.reply);
    } catch (err) {
        console.error("Send message failed:", err);
        typeResponse("Bot", "Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau.");
    } finally {
        showLoadingIcon(false);
    }
}

function appendMessage(sender, message) {
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    const displayName = sender === "Bot" ? "CGI" : sender;
    const isUser = sender === "Bạn";

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

function renderHtmlInChunks(bubble, htmlString, batchSize = 4) {
    const box = document.getElementById("chat-box");
    const temp = document.createElement("div");
    temp.innerHTML = htmlString;

    const gallery = temp.querySelector(".gallery");
    const prefixNodes = Array.from(temp.children).filter(node => node !== gallery);
    prefixNodes.forEach(node => bubble.appendChild(node));

    if (!gallery) {
        if (box) box.scrollTop = box.scrollHeight;
        return;
    }

    const items = Array.from(gallery.children);
    const galleryShell = document.createElement("div");
    galleryShell.className = "gallery";
    bubble.appendChild(galleryShell);

    const loadBatch = () => {
        if (!items.length) return;

        const batch = items.splice(0, batchSize);
        let pending = 0;

        batch.forEach(item => {
            const imgs = item.querySelectorAll("img");
            pending += imgs.length;

            imgs.forEach(img => {
                img.classList.add("fade-in");
                const markDone = () => {
                    img.classList.add("show");
                    pending -= 1;
                    if (pending === 0) {
                        if (box) box.scrollTop = box.scrollHeight;
                        if (items.length) {
                            setTimeout(loadBatch, 60);
                        }
                    }
                };

                if (img.complete) {
                    markDone();
                } else {
                    img.onload = markDone;
                    img.onerror = markDone;
                }
            });

            galleryShell.appendChild(item);
        });

        if (pending === 0) {
            if (box) box.scrollTop = box.scrollHeight;
            if (items.length) {
                setTimeout(loadBatch, 60);
            }
        }
    };

    loadBatch();
}

function typeResponse(sender, message) {
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    const displayName = sender === "Bot" ? "CGI" : sender;
    const safeMessage = message || "";

    div.classList.add("chat-row");

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble bot";

    const typingSpan = document.createElement("span");
    typingSpan.setAttribute("id", "typing-text");

    // Giữ phần intro gõ chữ từ từ; phần HTML (gallery, ảnh) xuất hiện sau
    const htmlStartIndex = safeMessage.search(/<h[1-6]|<div|<img|<p|<a/i);
    let textPart = htmlStartIndex >= 0 ? safeMessage.slice(0, htmlStartIndex) : safeMessage;
    let htmlParts = htmlStartIndex >= 0 ? safeMessage.slice(htmlStartIndex) : "";

    // Nếu nội dung bắt đầu bằng HTML (vd: <p>Intro...</p><div class="gallery">...), tách đoạn text đầu ra trước
    if (!textPart && htmlParts) {
        const tempExtract = document.createElement("div");
        tempExtract.innerHTML = htmlParts;
        const firstP = tempExtract.querySelector("p");
        if (firstP && firstP.innerText.trim()) {
            textPart = firstP.innerText.trim();
            firstP.remove();
            htmlParts = tempExtract.innerHTML;
        } else if (tempExtract.textContent.trim()) {
            textPart = tempExtract.textContent.trim();
            htmlParts = "";
        }
    }

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
                renderHtmlInChunks(bubble, htmlParts, 4);
            }
        }
    }, 10);
}

document.addEventListener("DOMContentLoaded", wireEnterToSend);
