from flask import Flask, request, jsonify, render_template
import faiss
import numpy as np
import pickle
import openai
import os
import json
from Chatbot import enrich_product_data, system_prompt
from datetime import datetime

# -----------------------------------------------
# CẤU HÌNH API KEY & TẢI FAISS DỮ LIỆU
# -----------------------------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")

BASE_DIR = os.path.dirname(__file__)
FAISS_INDEX_PATH = os.path.join(BASE_DIR, "Vecter_Data", "faiss_index.bin")
METADATA_PATH = os.path.join(BASE_DIR, "Vecter_Data", "metadata.pkl")

# Load FAISS index & metadata
print("🔹 Đang tải dữ liệu FAISS...")
index = faiss.read_index(FAISS_INDEX_PATH)
with open(METADATA_PATH, "rb") as f:
    metadata = pickle.load(f)
print("✅ FAISS sẵn sàng, tổng số vector:", len(metadata))

# -----------------------------------------------
# KHỞI TẠO FLASK APP
# -----------------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "<h2>🚀 Chatbot FAISS + OpenAI đang hoạt động!</h2><p>Dùng endpoint POST /chat để gửi tin nhắn.</p>"

# -----------------------------------------------
# FAISS SEARCH - xử lý tìm kiếm nội bộ
# -----------------------------------------------
def search_faiss(user_query):
    if "tranh" not in user_query.lower():
        query = "Tìm tranh: " + user_query
    else:
        query = user_query

    # Chuyển câu truy vấn thành vector
    response = openai.embeddings.create(
        input=[query],
        model="text-embedding-ada-002"
    )
    query_vector = np.array([response.data[0].embedding]).astype("float32")

    # Tìm các vector tương đồng
    k = min(10, len(metadata))
    D, I = index.search(query_vector, k=k)

    results = []
    for idx, dist in zip(I[0], D[0]):
        if idx != -1:
            item = metadata[idx].copy()
            item["distance"] = float(dist)
            results.append(item)

    return results

# -----------------------------------------------
# API /chat - nhận message từ người dùng
# -----------------------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Không có nội dung tin nhắn."}), 400

    # Tìm kết quả FAISS
    faiss_results = search_faiss(user_message)

    # Chuẩn hóa dữ liệu sản phẩm (hình, link, HTML)
    context_list = enrich_product_data(faiss_results)
    context_text = json.dumps(context_list, ensure_ascii=False, indent=2)

    # Tạo lời nhắc gửi cho OpenAI
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Khách hỏi: {user_message}\n\nDữ liệu sản phẩm:\n{context_text}"}
    ]

    # Gọi OpenAI
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7
    )

    reply = response.choices[0].message.content

    return jsonify({
        "user": user_message,
        "response": reply,
        "results": context_list
    })

# -----------------------------------------------
# KHỞI CHẠY SERVER
# -----------------------------------------------
if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Server khởi động trên cổng {port}")
    serve(app, host="0.0.0.0", port=port)
