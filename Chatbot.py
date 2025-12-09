import os
import json
import sqlite3
import pickle
import csv
import re
import unicodedata
from typing import Optional
from datetime import datetime
from uuid import uuid4
from functools import lru_cache

from openai import OpenAI
import numpy as np

# =========================
# 1. CẤU HÌNH ĐƯỜNG DẪN
# =========================

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def resolve_path(env_name: str, default_relative: str) -> str:
    """
    Pick a path from environment if provided, otherwise fall back to repo-relative.
    This keeps local dev (Windows) and deploy (Linux) in sync without hardcoding drives.
    """
    env_value = os.getenv(env_name)
    if env_value:
        return env_value
    return os.path.join(REPO_ROOT, default_relative)


BASE_DIR = resolve_path("CHATBOT_DATA_DIR", "central_data")

SQLITE_PATH = os.path.join(BASE_DIR, "sqlite", "paintings.db")
# Semantic index data (fallback when keyword search returns nothing)
TOPIC_META_PATH = os.path.join(BASE_DIR, "vectors", "meta.pkl")
TOPIC_VECTORS_PATH = os.path.join(BASE_DIR, "vectors", "vectors.npy")

LOG_DIR = resolve_path("CHATBOT_LOG_DIR", "logs")
IMAGE_BASE_URL = os.getenv(
    "IMAGE_BASE_URL",
    "https://painting-cgi.s3.ap-southeast-1.amazonaws.com/",
)

# =========================
# 2. OPENAI CLIENT & API KEY
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(
        "❌ Chưa thiết lập biến môi trường OPENAI_API_KEY. "
        "Hãy set trong hệ thống trước khi chạy chatbot."
    )

# client với timeout/retry ngắn hơn (giống file cũ đã tối ưu)
client = OpenAI(timeout=25, max_retries=2)

EMBED_MODEL = "text-embedding-3-small"  # 1536 chiều
CHAT_MODEL = "gpt-4o-mini"

# =========================
# 3. TOPIC INDEX & EMBEDDING
# =========================

TOPIC_VECTORS = None
TOPIC_META = None


def load_topic_index():
    """Nạp topic index (dùng cho semantic topic search)."""
    global TOPIC_VECTORS, TOPIC_META
    if TOPIC_VECTORS is not None and TOPIC_META is not None:
        return

    if not (os.path.exists(TOPIC_META_PATH) and os.path.exists(TOPIC_VECTORS_PATH)):
        TOPIC_VECTORS = None
        TOPIC_META = []
        return

    with open(TOPIC_META_PATH, "rb") as f:
        TOPIC_META = pickle.load(f)

    TOPIC_VECTORS = np.load(TOPIC_VECTORS_PATH).astype("float32")
    # Topic index loaded; keep silent to avoid noisy CLI startup.


@lru_cache(maxsize=256)
def embed_text(text: str):
    """Tạo embedding cho text (cache để giảm số lần gọi API)."""
    resp = client.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return np.array(resp.data[0].embedding, dtype="float32")


def get_db_connection():
    if not os.path.exists(SQLITE_PATH):
        raise RuntimeError(
            f"SQLite database not found at {SQLITE_PATH}. "
            "Set CHATBOT_DATA_DIR to point to the data directory."
        )
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_query_for_like(q: str) -> str:
    return f"%{q.strip()}%"


def build_image_url(img_path: str) -> str:
    """Normalize relative image path to absolute URL."""
    if not img_path:
        return ""
    clean = img_path.replace("\\", "/").lstrip("/")
    if clean.startswith("cgi/"):
        clean = clean[len("cgi/"):]
    return f"{IMAGE_BASE_URL.rstrip('/')}/{clean}"


# =========================
# 4. AGENT: RETRIEVER
# =========================

STOPWORDS = {"tranh", "buc", "con", "hinh", "anh", "ve"}


def strip_accents(text: str) -> str:
    """Remove accents for accent-insensitive comparisons."""
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def extract_tokens(query: str):
    """
    Normalize and split the user query into tokens:
    - lowercase + strip accents
    - split on non-alphanumeric
    - drop stopwords like 'tranh', 'con' to focus on core nouns
    """
    clean = strip_accents((query or "").lower())
    raw_tokens = re.split(r"[^a-z0-9]+", clean)
    return [t for t in raw_tokens if t and t not in STOPWORDS]


