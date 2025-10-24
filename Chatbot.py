# Chatbot_SSE.py
from flask import Flask, request, Response, jsonify
from openai import OpenAI
import os, json, requests, re

# --- Cấu hình Flask ---
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Truy vấn dữ liệu từ FAISS ---
def query_server(user_input):
    try:
        res = requests.post("http://127.0.0.1:5000/search", json={"query": user_input})
        return res.json() if res.status_code == 200 else []
    except:
        return []

# --- Bổ sung HTML cho sản phẩm ---
def enrich_product_data(context_list):
    for item in context_list:
        if isinstance(item, dict) and "hình_ảnh" in item and "id" in item:
            img_path = item["hình_ảnh"]
            sp_id = item["id"]
            item["hinh_html"] = f"""
                <div class='sanpham'>
                    <img src='https://cgi.vn/image/{img_path}' class="product-image">
                    <p>
                        <a href='https://cgi.vn/ar/{sp_id}' target='_blank'>Xem AR</a> |
                        <a href='https://cgi.vn/san-pham/{sp_id}' target='_blank'>Chi tiết</a>
                    </p>
                </div>
            """
    return context_list

# --- Gửi phản hồi dạng SSE ---
@app.route("/chat-stream", methods=["POST"])
def chat_stream():
    user_input = request.json.get("message", "")
    if not user_input:
        return jsonify({"error": "Missing message"}), 400

    # Lấy dữ liệu ngữ cảnh từ FAISS
    context = enrich_product_data(query_server(user_input))
    context_text = json.dumps(context, ensure_ascii=False)

    messages = [
        {"role": "system", "content": "Bạn là chuyên viên tư vấn tranh chuyên nghiệp, hãy trả lời tự nhiên và chèn HTML sản phẩm khi phù hợp."},
        {"role": "user", "content": f"Khách hỏi: {user_input}\n\nDữ liệu:\n{context_text}"}
    ]

    def stream():
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                stream=True
            )

            # Gửi từng token ra frontend (typing effect)
            for chunk in response:
                if hasattr(chunk, "choices") and chunk.choices[0].delta.get("content"):
                    content = chunk.choices[0].delta["content"]
                    yield f"data: {json.dumps({'token': content})}\n\n"

            # Gửi phần HTML sản phẩm (nếu có)
            html_part = "".join([item.get("hinh_html", "") for item in context])
            if html_part:
                yield f"data: {json.dumps({'html': html_part})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream(), mimetype="text/event-stream")

# --- Kiểm tra trạng thái ---
@app.route("/")
def index():
    return jsonify({"status": "🤖 Chatbot SSE đang hoạt động"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
