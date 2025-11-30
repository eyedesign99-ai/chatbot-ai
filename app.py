from flask import Flask, request, render_template, jsonify
from Chatbot import DirectorAgent


app = Flask(
    __name__,
    static_url_path="/static",
    static_folder="static",
    template_folder="templates"
)

director = DirectorAgent()


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    user_input = data.get("message", "")
    reply = director.handle_user_message(user_input)
    return jsonify({"reply": reply})


if __name__ == "__main__":
    print("Server đang chạy tại http://127.0.0.1:8000/")
    app.run(host="0.0.0.0", port=8000, debug=True)