class RetrieverAgent:
    """
    Nhiệm vụ:
    - Tìm tranh trong SQLite bằng keyword.
    - Nếu cần thì dùng semantic topic search (theo topic_meta + vectors).
    """

    def keyword_search_paintings(self, user_input: str, limit: Optional[int] = None):
        conn = get_db_connection()
        conn.create_function("strip_accents", 1, strip_accents)
        cur = conn.cursor()

        tokens = extract_tokens(user_input)
        if not tokens:
            normalized = strip_accents((user_input or "").lower().strip())
            tokens = [normalized] if normalized else []

        columns = ["title", "keywords", "themes", "emotions"]
        clauses = []
        params = []
        for tok in tokens:
            like_pattern = f"%{tok}%"
            clause = " OR ".join([f"strip_accents(lower({col})) LIKE ?" for col in columns])
            clauses.append(f"({clause})")
            params.extend([like_pattern] * len(columns))

        where_sql = " AND ".join(clauses) if clauses else "1=1"

        query = f"""
            SELECT id, title, image, general_info, keywords, themes, emotions,
                   description_short, json_path
            FROM paintings
            WHERE {where_sql}
            ORDER BY id ASC
        """
        if limit is not None:
            query += "\n            LIMIT ?;"
            params.append(limit)
        else:
            query += ";"

        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "title": r["title"],
                "image": r["image"],
                "general_info": r["general_info"],
                "keywords": (r["keywords"] or "").split(",") if r["keywords"] else [],
                "themes": (r["themes"] or "").split(",") if r["themes"] else [],
                "emotions": (r["emotions"] or "").split(",") if r["emotions"] else [],
                "description_short": r["description_short"],
                "json_path": r["json_path"]
            })

        return results

    def semantic_topic_search(
        self,
        user_input: str,
        top_k_topics: int = 2,
        max_items: Optional[int] = None
    ):
        load_topic_index()
        if TOPIC_VECTORS is None or len(TOPIC_META) == 0:
            return []

        try:
            q_vec = embed_text(user_input)
        except Exception as e:
            print(f"[Retriever] Semantic embedding error: {e}")
            return []
        q_norm = q_vec / (np.linalg.norm(q_vec) + 1e-8)
        topic_norm = TOPIC_VECTORS / (
            np.linalg.norm(TOPIC_VECTORS, axis=1, keepdims=True) + 1e-8
        )

        scores = topic_norm @ q_norm  # cosine similarity
        top_idx = np.argsort(scores)[::-1][:top_k_topics]

        candidate_ids = []
        for idx in top_idx:
            meta = TOPIC_META[idx]
            ids = meta.get("suggest_ids") or []
            if not ids and meta.get("id") is not None:
                ids = [meta.get("id")]
            candidate_ids.extend(ids)

        # loại trùng, giữ thứ tự
        seen = set()
        unique_ids = []
        max_allowed = max_items if max_items is not None else float("inf")
        for i in candidate_ids:
            if i not in seen:
                seen.add(i)
                unique_ids.append(i)
            if len(unique_ids) >= max_allowed:
                break

        if not unique_ids:
            return []

        conn = get_db_connection()
        cur = conn.cursor()

        placeholders = ",".join("?" for _ in unique_ids)
        sql = f"""
            SELECT id, title, image, general_info, keywords, themes, emotions,
                   description_short, json_path
            FROM paintings
            WHERE id IN ({placeholders});
        """
        cur.execute(sql, unique_ids)
        rows = cur.fetchall()
        conn.close()

        row_map = {r["id"]: r for r in rows}
        results = []
        for pid in unique_ids:
            r = row_map.get(pid)
            if not r:
                continue
            results.append({
                "id": r["id"],
                "title": r["title"],
                "image": r["image"],
                "general_info": r["general_info"],
                "keywords": (r["keywords"] or "").split(",") if r["keywords"] else [],
                "themes": (r["themes"] or "").split(",") if r["themes"] else [],
                "emotions": (r["emotions"] or "").split(",") if r["emotions"] else [],
                "description_short": r["description_short"],
                "json_path": r["json_path"]
            })

        return results

    def search_paintings_for_user_query(self, user_input: str, max_results: Optional[int] = None):
        """
        Router search:
        - Ưu tiên keyword.
        - Nếu keyword trả quá ít kết quả -> dùng thêm semantic topic search.
        """
        kw_results = self.keyword_search_paintings(user_input, limit=max_results)
        if kw_results:
            print(f"[Retriever] Keyword search trả {len(kw_results)} kết quả, dùng trực tiếp.")
            return kw_results

        print("[Retriever] Keyword ít kết quả -> thêm semantic topic search.")
        sem_results = self.semantic_topic_search(
            user_input, top_k_topics=2, max_items=max_results
        )

        if sem_results:
            print(f"[Retriever] Semantic topic search trả {len(sem_results)} kết quả.")
            return sem_results

        print("[Retriever] Không có semantic -> fallback keyword.")
        return kw_results


