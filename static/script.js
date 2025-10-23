async function sendMessage(){
    const input = document.getElementById("user-input");
    const msg = input.value.trim();
    if(!msg) return;
    appendMessage("Bạn", msg);
    input.value = "";
    setLoading(true);
    try{
        const res = await fetch("https://chatbot-ai-pm0b.onrender.com/chat", {
            method: "POST",
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: msg})
        });
        const data = await res.json();
        typeResponse("Bot", `${data.response||''}${data.hinh_html||''}`);
    }catch(e){
        appendMessage("Bot", "Xin lỗi, có lỗi kết nối.");
    }finally{
        setLoading(false);
    }
}

function appendMessage(sender, message){
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    div.className = "chat-row";
    const isUser = sender === "Bạn";
    const name = isUser ? sender : "CGI";
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble " + (isUser ? "user" : "bot");
    bubble.innerHTML = `<strong>${name}:</strong> ${escapeHtml(message)}`;
    div.appendChild(bubble);
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function setLoading(val){
  const btn = document.querySelector(".send-btn");
  if(val){
    btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 50 50">
      <circle cx="25" cy="25" r="20" stroke="white" stroke-width="4" fill="none" stroke-dasharray="90" stroke-linecap="round">
        <animateTransform attributeName="transform" type="rotate" repeatCount="indefinite" dur="0.8s" values="0 25 25;360 25 25"/>
      </circle>
    </svg>`;
  }else{
    btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="35" height="35" fill="white" viewBox="0 0 24 24">
      <path d="M4 12l1.41 1.41L11 7.83V20h2V7.83l5.59 5.58L20 12l-8-8-8 8z"/>
    </svg>`;
  }
}

function typeResponse(sender, message){
    // loại bỏ các ký hiệu markdown không mong muốn
    message = message
      .replace(/```html|```/gi, "")
      .replace(/\*\*Hình ảnh:\*\*/gi, "")
      .replace(/- \*\*Hình ảnh:\*\*/gi, "")
      .trim();

    const box = document.getElementById("chat-box");
    const row = document.createElement("div");
    row.className = "chat-row";
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble bot";
    bubble.innerHTML = `<strong>CGI:</strong> <span class="typing"></span>`;
    row.appendChild(bubble);
    box.appendChild(row);
    box.scrollTop = box.scrollHeight;

    const idx = message.search(/<div|<img/i);
    const textPart = idx > -1 ? message.substring(0, idx) : message;
    const htmlPart = idx > -1 ? message.substring(idx) : "";

    const span = bubble.querySelector(".typing");
    let i = 0;
    const tick = setInterval(()=>{
        if(i < textPart.length){
            span.textContent += textPart.charAt(i++);
            box.scrollTop = box.scrollHeight;
        } else {
            clearInterval(tick);
            if(htmlPart){
                const temp = document.createElement("div");
                temp.className = "bot-message";
                temp.innerHTML = htmlPart;
                bubble.insertAdjacentElement("afterend", temp);
                box.scrollTop = box.scrollHeight;
            }
        }
    }, 8);
}

function escapeHtml(str){
    if(!str) return "";
    return str.replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; });
}
