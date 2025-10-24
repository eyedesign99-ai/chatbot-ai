async function sendMessage() {
    const input = document.getElementById("user-input");
    const message = input.value.trim();
    if (!message) return;

    appendMessage("Bạn", message);
    input.value = "";

    showLoadingIcon(true);

    try {
        const response = await fetch("https://chatbot-ai-pm0b.onrender.com/chat", {
            method: "POST",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        const data = await response.json();
        typeResponse("Bot", `${data.response || ''}${data.hinh_html || ''}`);
    } catch (err) {
        appendMessage("Bot", "Lỗi kết nối. Vui lòng thử lại.");
        console.error(err);
    } finally {
        showLoadingIcon(false);
    }
}

function appendMessage(sender, message) {
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    let displayName = (sender === "Bot") ? "CGI" : sender;
    let isUser = (sender === "Bạn");
    div.classList.add("chat-row");
    div.innerHTML = isUser
        ? `<div class="chat-bubble user"><strong>${displayName}:</strong> ${escapeHtml(message)}</div>`
        : `<div class="chat-bubble bot"><strong>${displayName}:</strong> ${escapeHtml(message)}</div>`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

/* small helper to escape raw text when we don't intend to parse HTML */
function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
}

function showLoadingIcon(show) {
    const sendBtn = document.querySelector(".send-btn");
    sendBtn.innerHTML = show
        ? `<img src="/static/icon.png" alt="loading" class="loading-icon">`
        : `<svg xmlns="http://www.w3.org/2000/svg" width="35" height="35" fill="white" viewBox="0 0 24 24">
                <path d="M4 12l1.41 1.41L11 7.83V20h2V7.83l5.59 5.58L20 12l-8-8-8 8z"/>
           </svg>`;
}

/* CHÍNH: show text typing + parse markdown-like htmlPart thành proper HTML */
function typeResponse(sender, message) {
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    let displayName = (sender === "Bot") ? "CGI" : sender;
    div.classList.add("chat-row");

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble bot";

    // tách phần text và phần html nếu backend gửi cùng
    const splitIndex = message.search(/<div|<img|!\[|\[http|http[s]?:\/\/|^\s*\d+\.\s*/i);
    const textPart = splitIndex > -1 ? message.substring(0, splitIndex) : message;
    const restPart = splitIndex > -1 ? message.substring(splitIndex) : "";

    bubble.innerHTML = `<strong>${displayName}:</strong> <span id="typing-text"></span>`;
    div.appendChild(bubble);
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;

    // typing effect cho phần text (nhanh)
    let i = 0;
    const typingSpan = bubble.querySelector("#typing-text");
    const interval = setInterval(() => {
        if (i < textPart.length) {
            typingSpan.innerHTML += escapeHtml(textPart.charAt(i));
            i++;
        } else {
            clearInterval(interval);
            // sau khi gõ xong, nếu có phần rest (markdown/image/links), parse và chèn
            if (restPart && restPart.trim().length > 0) {
                const parsed = parseMarkdownLike(restPart);
                // tạo container .bot-message (CSS đã set là trong suốt)
                const tempDiv = document.createElement("div");
                tempDiv.classList.add("bot-message");
                tempDiv.innerHTML = parsed;
                // chèn sau div hiện tại (để giữ thứ tự)
                div.insertAdjacentElement("afterend", tempDiv);
                box.scrollTop = box.scrollHeight;
            }
        }
    }, 8);
}

/* --- Thay thế toàn bộ hàm parseMarkdownLike bằng version này --- */
function parseMarkdownLike(input) {
    const s = input || "";

    // Nếu backend đã trả HTML thực sự thì giữ nguyên (nhưng convert bare URLs bên trong)
    if (/<\/?[a-z][\s\S]*>/i.test(s)) {
        return convertBareUrls(s);
    }

    // Regex: image markdown | link markdown | bare url
    const regex = /!\[([^\]]*?)\]\(([^)]+?)\)|\[((?:[^\]]+?))\]\(([^)]+?)\)|(https?:\/\/[^\s)]+)/g;

    const tokens = [];
    let lastIndex = 0;
    let m;
    while ((m = regex.exec(s)) !== null) {
        // text giữa các match
        if (m.index > lastIndex) {
            tokens.push({ type: "text", text: s.slice(lastIndex, m.index) });
        }

        if (m[1] !== undefined) {
            // image: m[1]=alt, m[2]=url
            tokens.push({ type: "image", alt: m[1], url: m[2] });
        } else if (m[3] !== undefined) {
            // link: m[3]=text, m[4]=url
            tokens.push({ type: "link", text: m[3], url: m[4] });
        } else if (m[5] !== undefined) {
            // bare url
            tokens.push({ type: "url", url: m[5] });
        }
        lastIndex = regex.lastIndex;
    }
    // phần text cuối
    if (lastIndex < s.length) {
        tokens.push({ type: "text", text: s.slice(lastIndex) });
    }

    // gom dữ liệu: ảnh, link, text
    const images = tokens.filter(t => t.type === "image");
    const links = tokens.filter(t => t.type === "link" || t.type === "url");
    const textPieces = tokens
        .filter(t => t.type === "text")
        .map(t => t.text.replace(/\r\n|\r/g, "\n"))
        .join("\n")
        .split("\n")
        .map(l => l.trim())
        .filter(Boolean);

    // lấy title (dòng đầu) và mô tả (còn lại)
    const title = textPieces.length ? textPieces.shift() : "";
    const desc = textPieces.join(" ");

    // build HTML
    let inner = "";

    // nếu có ảnh -> tạo block ảnh (giữ thứ tự: tất cả ảnh xuất theo thứ tự)
    if (images.length) {
        inner += images.map(img => {
            const url = escapeAttr(img.url.trim());
            const alt = escapeHtml(img.alt || "");
            return `<div class="sanpham-image-wrap"><img src="${url}" alt="${alt}" class="fade-in"></div>`;
        }).join("");
    }

    // nếu không có ảnh, sẽ hiển thị title/desc bên trong .sanpham
    if (!/<img/i.test(inner)) {
        inner = `<h4>${escapeHtml(title)}</h4><div class="desc">${escapeHtml(desc)}</div>`;
    }

    // build links row (giữ toàn bộ link markdown và bare urls theo thứ tự xuất hiện)
    let linksHtml = "";
    if (links.length) {
        linksHtml = links.map(l => {
            const url = escapeAttr((l.url || "").trim());
            const text = escapeHtml(l.text || l.url);
            return `<a href="${url}" target="_blank" rel="noopener">${text}</a>`;
        }).join(' <span class="sep">|</span> ');
        inner += `<p class="links-row">${linksHtml}</p>`;
    }

    // bọc vào .sanpham
    const result = `<div class="sanpham">${inner}</div>`;
    return result;
}

/* helpers (giữ nguyên từ code trước đó) */
function convertBareUrls(html) {
    return html.replace(/(https?:\/\/[^\s"']+)/g, (m) => {
        const u = escapeAttr(m);
        return `<a href="${u}" target="_blank" rel="noopener">${escapeHtml(m)}</a>`;
    });
}
function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
}
function escapeAttr(s) {
    return String(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/* convert bare URLs inside existing HTML to anchors (simple) */
function convertBareUrls(html) {
    return html.replace(/(https?:\/\/[^\s"']+)/g, (m) => {
        const u = escapeAttr(m);
        return `<a href="${u}" target="_blank" rel="noopener">${escapeHtml(m)}</a>`;
    });
}

/* helpers to safely escape attributes (minimal) */
function escapeAttr(s) {
    return String(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