# =========================
# 5. AGENT: SUMMARIZER
# =========================

class SummarizerAgent:
    """
    Nhiệm vụ:
    - Viết 1 đoạn giới thiệu ngắn (2–4 câu) về chủ đề tranh phù hợp với yêu cầu của khách.
    - Không render gallery, chỉ text giới thiệu.
    """

    SYSTEM_PROMPT = """
Bạn là nhân viên tư vấn bán tranh.
Nhiệm vụ: Viết đoạn giới thiệu NGẮN GỌN (2–4 câu) về bộ sưu tập tranh
phù hợp với yêu cầu của khách hàng.

Quy tắc:
- Không liệt kê từng bức tranh chi tiết.
- Chỉ nói khái quát về phong cách, cảm xúc, không gian phù hợp.
- Giọng văn thân thiện, rõ ràng, ưu tiên súc tích.
"""

    def _compact_for_summary(self, products, max_items: int = 10):
        """Giữ thông tin tối thiểu cho Summarizer để giảm token."""
        trimmed = []
        for item in products[:max_items]:
            if not isinstance(item, dict):
                continue
            trimmed.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "general_info": item.get("general_info"),
                "themes": item.get("themes"),
                "emotions": item.get("emotions"),
                "description_short": item.get("description_short"),
            })
        return trimmed

    def summarize(self, user_input: str, products: list) -> str:
        if not products:
            return "Hiện tại mình chưa tìm thấy bức tranh phù hợp trong kho dữ liệu."

        compacted = self._compact_for_summary(products)
        context_text = json.dumps(compacted, ensure_ascii=False, separators=(",", ":"))

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Yêu cầu của khách: {user_input}\n\n"
                    f"Dữ liệu tóm tắt các tranh:\n{context_text}"
                )
            },
        ]

        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=400,
            response_format={"type": "text"},
        )

        return resp.choices[0].message.content


# =========================
# 6. AGENT: DESIGNER (RENDER UI/HTML)
# =========================

