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

/* Chuyển các đoạn markdown-like sang HTML:
   - ![alt](url) -> <img src="url" alt="alt">
   - [text](url) -> <a href="url" target="_blank" rel="noopener">text</a>
   - các URL thô -> <a ...>url</a>
   - nhóm các link vào 1 <p class="links-row"> để CSS canh giữa */
function parseMarkdownLike(input) {
    let s = input || "";

    // 1) nếu backend đã trả HTML thực sự (có <div class=...> hoặc <img>), giữ nguyên
    if (/<\/?[a-z][\s\S]*>/i.test(s)) {
        // nhưng vẫn convert bare URLs inside that HTML for safety
        return convertBareUrls(s);
    }

    // 2) thay các image markdown ![alt](url)
    s = s.replace(/!\[([^\]]*?)\]\(([^)]+?)\)/g, (m, alt, url) => {
        const cleanUrl = url.trim();
        const cleanAlt = escapeHtml(alt || "");
        return `<div class="sanpham-image-wrap"><img src="${escapeAttr(cleanUrl)}" alt="${cleanAlt}" class="fade-in"></div>`;
    });

    // 3) thay các link markdown [text](url)
    // lưu các link vào mảng để gom chung vào 1 <p>
    const links = [];
    s = s.replace(/\[([^\]]+?)\]\(([^)]+?)\)/g, (m, text, url) => {
        links.push({ text: escapeHtml(text), url: escapeAttr(url.trim()) });
        return ""; // remove original
    });

    // 4) tìm các bare URLs còn lại và thêm vào links
    const urlPattern = /https?:\/\/[^\s)]+/g;
    let m;
    while ((m = urlPattern.exec(s)) !== null) {
        links.push({ text: escapeHtml(m[0]), url: escapeAttr(m[0]) });
    }
    // xóa bare urls xuất hiện trong text (đã ghi lại)
    s = s.replace(urlPattern, "");

    // 5) xóa các kí tự tách dòng thừa, số thứ tự "3." ở đầu
    s = s.replace(/^\s*\d+\.\s*/gm, "");
    s = s.trim();

    // 6) kết hợp: nếu có ảnh (class sanpham-image-wrap), đặt links dưới ảnh, canh giữa
    let result = s;
    if (links.length) {
        const linksHtml = links.map(l => `<a href="${l.url}" target="_blank" rel="noopener">${l.text}</a>`).join(' <span class="sep">|</span> ');
        result += `<p class="links-row">${linksHtml}</p>`;
    }

    // nếu không có image nhưng có text chứa tiêu đề + link, bọc tổng thể bằng .sanpham để CSS xử lý
    // kiểm tra có <img> đã được chèn vào result
    if (!/<img/i.test(result)) {
        // nếu result có 2 hay nhiều dòng, convert những dòng đầu làm tiêu đề
        const lines = result.split(/\n+/).map(l => l.trim()).filter(Boolean);
        if (lines.length) {
            const title = escapeHtml(lines.shift());
            const desc = escapeHtml(lines.join(' '));
            result = `<div class="sanpham"><h4>${title}</h4><div class="desc">${desc}</div>${links.length ? `<p class="links-row">${links.map(l=>`<a href="${l.url}" target="_blank" rel="noopener">${l.text}</a>`).join(' <span class="sep">|</span> ')}</p>` : ''}</div>`;
        }
    } else {
        // nếu đã có ảnh, bọc vào .sanpham nếu chưa bọc
        if (!/class=["']?sanpham["']?/i.test(result)) {
            result = `<div class="sanpham">${result}</div>`;
        }
    }

    return result;
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
