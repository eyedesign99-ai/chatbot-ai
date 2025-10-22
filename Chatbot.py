import requests
import openai
import json
import os
from openpyxl import Workbook, load_workbook
from datetime import datetime
import uuid

# --- Cấu hình API Key ---
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

# --- Nạp dữ liệu giá ---
price_path = os.path.join(os.path.dirname(__file__), "information", "price.json")
try:
    with open(price_path, "r", encoding="utf-8") as f:
        ty_le_khung_data = json.load(f)
    print(f"✅ Đã nạp dữ liệu từ: {os.path.abspath(price_path)}")
except FileNotFoundError:
    ty_le_khung_data = {}
    print(f"❌ Không tìm thấy file: {price_path}")

# --- Nạp dữ liệu phong thủy ---
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

# --- Ghi log ---
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

# --- Gửi truy vấn FAISS server ---
def query_server(user_input):
    url = "http://127.0.0.1:5000/search"
    headers = {"Content-Type": "application/json"}
    data = {"query": user_input, "limit": 20}
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print("❌ Lỗi server:", response.text)
            return None
    except requests.exceptions.ConnectionError as e:
        print("❌ Không kết nối được đến Flask server:", e)
        return None

# --- Chuẩn hóa dữ liệu sản phẩm ---
def enrich_product_data(context_list):
    enriched = []
    for item in context_list:
        if isinstance(item, dict) and "hình_ảnh" in item and "id" in item:
            img_path = item["hình_ảnh"]
            sp_id = item["id"]
            img_id = sp_id.split("-")[1] if "-" in sp_id else sp_id

            sanpham_html = f"""
            <div class='sanpham'>
                <img src='https://cgi.vn/image/{img_path}' alt='tranh {img_id}' style='width:100%; border-radius:10px; margin-bottom:6px;'>
                <a href='https://cgi.vn/ar/{img_id}' target='_blank'>Xem AR</a> |
                <a href='https://cgi.vn/san-pham/{img_id}' target='_blank'>Xem Chi Tiết</a>
            </div>
            """
            enriched.append(sanpham_html)
    return enriched

# --- Prompt bán hàng ---
system_prompt = """
Bạn là nhân viên bán tranh chuyên nghiệp của CGI.

YÊU CẦU HIỂN THỊ:
- Trả lời tự nhiên, thân thiện như người bán hàng, 
- KHÔNG sử dụng markdown (![], (), **, []()).
- Mỗi sản phẩm chỉ hiển thị hình ảnh + link AR + link Xem Chi Tiết.
- Ví dụ hiển thị:
  <img src='https://cgi.vn/image/abc.jpg' alt='Ảnh tranh'>
  <a href='https://cgi.vn/ar/ID' target='_blank'>Xem AR</a> |
  <a href='https://cgi.vn/san-pham/ID' target='_blank'>Xem Chi Tiết</a>
- Toàn bộ câu trả lời phải là HTML hợp lệ để hiển thị trực tiếp trong trình duyệt.
"""

# --- Gửi câu hỏi tới OpenAI ---
def query_openai_with_context(context_list, user_input):
    enriched_html_blocks = enrich_product_data(context_list)
    html_output = "\n".join(enriched_html_blocks)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Khách hỏi: {user_input}\nHãy viết câu trả lời HTML ngắn gọn và chèn danh sách sản phẩm sau đây vào cuối:\n{html_output}"}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.5
    )

    gpt_text = response.choices[0].message.content

    # ✅ Làm sạch toàn bộ div rác và xuống dòng sai
    import re
    gpt_text = re.sub(r"<div[^>]*>", "", gpt_text)
    gpt_text = re.sub(r"</div>", "", gpt_text)
    gpt_text = gpt_text.replace("\n", " ").replace("\r", " ")

    # ✅ Tạo markup hoàn toàn an toàn cho Flask/Render
    # Bọc toàn bộ nội dung vào 1 div duy nhất => Render không thể phá cấu trúc grid
    full_html = f"""
    <div class='bot-message'>
        <div class='bot-text'>{gpt_text.strip()}</div>
        <div class='chatbot-gallery'>
            {html_output}
        </div>
    </div>
    """
    return full_html


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
