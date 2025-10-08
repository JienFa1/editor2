# -*- coding: utf-8 -*-
"""
config.py — cấu hình dùng lại 'compose'
- Có biến DOCUMENT (đối tượng python-docx Document) để giữ file Word đang xử lý.
- Nhãn (labels) phản ánh bố cục tin tức mục vụ.
- edit_prompts: các quy tắc biên tập độc lập.
- map: ánh xạ N–N giữa label_key và edit_prompt_ids.
- compose: điều khiển cách kết hợp & sắp xếp quy tắc khi một đoạn có nhiều nhãn.
"""

# === Document hiện hành (gán ở runtime) ===

DOCUMENT =   r"C:\Users\WangJienFa\Postgre&MySQL\Downloads\HKTT\New folder\Editor\data\04-Bản gốc-BẢNG TIN THÁNG 7 GX CHANH THIEN.docx"

# === Danh sách nhãn hợp lệ (whitelist cho classifier) ===
ALLOWED_LABELS_DEFAULT = [
    "thong_bao_muc_vu_gioi_thieu",  # Thông báo sự kiện mục vụ (giới thiệu)
    "gioi_thieu_nhan_su",           # Giới thiệu nhân sự
    "tuong_thuat_su_kien",          # Tường thuật sự kiện
    "ket_tu_tong_ket",              # Kết từ - tổng kết
    "ket_tu_suy_niem",              # Kết từ - suy niệm
]

# ====== (2) Cấu hình LLM Providers ======
# --- OLLAMA ---
# Model Ollama bạn muốn dùng
OLLAMA_MODEL = "llama3.1:8b-instruct-q6_K"
# API URL đầy đủ (tiện tra cứu/ghi log; llm.py KHÔNG dùng biến này)
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# --- OPENAI ---
# Model OpenAI bạn muốn dùng
OPENAI_MODEL = "gpt-4o-mini"
# API URL đầy đủ (tham khảo; llm.py KHÔNG dùng biến này)
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
# API key đặt trực tiếp ở đây (nếu bạn muốn), hoặc để trống rồi set ở nơi khác trong runtime
OPENAI_API_KEY = ""  # Ví dụ: "sk-xxx"

# ====== (2) Cấu hình LLM Providers ======
USE_OLLAMA = True  # "OPENAI" hoặc "OLLAMA"

