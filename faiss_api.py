from flask import Flask, request, jsonify
import faiss
import numpy as np
import pickle
import os
import openai

FAISS_INDEX_PATH = "F:/AI/Chatbot/Vecter_Data/faiss_index.bin"
METADATA_PATH = "F:/AI/Chatbot/Vecter_Data/metadata.pkl"

# Load FAISS index & metadata
index = faiss.read_index(FAISS_INDEX_PATH)
with open(METADATA_PATH, "rb") as f:
    metadata = pickle.load(f)

# Configure OpenAI API key from environment
openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("Missing environment variable OPENAI_API_KEY")

app = Flask(__name__)

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    user_query = data["query"].strip()

    # If query does not contain 'tranh', prepend to clarify intent
    if "tranh" not in user_query.lower():
        query = "Tim tranh: " + user_query
    else:
        query = user_query

    # Convert query to embedding vector
    response = openai.embeddings.create(
        input=[query],
        model="text-embedding-ada-002"
    )
    query_vector = np.array([response.data[0].embedding]).astype("float32")

    # Number of results to retrieve
    k = min(10, len(metadata))
    D, I = index.search(query_vector, k=k)

    # Return results with distance score
    results = []
    for idx, dist in zip(I[0], D[0]):
        if idx != -1:
            item = metadata[idx].copy()
            item["distance"] = float(dist)  # smaller distance = more similar
            results.append(item)

    return jsonify(results)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
