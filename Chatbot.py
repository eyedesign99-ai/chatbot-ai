import requests
import openai
import json
import os
from openpyxl import Workbook, load_workbook
from datetime import datetime
import uuid


# Cấu hình API Key của OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)


# --- Tải dữ liệu từ price.json ---
price_path = os.path.join(os.path.dirname(__file__), "information", "price.json")
try:
    with open(price_path, "r", encoding="utf-8") as f:
        ty_le_khung_data = json.load(f)
    print(f"✅ Đã nạp dữ liệu từ: {os.path.abspath(price_path)}")
except FileNotFoundError:
    ty_le_khung_data = {}
    print(f"❌ Không tìm thấy file: {price_path}")

# --- Thêm file tri thức phong thủy ---
phong_thuy_path = os.path.join(os.path.dirname(__file__), "information", "phong_thuy.json")
thong_tin_chung = {}
try:
    with open(phong_thuy_path, "r", encoding="utf-8") as f:
        thong_tin_chung.update({"phong_thuy": json.load(f)})
    print(f"✅ Đã nạp dữ liệu từ: {os.path.abspath(phong_thuy_path)}")
except FileNotFoundError:
    print(f"❌ Không tìm thấy file: {phong_thuy_path}")

# --- Sinh ID phiên chat ---
session_id = str(uuid.uuid4())[:8]

# --- Ghi log chat vào Excel ---
def log_chat(user_input, bot_reply):
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"{today}.xlsx")

    if os.path.exists(log_file):
        wb = load_workbook(log_file)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.append(["ID phiên", "Thời gian", "Người dùng", "Chatbot"])

    current_time = datetime.now().strftime("%H:%M:%S")
    ws.append([session_id, current_time, user_input, bot_reply])

    wb.save(log_file)

# --- Gửi truy vấn đến FAISS server ---
def query_server(user_input):
    url = "http://127.0.0.1:5000/search"
    headers = {"Content-Type": "application/json"}
    data = {"query": user_input}
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print("❌ Server trả về lỗi:", response.text)
            return None
    except requests.exceptions.ConnectionError as e:
        print("❌ Không kết nối được đến Flask server:", e)
        return None

# --- Chuẩn hóa dữ liệu sản phẩm: thêm hình_html và link_html ---
def enrich_product_data(context_list):
    for item in context_list:
        if isinstance(item, dict) and "hình_ảnh" in item and "id" in item:
            img_path = item["hình_ảnh"]
            sp_id = item["id"]
            img_id = sp_id.split("-")[1] if "-" in sp_id else sp_id
            item["hinh_html"] = f"<img src='https://cgi.vn/image/{img_path}' style='max-width:100%; border-radius:10px;'>"
            item["link_html"] = f"<p><a href='https://cgi.vn/san-pham/{img_id}' target='_blank'>Xem chi tiết sản phẩm</a></p>"
    return context_list

# --- Prompt bán hàng ---
system_prompt = """
Bạn là một nhân viên bán tranh chuyên nghiệp. 
Nguyên tắc hiển thị:
- LUÔN sử dụng đúng đường dẫn hình ảnh và link sản phẩm có sẵn trong dữ liệu.
- Hình ảnh hiển thị theo dạng HTML, ví dụ:
  <img src='/static/product/cgi/28.jpg' style='max-width: 100%; border-radius: 10px;'>
  <p><a href='https://cgi.vn/san-pham/28' target='_blank'>Xem chi tiết sản phẩm</a></p>
- Không dùng markdown ![Hình ảnh](...) hoặc link giả (#).
- Trả lời tự nhiên, thân thiện như người bán hàng, tư vấn thêm phong thủy, vị trí treo nếu có.
"""

# --- Gửi câu hỏi tới OpenAI ---
def query_openai_with_context(context_list, user_input):
    context_list = enrich_product_data(context_list)
    context_text = json.dumps(context_list, ensure_ascii=False, indent=2)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Khách hỏi: {user_input}\n\nDữ liệu sản phẩm:\n{context_text}"}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7
    )

    return response.choices[0].message.content

# --- Chạy chatbot ---
def chatbot():
    print("🤖 Chatbot đã sẵn sàng! Gõ 'exit' để thoát.\n")
    while True:
        user_input = input("Bạn: ")
        if user_input.lower() == "exit":
            print("👋 Chatbot kết thúc.")
            break
        faiss_results = query_server(user_input)
        if faiss_results:
            gpt_response = query_openai_with_context(faiss_results, user_input)
        else:
            gpt_response = query_openai_with_context([], user_input)
        print("Chatbot:", gpt_response)
        log_chat(user_input, gpt_response)

if __name__ == "__main__":
    chatbot()
