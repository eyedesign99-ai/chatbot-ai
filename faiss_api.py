from flask import Flask, request, jsonify
import faiss
import numpy as np
import pickle
import openai
import os

BASE_DIR = os.path.dirname(__file__)
FAISS_INDEX_PATH = os.path.join(BASE_DIR, "Vecter_Data", "faiss_index.bin")
METADATA_PATH = os.path.join(BASE_DIR, "Vecter_Data", "metadata.pkl")

# Load FAISS index & metadata
index = faiss.read_index(FAISS_INDEX_PATH)
with open(METADATA_PATH, "rb") as f:
    metadata = pickle.load(f)

# Cấu hình API Key của OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    user_query = data["query"].strip()

    # 🔹 Nếu truy vấn không chứa từ "tranh", thêm tiền tố để làm rõ ngữ nghĩa
    if "tranh" not in user_query.lower():
        query = "Tìm tranh: " + user_query
    else:
        query = user_query

    # Chuyển truy vấn thành vector
    response = openai.embeddings.create(
        input=[query],
        model="text-embedding-ada-002"
    )
    query_vector = np.array([response.data[0].embedding]).astype("float32")

    # Số kết quả tối đa cần lấy
    k = min(10, len(metadata))
    D, I = index.search(query_vector, k=k)

    # Trả về kết quả kèm độ tương đồng (distance)
    results = []
    for idx, dist in zip(I[0], D[0]):
        if idx != -1:
            item = metadata[idx].copy()
            item["distance"] = float(dist)  # Càng nhỏ càng giống
            results.append(item)

    return jsonify(results)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
