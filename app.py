from flask import Flask, request, jsonify, render_template
from Chatbot import query_openai_with_context, search_paintings_for_user_query

app = Flask(__name__)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')

    # Tìm dữ liệu sản phẩm trước (FAISS/SQLite)
    faiss_results = search_paintings_for_user_query(user_message)

    # Gửi lên ChatGPT kèm context
    response = query_openai_with_context(faiss_results or [], user_message)

    return jsonify({'response': response})


if __name__ == '__main__':
    app.run(debug=True, port=8501)
