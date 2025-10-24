# Chatbot_Full_SSE_Lite.py
from flask import Flask, request, Response, jsonify
from openai import OpenAI
import os, json, requests
from datetime import datetime

# --- Khởi tạo Flask và OpenAI ---
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("✅ Chatbot SSE Lite khởi tạo thành công!")

# --- Ghi log siêu nhẹ ---
def log_chat(user_input, bot_reply):
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.txt")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 {user_input}\n🤖 {bot_reply}\n---\n")

# --- Truy vấn FAISS (server cục bộ hoặc cloud) ---
def query_server(user_input):
    try:
        res = requests.post("http://127.0.0.1:5000/search", json={"query": user_input}, timeout=5)
        return res.json() if res.status_code == 200 else []
    except Exception as e:
        print("❌ Không kết nối được FAISS:", e)
        return []

# --- Thêm HTML hiển thị sản phẩm ---
def enrich_product_data(context_list):
    for item in context_list:
        if isinstance(item, dict) and "hình_ảnh" in item and "id" in item:
            img_path = item["hình_ảnh"]
            sp_id = item["id"]
            item["hinh_html"] = f"""
                <div class='sanpham'>
                    <img src='https://cgi.vn/image/{img_path}' class='bot-image'>
                    <p>
                        <a href='https://cgi.vn/ar/{sp_id}' target='_blank'>Xem AR</a> |
                        <a href='https://cgi.vn/san-pham/{sp_id}' target='_blank'>Chi tiết</a>
                    </p>
                </div>
            """
    return context_list

# --- Route SSE (stream phản hồi) ---
@app.route("/chat-stream", methods=["POST"])
def chat_stream():
    user_input = request.json.get("message", "")
    if not user_input:
        return jsonify({"error": "Thiếu nội dung"}), 400

    # Lấy dữ liệu FAISS nếu có
    context = enrich_product_data(query_server(user_input))
    context_text = json.dumps(context, ensure_ascii=False)

    # Prompt ngắn gọn, chuyên tư vấn tranh
    messages = [
        {"role": "system", "content": (
            "Bạn là nhân viên tư vấn tranh chuyên nghiệp. "
            "Luôn trả lời thân thiện, tự nhiên, và hiển thị sản phẩm bằng HTML nếu có.")},
        {"role": "user", "content": f"Khách hỏi: {user_input}\n\nDữ liệu:\n{context_text}"}
    ]

    def stream():
        reply_accum = ""
        try:
            # Stream token từng phần
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                stream=True
            )

            for chunk in response:
                if hasattr(chunk, "choices") and chunk.choices[0].delta.get("content"):
                    content = chunk.choices[0].delta["content"]
                    reply_accum += content
                    yield f"data: {json.dumps({'token': content})}\n\n"

            # Sau khi trả lời xong → gửi HTML sản phẩm (nếu có)
            html_part = "".join([item.get("hinh_html", "") for item in context])
            if html_part:
                yield f"data: {json.dumps({'html': html_part})}\n\n"

            # Ghi log (siêu nhẹ)
            log_chat(user_input, reply_accum)
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream(), mimetype="text/event-stream")

# --- Kiểm tra trạng thái ---
@app.route("/")
def home():
    return jsonify({"status": "🤖 Chatbot SSE Lite đang hoạt động!"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
