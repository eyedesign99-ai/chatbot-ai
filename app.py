from flask import Flask, request, jsonify, render_template
from Chatbot import query_openai_with_context, query_server  # Dùng lại code bạn đã có

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')

    # Truy vấn FAISS trước
    faiss_results = query_server(user_message)

    # Gửi tới ChatGPT với context
    response = query_openai_with_context(faiss_results or [], user_message)

    return jsonify({'response': response})

if __name__ == '__main__':
    from waitress import serve
    import os
    port = int(os.environ.get("PORT", 10000))
    serve(app, host="0.0.0.0", port=port)


