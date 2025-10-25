import requests
import openai
import json
import os
from datetime import datetime

# Cấu hình OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

# Load price / phong_thuy (nếu có)
base_dir = os.path.dirname(__file__)
def load_json(rel_path):
    path = os.path.join(base_dir, rel_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            print(f"✅ Nạp: {os.path.abspath(path)}")
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Không tìm thấy: {path}")
        return {}

ty_le_khung_data = load_json("information/price.json")
thong_tin_chung = {"phong_thuy": load_json("information/phong_thuy.json")}

# Simple session id (timestamp)
session_id = datetime.now().strftime("%Y%m%d%H%M%S")

# Ghi log dạng text (nhẹ hơn excel)
def log_chat(user_input, bot_reply):
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"chat_{datetime.now().strftime('%Y-%m-%d')}.txt")
    now = datetime.now().strftime("%H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {session_id} | USER: {user_input}\nBOT: {bot_reply}\n\n")

# Gọi FAISS server
def query_server(user_input):
    url = "http://127.0.0.1:5000/search"
    try:
        r = requests.post(url, json={"query": user_input}, timeout=4)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception as e:
        # im lặng để không làm crash; trả None để dùng fallback
        return None

# Thêm hinh_html nếu có
def enrich_product_data(context_list):
    for item in context_list:
        if isinstance(item, dict) and "hình_ảnh" in item and "id" in item:
            img_path = item["hình_ảnh"]
            sp_id = item["id"]
            img_id = sp_id.split("-")[1] if "-" in sp_id else sp_id
            item["hinh_html"] = (
                f"<div class='sanpham'>"
                f"<img src='https://cgi.vn/image/{img_path}' style='max-width:100%; border-radius:0px;'>"
                f"<p><a href='https://cgi.vn/ar/{img_id}' target='_blank'>Xem AR</a> | "
                f"<a href='https://cgi.vn/san-pham/{img_id}' target='_blank'>Xem Chi Tiết</a></p>"
                f"</div>"
            )
    return context_list

system_prompt = """
Bạn là nhân viên bán tranh chuyên nghiệp. Khi trả lời:
- Luôn dùng đường dẫn ảnh/link như dữ liệu.
- Trả về HTML cho phần hình ảnh (nếu có).
- Trả lời tự nhiên, thân thiện.
"""

def query_openai_with_context(context_list, user_input):
    context_list = enrich_product_data(context_list)
    context_text = json.dumps(context_list, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Khách hỏi: {user_input}\n\nDữ liệu sản phẩm:\n{context_text}"}
    ]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7
    )
    reply = response.choices[0].message.content
    reply = reply.replace("&lt;", "<").replace("&gt;", ">")
    return reply

def chatbot():
    print("🤖 Chatbot sẵn sàng. Gõ 'exit' để thoát.")
    while True:
        user_input = input("Bạn: ").strip()
        if user_input.lower() == "exit":
            break
        faiss_results = query_server(user_input) or []
        gpt_response = query_openai_with_context(faiss_results, user_input)
        print("Chatbot:", gpt_response)
        log_chat(user_input, gpt_response)

if __name__ == "__main__":
    chatbot()