# === Registry chính ===
REGISTRY_DICT = {
    # 1) Danh mục nhãn
    "labels": [
        {"key": "thong_bao_muc_vu_gioi_thieu", "name": "Thông báo sự kiện mục vụ (giới thiệu)"},
        {"key": "gioi_thieu_nhan_su",          "name": "Giới thiệu nhân sự"},
        {"key": "tuong_thuat_su_kien",         "name": "Tường thuật sự kiện"},
        {"key": "ket_tu_tong_ket",             "name": "Kết từ - tổng kết"},
        {"key": "ket_tu_suy_niem",             "name": "Kết từ - suy niệm"},
    ],

    # 2) Các quy tắc biên tập (tái sử dụng nhiều label)
    "edit_prompts": [
        {
            "id": "EP_LEAD_TBMV",
            "text": (
                "Chỉnh sửa lead cho bản tin mục vụ: làm rõ 5W1H (Ai/Sự kiện/Khi nào/Ở đâu/Vì sao hoặc Mục đích). "
                "Tiêu đề ngắn gọn, đúng trọng tâm. Chuẩn hoá ngày-tháng (dd/mm/yyyy), chức danh, tên riêng; "
                "giọng trang trọng, mục vụ; không thêm dữ kiện mới."
            )
        },
        {
            "id": "EP_PROFILE_INTRO",
            "text": (
                "Biên tập giới thiệu nhân sự: nêu rõ chức vụ, nhiệm vụ, bối cảnh/bổ nhiệm, thời điểm hiệu lực. "
                "Kiểm chuẩn tên riêng, học vị, chức danh Giáo hội; giọng trung dung, trang trọng; không bình luận."
            )
        },
        {
            "id": "EP_EVENT_REPORT",
            "text": (
                "Tường thuật sự kiện: mở đầu ngắn gọn, tóm tắt mục đích; trình bày diễn tiến theo thời gian; "
                "trích yếu nội dung chính, số liệu/cột mốc quan trọng; tránh cảm tính; ngôi thứ ba; nhất quán thời-thể."
            )
        },
        {
            "id": "EP_CONCLUSION_SUMMARY",
            "text": (
                "Kết từ - tổng kết: tóm lược thông điệp chính, ghi nhận đóng góp/cảm ơn (nếu có), "
                "điểm lại kết quả/ý nghĩa; không nêu thông tin mới."
            )
        },
        {
            "id": "EP_CONCLUSION_REFLECTION",
            "text": (
                "Kết từ - suy niệm: gợi suy tư thiêng liêng ngắn gọn, liên hệ Lời Chúa hoặc giáo huấn phù hợp; "
                "không diễn giải giáo lý mới; tránh khẳng định gây tranh cãi."
            )
        },
        {
            "id": "EP_STYLE_NEWS_TONE",
            "text": (
                "Chuẩn hoá văn phong báo chí: câu ngắn, súc tích, khách quan; tránh cảm thán; "
                "thống nhất ngôi và thì; dùng thuật ngữ mục vụ chính xác."
            )
        },
        {
            "id": "EP_NUM_DATE_CLEAN",
            "text": (
                "Chuẩn hoá chính tả, số và ngày tháng: viết số/tháng/năm theo định dạng nhất quán; "
                "chuẩn hoá tên riêng, địa danh, chức danh; bỏ khoảng trắng/dấu câu thừa."
            )
        },
    ],

    # 3) Ánh xạ N–N: mỗi label_key -> nhiều edit_prompt_ids
    "map": [
        {
            "label_key": "thong_bao_muc_vu_gioi_thieu",
            "edit_prompt_ids": ["EP_LEAD_TBMV", "EP_STYLE_NEWS_TONE", "EP_NUM_DATE_CLEAN"]
        },
        {
            "label_key": "gioi_thieu_nhan_su",
            "edit_prompt_ids": ["EP_PROFILE_INTRO", "EP_STYLE_NEWS_TONE", "EP_NUM_DATE_CLEAN"]
        },
        {
            "label_key": "tuong_thuat_su_kien",
            "edit_prompt_ids": ["EP_EVENT_REPORT", "EP_STYLE_NEWS_TONE", "EP_NUM_DATE_CLEAN"]
        },
        {
            "label_key": "ket_tu_tong_ket",
            "edit_prompt_ids": ["EP_CONCLUSION_SUMMARY", "EP_STYLE_NEWS_TONE"]
        },
        {
            "label_key": "ket_tu_suy_niem",
            "edit_prompt_ids": ["EP_CONCLUSION_REFLECTION", "EP_STYLE_NEWS_TONE"]
        },
    ],

    # 4) compose: điều khiển cách ghép quy tắc khi đa nhãn
    "compose": {
        # Khung system chung cho LLM
        "base_system_prompt": (
            "Bạn là biên tập viên tin tức mục vụ. Chỉ trả về nội dung đã chỉnh sửa theo yêu cầu. "
            "Giữ trung thực dữ kiện; không thêm thông tin mới; tôn trọng bối cảnh mục vụ."
        ),

        # Chiến lược **duy nhất** theo yêu cầu của bạn
        "multi_label_strategy": "union",      # lấy HỢP các quy tắc của mọi nhãn
        "deduplicate": True,                  # loại trùng (gặp trước giữ trước)

        # Thứ tự cuối cùng (ổn định): theo bảng ưu tiên toàn cục
        "ordering": "by_global_order",
        "global_prompt_order": [
            "EP_LEAD_TBMV",
            "EP_PROFILE_INTRO",
            "EP_EVENT_REPORT",
            "EP_CONCLUSION_SUMMARY",
            "EP_CONCLUSION_REFLECTION",
            "EP_STYLE_NEWS_TONE",
            "EP_NUM_DATE_CLEAN"
        ]
    }
}