class DesignerAgent:
    """
    Nhiệm vụ:
    - Enrich dữ liệu (thêm image_html, link_html).
    - Render HTML layout: phần trên là intro_text, phần dưới là gallery nhiều tranh.
    """

    @staticmethod
    def enrich_product_data(context_list):
        for item in context_list:
            if isinstance(item, dict) and "image" in item and "id" in item:
                img_path = item["image"]  # vd: "cgi/28.jpg"
                sp_id = item["id"]        # vd: 28
                image_url = build_image_url(img_path)

                image_html = (
                    f"<img src='{image_url}' "
                    f"style='max-width: 100%; border-radius: 10px;'>"
                )
                link_html = (
                    f"<a class='link-btn' href='https://cgi.vn/san-pham/{sp_id}' "
                    f"target='_blank'>Xem chi tiết</a>"
                )
                ar_link_html = (
                    f"<a class='link-btn' href='https://cgi.vn/ar/{sp_id}.html' "
                    f"target='_blank'>Xem AR</a>"
                )

                item["image_html"] = image_html
                item["hình_html"] = image_html  # alias
                item["link_html"] = link_html
                item["ar_link_html"] = ar_link_html

        return context_list

    def render_gallery(self, intro_text: str, products: list) -> str:
        """
        Tạo HTML hoàn chỉnh:
        - Phần đầu: intro_text.
        - Phần sau: gallery tất cả tranh.
        """
        if not products:
            return (
                "<p>Hiện tại mình chưa tìm thấy bức tranh phù hợp trong kho dữ liệu.</p>"
            )

        products = self.enrich_product_data(products)

        html_parts = []
        # Phần giới thiệu ngắn
        if intro_text:
            html_parts.append(f"<p>{intro_text}</p>")

        # Phần gallery
        html_parts.append("<h3>Danh sách tranh gợi ý</h3>")
        html_parts.append('<div class="gallery">')

        for item in products:
            title = item.get("title") or "Tranh"
            image_html = (
                item.get("image_html")
                or item.get("hình_html")
                or "<div>(Không có hình)</div>"
            )
            link_html = item.get("link_html") or ""
            ar_link_html = item.get("ar_link_html") or ""
            links_combined = ""
            if ar_link_html or link_html:
                separator = "<span class=\"link-separator\">|</span>" if ar_link_html and link_html else ""
                links_combined = f"<p class='links-row'>{ar_link_html}{separator}{link_html}</p>"

            block = f"""
            <div class="item" style="margin-bottom: 16px;">
                <h4>{title}</h4>
                {image_html}
                {links_combined}
            </div>
            """
            html_parts.append(block)

        html_parts.append("</div>")
        return "\n".join(html_parts)


# =========================
# 7. AGENT: LOGS
# =========================

SESSION_ID = str(uuid4())[:8]


class LogAgent:
    """
    Nhiệm vụ:
    - Ghi log dạng CSV: mỗi ngày 1 file, mỗi dòng là 1 lượt chat.
    """

    def __init__(self, log_dir: str = LOG_DIR):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

    def log_chat(self, user_input: str, bot_reply: str):
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"{today}.csv")

        current_time = datetime.now().strftime("%H:%M:%S")
        is_new = not os.path.exists(log_file)

        with open(log_file, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(["ID phiên", "Thời gian", "Người dùng", "Chatbot"])
            writer.writerow([SESSION_ID, current_time, user_input, bot_reply])


# =========================
# 8. AGENT: DIRECTOR (ĐIỀU PHỐI)
# =========================

class DirectorAgent:
    """
    Nhiệm vụ:
    - Nhận câu hỏi từ user.
    - Gọi Retriever -> lấy danh sách tranh.
    - Gọi Summarizer -> tạo intro ngắn.
    - Gọi Designer -> render HTML trả về.
    - Gọi LogAgent -> ghi log.
    """

    def __init__(self):
        self.retriever = RetrieverAgent()
        self.summarizer = SummarizerAgent()
        self.designer = DesignerAgent()
        self.logger = LogAgent()

    def handle_user_message(self, user_input: str) -> str:
        # 1. Lấy dữ liệu tranh
        products = self.retriever.search_paintings_for_user_query(user_input)

        # 2. Tạo đoạn giới thiệu ngắn
        intro_text = self.summarizer.summarize(user_input, products)

        # 3. Render HTML layout
        response_html = self.designer.render_gallery(intro_text, products)

        # 4. Ghi log
        self.logger.log_chat(user_input, response_html)

        return response_html


# =========================
# 9. MAIN CHATBOT LOOP (CLI)
# =========================

def chatbot_cli():
    # Preload topic index để tránh đọc file ở request đầu tiên
    load_topic_index()

    director = DirectorAgent()

    print("🤖 Chatbot (multi-agent) đã sẵn sàng! Gõ 'exit' để thoát.\n")
    while True:
        user_input = input("Bạn: ")
        if user_input.lower().strip() == "exit":
            print("👋 Chatbot kết thúc.")
            break

        try:
            reply = director.handle_user_message(user_input)
        except Exception as e:
            print("❌ Lỗi trong quá trình xử lý:", e)
            reply = "Xin lỗi, hiện tại mình đang gặp chút trục trặc hệ thống, bạn thử lại sau nhé."

        print("Chatbot (HTML):")
        print(reply)
        print("-" * 40)


if __name__ == "__main__":
    chatbot_cli()
