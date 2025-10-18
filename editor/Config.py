# -*- coding: utf-8 -*-
import sys
import unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8") 
"""
config.py — cấu hình dùng lại 'compose'
- Có biến DOCUMENT (đối tượng python-docx Document) để giữ file Word đang xử lý.
- Nhãn (labels) phản ánh bố cục tin tức mục vụ.
- edit_prompts: các quy tắc biên tập độc lập.
- map: ánh xạ N–N giữa label_key và edit_prompt_ids.
- compose: điều khiển cách kết hợp & sắp xếp quy tắc khi một đoạn có nhiều nhãn.
"""

# === Document hiện hành (gán ở runtime) ===

DOCUMENT =   r"C:\Users\TRUYENTHONG\Desktop\finetune\editor\data\test_open_20251017T083054Z.docx"

# === Semantic label index (finetune-v2) ===
_MODULE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE_DIR.parent
SEMANTIC_INDEX_DIR = _PROJECT_ROOT / "semantic_index"
FAISS_INDEX_PATH = SEMANTIC_INDEX_DIR / "label_index.faiss"
FAISS_METADATA_PATH = SEMANTIC_INDEX_DIR / "label_index_meta.json"
LABEL_DESCRIPTIONS_PATH = SEMANTIC_INDEX_DIR / "label_descriptions.json"
EMBEDDING_MODEL_NAME = "AITeamVN/Vietnamese_Embedding"
# Ưu tiên GPU (CUDA); mã sẽ tự fallback về CPU nếu không khả dụng.
EMBEDDING_DEVICE = "cuda"
SIMILARITY_TOP_K = 1
SIMILARITY_THRESHOLD = 0.1

# === Danh sách nhãn hợp lệ (whitelist cho classifier) ===

# ====== (2) Cấu hình LLM Providers ======
# --- OLLAMA ---
# Model Ollama bạn muốn dùng
OLLAMA_MODEL = "gpt-oss:20b"
# API URL đầy đủ (tiện tra cứu hoặc ghi log; llm.py KHÔNG dùng biến này)
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# --- OPENAI ---
# Model OpenAI bạn muốn dùng
OPENAI_MODEL = "gpt-4o-mini"
# API URL đầy đủ (tham khảo; llm.py KHÔNG dùng biến này)
OPENAI_API_URL = "https: hoặc  hoặc api.openai.com hoặc v1 hoặc chat hoặc completions"
# API key đặt trực tiếp ở đây (nếu bạn muốn),  hoặc  để trống rồi set ở nơi khác trong runtime
OPENAI_API_KEY = ""  # Ví dụ: "sk-xxx"

# ====== (2) Cấu hình LLM Providers ======
USE_OLLAMA = True  # "OPENAI"  hoặc  "OLLAMA"

# === Registry chính ===
REGISTRY_DICT = {
    # 1) Danh mục nhãn
    "labels": [
        {"key": "tittle", "name": "tiêu đề"}, 
        #{"key": "", "name": "mở bài (LEAD tin tức mục vụ) - Thánh Lễ Tri ân (Mở bài)"},       #thong_bao_muc_vu_gioi_thieu_TA
        {"key": "mo_bai_tom_tat_thanh_le", "name": "mở bài (LEAD tin tức mục vụ) - Thánh Lễ"},        #thong_bao_muc_vu_gioi_thieu_TA
        #{"key": "", "name": "mở bài (LEAD tin tức mục vụ) - Thánh Lễ Ban Bí Tích (Mở bài)"},      #thong_bao_muc_vu_gioi_thieu_TA
        #{"key": "thong_bao_muc_vu_khan_dong", "name": "mở bài (LEAD tin tức mục vụ) - Kỷ niệm khấn dòng"},
        #{"key": "thong_bao_muc_vu_gioi_thieu_K", "name": "mở bài tóm tắt - Thánh Lễ khác (Mở bài)"},
        #{"key": "thong_bao_muc_vu_shdd", "name": "mở bài tóm tắt - sinh hoạt đạo đức (Mở bài)"},
        {"key": "gioi_thieu_nhan_su",          "name": "Giới thiệu nhân sự"},
        {"key": "tuong_thuat_su_kien_thanh_le",         "name": "Tường thuật sự kiện Thánh lễ "},
        {"key": "tuong_thuat_su_kien_ngoai_thanh_le",         "name": "Tường thuật sự kiện ngoài Thánh lễ "},
        {"key":"tuong_thuat_su_kien_bai_giang","name":"Tường thuật sự kiện – Bài giảng"},
        {"key":"ket_tu_tuong_thuat_thanh_le","name":"Kết từ "},
        #{"key": "ket_tu_tong_ket",             "name": "Kết từ - tổng kết"},của tường thuật Thánh lễ
        #{"key": "ket_tu_suy_niem",             "name": "Kết từ - suy niệm"}
        #{"key":"ket_tu_suy_niem_loi_cau_nguyen","name":"Kết từ suy niệm – Lời cầu nguyện"},
    ],

    # 2) Các quy tắc biên tập (tái sử dụng nhiều label)
    "edit_prompts": [
        {
            "id": "EP_STYLE_TONE", #giọng văn
            "text": (
                "Chuẩn hoá văn phong tin tức Công giáo: trang trọng, súc tích, khách quan; tránh cảm thán;"
                "Luôn sử dụng ngôi thứ ba; Dùng giọng văn trung tính kết hợp với sắc thái mục vụ và hiệp thông"
                "Kết hợp sự long trọng của phụng vụ với sự vui tươi, gần gũi, ấm áp của cộng đoàn."
            )
        },{
            "id": "EP_STYLE_TONE", #giọng văn
            "text": (
                "Chuẩn hoá văn phong tin tức Công giáo: trang trọng, súc tích, khách quan; tránh cảm thán;"
                "Luôn sử dụng ngôi thứ ba; Dùng giọng văn trung tính kết hợp với sắc thái mục vụ và hiệp thông"
                "Kết hợp sự long trọng của phụng vụ với sự vui tươi, gần gũi, ấm áp của cộng đoàn."
            )
        },{
            "id": "EP_STYLE_TONE", #giọng văn
            "text": (
                "Chuẩn hoá văn phong tin tức Công giáo: trang trọng, súc tích, khách quan; tránh cảm thán;"
                "Luôn sử dụng ngôi thứ ba; Dùng giọng văn trung tính kết hợp với sắc thái mục vụ và hiệp thông"
                "Kết hợp sự long trọng của phụng vụ với sự vui tươi, gần gũi, ấm áp của cộng đoàn."
            )
        },{
            "id": "EP_STYLE_TONE", #giọng văn
            "text": (
                "Chuẩn hoá văn phong tin tức Công giáo: trang trọng, súc tích, khách quan; tránh cảm thán;"
                "Luôn sử dụng ngôi thứ ba; Dùng giọng văn trung tính kết hợp với sắc thái mục vụ và hiệp thông"
                "Kết hợp sự long trọng của phụng vụ với sự vui tươi, gần gũi, ấm áp của cộng đoàn."
            )
        },
        {
            "id": "EP_TITTLE", #giọng văn
            "text": (
                "không buộc phải chỉnh sửa theo toàn bộ yêu cầu bên dưới, chỉ xác định những yêu cầu nào có thể áp dụng để cải thiện tiêu đề."
                "Kiểm tra cấu trúc:\nDạng chuẩn: [Sự kiện hoặc lễ] – [Dịp hoặc chủ đề bổn mạng/kỷ niệm] (, [Địa điểm/đơn vị hành lễ]).\nNếu thiếu hoặc thừa dấu câu, điều chỉnh cho hợp lý (dấu gạch ngang “–”, dấu phẩy)."
                "Kiểm tra và thêm dấu phẩy để tách rõ các cụm địa danh hoặc danh xưng Giáo hội (Giáo khu, Hội đoàn, Giáo xứ, Giáo hạt, Giáo phận, Dòng tu…)."
                "Dùng đúng các cụm: “Mừng lễ kính…”, “Thánh lễ tạ ơn…”, “Mừng kính Thánh…”, “Bổn mạng…”"
                "Xóa dấu phẩy không cần thiết khi nó tách rời các cụm danh xưng tôn giáo liên kết chặt chẽ, ví dụ: “bổn mạng, Thánh X” → “bổn mạng Thánh X”"
                "Đặt nội dung sự kiện lên trước, địa điểm về sau: Ví dụ “Thánh lễ Tạ ơn... tại Giáo xứ...” thay cho “Giáo xứ... – Thánh lễ...”"
                "Kết nối cụm từ mô tả lễ và tên vị Thánh thành một đơn vị nghĩa duy nhất."
                "Nếu tiêu đề đã đúng cấu trúc, giữ nguyên."
                "Không thêm, bớt hoặc thay đổi nội dung sự kiện."
                "Liệt kê nhiều hoạt động bằng dấu phẩy hoặc “và”, không dùng ký hiệu “&”."
                "Giữ nguyên phong cách trang trọng, không thêm cảm xúc"
                "Loại bỏ phần mở đầu hành chính hoặc kỹ thuật, như: “BẢNG TIN, “THÔNG BÁO”, “TIN MỚI”, “LỊCH MỤC VỤ”, “CẬP NHẬT”, “THÔNG TIN”…"
                "Duy trì cấu trúc trang trọng, tránh rườm rà hoặc ngắt quãng."
                "Chuyển tất cả về chữ hoa"
                "Trả về chỉ một tiêu đề duy nhất, đã chỉnh sửa hoàn chỉnh."
            )
        },
        {
            "id": "EP_CHUAN_HOA",
            "text": (
                "Sửa lỗi chính tả, ngữ pháp, dấu câu, bỏ khoảng trắng hoặc dấu câu thừa, các lỗi đánh máy khác."
                "Chuẩn hoá thời gian theo dạng: dd/mm/yyyy; giờ theo dạng hhgmm (ví dụ: 08g00, 16g30)."
                "quy tắc viết hoa cho danh xưng hoặc chức vụ hoặc đơn vị và thuật ngữ phụng vụ; chuẩn hóa tên dòng tu; dấu câu chặt chẽ."
                "Tên tổ chức hoặc đơn vị rõ ràng: viết đầy đủ (không viết tắt), giữ sự trang nghiêm. Nêu đầy đủ vai trò hoặc chức vụ và đơn vị chỉ khi có trong nguồn; không suy diễn thêm."
                "Tông trọng phẩm trật Công giáo"
                "giữ nguyên các dữ kiện định lượng (nếu nguồn có số cụ thể thì giữ nguyên số, không thay bằng diễn đạt mơ hồ); không mở rộng phạm vi người hoặc đơn vị  hoặc  thêm tập thể mới khi nguồn không nêu."
                "không lược bỏ các dữ kiện cốt lõi (nhất là người chủ sự, số lượng, đối tượng cầu nguyện)."
                "chỉ tái diễn đạt, sắp xếp, chuẩn hóa."
            )
        },
        {
            "id": "EP_STYLE_TONE", #giọng văn
            "text": (
                "Chuẩn hoá văn phong tin tức Công giáo: trang trọng, súc tích, khách quan; tránh cảm thán;"
                "Luôn sử dụng ngôi thứ ba; Dùng giọng văn trung tính kết hợp với sắc thái mục vụ và hiệp thông"
                "Kết hợp sự long trọng của phụng vụ với sự vui tươi, gần gũi, ấm áp của cộng đoàn."
            )
        },
        {
            "id": "EP_STYLE_TONE_TLTA", #giọng văn - TL bổn mạng, tri ân
            "text": (
                "Kết hợp thêm giọng văn nhấn mạnh tinh thần hiệp thông, tri ân, hân hoan."
            )
        },
        {
            "id": "EP_STYLE_TONE_TLKNKD", #giọng văn - TL kỷ niệm khấn dòng
            "text": (
                "Bổ sung giọng văn nhấn mạnh bầu khí linh thiêng và trang nghiệm, niềm vui thánh hiến, tinh thần tạ ơn."
            )
        },
        {
            "id": "EP_WORD_LEAD", #từ ngữ - lead chung
            "text": (
                "Tránh từ ngữ quá báo chí, giật gân  hoặc  thuần tuý hành chính."
                "Sử dụng từ ngữ nhẹ nhàng, mục vụ và gợi ý nghĩa, cảm xúc thiêng liêng; Kết hợp với từ ngữ giàu tính biểu tượng."
                "Thêm các từ ngữ phụng vụ với các cử hành phụng vụ Công giáo"
                "Có thể thêm lối diễn đạt sâu lắng nhưng vẫn giữ khách quan, tránh lối văn quá cá nhân."
                "Thay đổi sang những động từ trang trọng, (ví dụ: “được cử hành trọng thể”, “quy tụ đông đảo”,...)"
                "Bổ sung sắc thái cộng đoàn, hiệp thông, (ví dụ: “cùng hiệp dâng thánh lễ”, “hân hoan”,...)"
                "Thay từ cá nhân bằng cộng đoàn"
                "Ngôn ngữ cần được trau chuốt, dễ đọc, chuẩn biên tập."
            )
        },
        
        {
            "id": "EP_STRUC_LEAD", #Lead chung
            "text": (
                "Mở đầu bằng lead báo chí “Địa điểm + thời gian – … ” Ví dụ: Giáo xứ X, dd/mm/yyyy – Vào lúc hhgmm (Nếu có),..."
                "Sắp xếp đoạn văn theo cấu trúc: (1) địa điểm – thời gian → (2) bầu khí (ví dụ: “Trong tâm tình tạ ơn”, “Trong bầu khí linh thiêng và tràn đầy hồng ân”) + sự kiện chính (ai, làm gì) → (3) nội dung cụ thể."
                "Nếu có giới thiệu nhân sự thì viết thành 1 câu riêng gồm chủ sự + thành phần tham dự, giữ nguyên tên và chức vụ."
                "Tránh câu quá dài. Nếu gặp tình trạng dồn thông tin trong một câu thì nên chia thành các mệnh đề rõ ràng,  hoặc  sửa thành cách trình bày song song, mạch lạc các thông tin khác nhau, phân lớp đối tượng để đảm bảo logic mục vụ."
                "Tránh lối kể “hôm nay… đã diễn ra…”, thay bằng cấu trúc trang trọng."
            )
        },
        {
            "id": "EP_STRUC_LEAD_KNKD", #cấu trúc cho lễ kỷ niệm khấn dòng
            "text": (
                "Mở đầu bằng lead báo chí “Địa điểm, thời gian – …”"
                "Câu 1: Bối cảnh, bầu khí sự kiện (linh thiêng, vui tươi, thánh hiến)."
                "Câu 2: Giới thiệu Nhân vật chính, kỷ niệm (Ngân khánh, Kim khánh, khấn dòng…)."
                "Tránh viết một câu quá dài, chia mạch lạc 1–2 câu và sử dụng cấu trúc trang trọng."
            )
        },
        # {
        #     "id": "EP_TONE_LEAD_KGGL",
        #     "text": (
        #         "Chuẩn hoá văn phong tin tức Công giáo: trang trọng, súc tích, khách quan; tránh cảm thán; (trang trọng nhưng vẫn gần gũi, vui tươi, mang tính cộng đoàn)"
        #         "Luôn sử dụng ngôi thứ ba; Dùng giọng văn trung tính kết hợp với sắc thái mục vụ và hiệp thông"
        #         "Thêm bầu khí hân hoan, vui tươi của ngày giáo lý."
        #         "Nhấn mạnh tinh thần hiệp thông và ý nghĩa phụng vụ của sự kiện."
        #     )
        # },
        # {
        #     "id": "EP_STRUC_LEAD_KGGL",
        #     "text": (
        #         "Mở đầu bằng lead báo chí “Địa điểm, thời gian – …”"
        #         "Câu 1: Bầu khí + sự kiện chính (Thánh lễ khai giảng năm học giáo lý)."
        #         "Câu 2: Thành phần tham dự (cha xứ, tu sĩ, giáo lý viên, huynh trưởng, thiếu nhi)."
        #         "Tránh viết một câu quá dài, chia mạch lạc 1–2 câu."
        #     )
        # },
        {
            "id": "EP_TONE_LEAD_SHDS", #giọng văn - sinh hoạt đạo đức
            "text": (
                "Chuẩn hoá văn phong tin tức Công giáo: trang trọng, súc tích, khách quan; tránh cảm thán;"
                "Luôn sử dụng ngôi thứ ba; Dùng giọng văn trung tính kết hợp với sắc thái mục vụ và hiệp thông"
                "Bổ sung yếu tố ấm áp, vui tươi của sinh hoạt đạo đức"            )
        },
        {
            "id": "EP_STRUC_LEAD_SHDS", #cấu trúc - sinh hoạt đạo đức
            "text": (
                "Mở đầu bằng lead báo chí “Địa điểm, thời gian – …”"
                "Câu 1: Nêu sự kiện chính + ý nghĩa"
                "Câu 2: Thời gian chi tiết + số lượng tham dự + bầu khí (niềm vui, hiệp nhất)."
            )
        },
        {
            "id": "EP_WORD_LEAD_SHDS", #từ ngữ - sinh hoạt đạo đức
            "text": (
                "Ưu tiên từ ngữ mục vụ: “dành tặng món quà yêu thương”, “niềm hân hoan và tinh thần hiệp nhất”."
                "Sử dụng cách diễn đạt tích cực, thân tình: “biết bao giờ học, giờ lễ và sinh hoạt ý nghĩa”."
                "Sửa từ ngữ cá nhân thành từ ngữ cộng đoàn"
                "Ngôn ngữ cần được trau chuốt, dễ đọc, chuẩn biên tập."
            )
        },
        #=========================================================bắt đầu=========================================#
        {
            "id": "EP_LEAD_HOI_DOAN_STRUC",
            "text": (
                "Bố cục: Sắp xếp đoạn văn theo cấu trúc: Mở đầu bằng lead báo chí “Địa điểm, thời gian –  bầu khí (ví dụ: “Trong tâm tình tạ ơn”),  Sự kiện chính (ai, làm gì) – Nội dung cụ thể."
                " hoặc Nếu có giới thiệu nhân sự thì viết thành 1 câu riêng gồm chủ sự (& đồng tế nếu có) + thành phần tham dự, giữ nguyên tên và chức vụ."
                " hoặc Nếu câu có nhiều chi tiết, bị dồn thông tin, tách thành nhiều câu, mệnh đề rõ ràng để văn bản dễ đọc,  đảm bảo logic mục vụ."
            )
        },
        {
            "id": "EP_LEAD_HOI_DOAN_TONE",
            "text": (
                "Giọng văn: đảm bảo sắc thái trang trọng, sốt sắng, mang tính thiêng liêng và mục vụ; tránh giọng hành chính hoặc báo cáo khô khan."
            )
        },
        {
            "id": "EP_LEAD_HOI_DOAN_WORD",
            "text": (
                "Cách dùng từ: chọn từ ngữ giàu tính phụng vụ, gợi ý nghĩa thiêng liêng, câu văn gọn gàng, nhấn mạnh sự kiện chính và mục đích;"
                "Tránh từ ngữ thuần tuý hành chính hoặc báo chí giật gân."
            )
        },
        {
            "id": "EP_LEAD_HOI_DOAN_AIM",
            "text": (
                "Diễn đạt ý nghĩa: làm nổi bật mục đích và giá trị tinh thần, không chỉ tường thuật sự kiện."
            )
        },
        {
            "id": "EP_PROFILE_ALL_AIM",
            "text": (
                "Diễn đạt ý nghĩa: làm rõ ai phụ trách, ai điều phối, nội dung chính, ai đảm trách; đảm bảo người đọc dễ nắm toàn cảnh."
            )
        },
        {
            "id": "EP_PROFILE_HOI_DOAN_TONE",
            "text": (
                "Giọng văn: giữ sắc thái trang trọng và mạch lạc, tránh giọng liệt kê rườm rà."
            )
        },
        {
            "id": "EP_PROFILE_HOI_DOAN_WORD",
            "text": (
                "Cách dùng từ: chọn từ gọn gàng, khái quát để bao quát nội dung; dùng dấu ngoặc thay cho gạch nối để bổ sung thông tin; lược bỏ chi tiết thừa, giữ trang nghiêm khi nhắc đến danh xưng."
            )
        },
        {
            "id": "EP_PROFILE_HOI_DOAN_STRUC",
            "text": (
                "bố cục: sắp xếp theo cấu trúc Người phụ trách hoặc điều phối – Nội dung chính của khóa học hoặc sự kiện – Người đảm trách nội dung. Nếu nhiều chi tiết, tách thành câu riêng để mạch văn rõ ràng."
                "thống nhất cách liệt kê nhân sự theo trật tự: trật tự “họ tên → chức vụ → định danh dòng tu (nếu có) → đơn vị mục vụ”"
            )
        },
        #=========================================================bắt đầu của biến cố & suy niệm=========================================#
        {
            "id": "EP_REPORT_BIEN_CO_SUY_NIEM_STRUC",
            "text": (
                "bố cục: sắp xếp đoạn văn theo cấu trúc Biến cố – Ý nghĩa – Tâm tình hoặc Nội dung liên hệ. Tách ý thành nhiều câu thay vì dồn nén chi tiết trong một câu dài."
            )
        },
        {
            "id": "EP_REPORT_BIEN_CO_SUY_NIEM_TONE",
            "text": (
                "Giọng văn: giữ sắc thái trang trọng, thiêng liêng, Mang chiều hướng suy niệm, tránh giọng tường thuật chi tiết khô khan."
            )
        },
        {
            "id": "EP_REPORT_BIEN_CO_SUY_NIEM_WORD",
            "text": (
                "Cách dùng từ: chọn từ ngữ súc tích, giàu cảm xúc suy niệm thiêng liêng, lược bỏ chi tiết phụ; dùng hình ảnh khái quát thay cho diễn đạt dài dòng."
            )
        },
        {
            "id": "EP_REPORT_BIEN_CO_SUY_NIEM_AIM",
            "text": (
                "Diễn đạt ý nghĩa: làm nổi bật chiều kích thiêng liêng của biến cố, gắn kết với tâm tình người tham dự."
            )
        },
        #=========================================================kết thúc của biến cố & suy niệm=========================================#
        #=========================================================bắt đầu của Thánh Lễ=========================================#
        {
            "id": "EP_REPORT_THANH_LE_STRUC",
            "text": (
                "bố cục: sắp xếp theo khung Nghi thức hoặc Thánh lễ – Chủ sự (& đồng tế nếu có) – Thành phần tham dự – Tâm tình hoặc ý hướng. Nếu thời gian hoặc địa điểm là lần đầu xuất hiện, đặt ở mở đầu; nếu đã nêu ngay trước đó, có thể lược để tránh lặp; tránh tường thuật nặng liệt kê  hoặc  phóng đại cảm xúc không có trong nguồn."
            )
        },
        {
            "id": "EP_REPORT_THANH_LE_WORD",
            "text": (
                "Cách dùng từ: ưu tiên từ gợi cảm xúc phụng vụ và hiệp thông; câu ngắn, rõ nhịp; dùng dấu gạch ngang để bổ sung vai trò; lược bỏ diễn đạt hành chính rườm rà."
                "Dùng cấu trúc đồng vị (họ tên ↔ chức vụ ↔ định danh dòng tu (nếu có) ↔ đơn vị mục vụ) bằng dấu gạch ngang; bảo đảm song song ngữ pháp khi liệt kê."
            )
        },
        {
            "id": "EP_REPORT_THANH_LE_TONE", #giọng văn
            "text": (
                "Chuẩn hoá văn phong tin tức Công giáo: trang trọng, súc tích, khách quan; tránh cảm thán;"
                "Luôn sử dụng ngôi thứ ba; Dùng giọng văn trung tính kết hợp với sắc thái mục vụ và hiệp thông"
                "Áp dụng sắc thái trang nghiêm, sốt sắng, mang chiều kích mục vụ; tránh tường thuật khô khan."
            )
        },
        {
            "id": "EP_REPORT_THANH_LE_AIM",
            "text": (
                "Diễn đạt ý nghĩa: nhấn mạnh tinh thần hiệp thông và ý hướng cầu nguyện gắn với mục đích cụ thể của cộng đoàn. Làm nổi bật ý hướng phụng vụ nêu trong nguồn (ví dụ: tạ ơn, cầu xin…); không đổi trọng tâm ý nghĩa."
            )
        },
        {
            "id": "EP_REPORT_THANH_LE_CHECK",
            "text": (
                "Kiểm tra tính chính xác của các dữ kiện: tên người, chức vụ, đơn vị; số lượng tham dự; thời gian, địa điểm; nội dung nghi thức; tránh thêm bớt  hoặc  suy diễn không có trong nguồn."
            )
        },
#=========================================================kết thúc của Thánh Lễ=========================================#
        #========================================================bắt đầu của Bài Giảng=========================================#
        {
            "id": "EP_BAI_GIANG_STRUC",
            "text": (
                "Thứ tự ưu tiên: Khung cảnh (địa điểm hoặc thời gian, nếu có) → Mệnh đề chính (nêu chủ thể giảng; nếu có đối tượng trọng tâm, đặt đồng vị ngắn gọn; tiếp theo là thông điệp trung tâm và (nếu có) một nhóm hành động song song để minh họa thực hành.) → Thông tin thứ cấp (thành phần hoặc diễn tiến hoặc bối cảnh phụ) → Mục đích hoặc Kết quả (chỉ nếu có trong nguồn)."
                "Sắp xếp mạch ý thành các phần rõ ràng, theo khung: Mở ý chính → nêu bối cảnh hoặc thực trạng (nếu có) → mệnh đề hoặc nhận định cốt lõi → lời kêu gọi hoặc đối tượng thực hành → mục tiêu hoặc hoa trái mong muốn."
                "Mỗi ý 1–2 câu, tách câu khi chuỗi liệt kê dài. Tách ý thành nhiều câu thay vì dồn nén chi tiết trong một câu dài."
            )
        },
        {
            "id": "EP_BAI_GIANG_TONE",
            "text": (
                "Giọng văn: giữ sắc thái giảng lễ trang nghiêm, ấm áp, mang tính giáo huấn hoặc mục vụ và khích lệ thực hành; tránh tường thuật khô khan hoặc cảm tính quá mức."
            )
        },
        {
            "id": "EP_BAI_GIANG_WORD",
            "text": (
                "Cách dùng từ: khái quát các danh sách dài thành nhóm; ưu tiên động từ kêu gọi–khích lệ; dùng thuật ngữ thần học hoặc phụng vụ ở mức cần thiết; ưu tiên cấu trúc song song (2–3 vế) thay cho liệt kê dàn trải"
                "nếu nguồn có mệnh đề then chốt, giữ ở dạng trích dẫn; không sáng tác khẩu hiệu hoặc ẩn dụ mới."
            )
        },
        {
            "id": "EP_BAI_GIANG_AIM",
            "text": (
                "Diễn đạt ý nghĩa: làm nổi bật chiều kích thiêng liêng của bài giảng (nuôi dưỡng đức tin, hướng tới đời sống tốt lành), gắn kết với tâm tình người tham dự; theo đúng nội dung nguồn. "
            )
        },
        {
            "id": "EP_BAI_GIANG_CHECK",
            "text": (
                "không thêm hoặc bớt số liệu, không thêm chủ thể mới; không đổi trọng tâm"
            )
        },
        #========================================================kết thúc của Bài Giảng=========================================#
        #=========================================================bắt đầu của Kết từ của tường thuật thánh lễ=========================================#
        {
            "id": "EP_END_THANH_LE_STRUC",
            "text": (
                "Nếu câu về thông điệp thì Tái cấu trúc câu dài thành hai nhịp: (i) thông điệp khích lệ trọng tâm; (ii) câu kết đóng nghi thức, tạo điểm rơi cảm xúc và khép bài tự nhiên."
                "Nếu câu về tri ân ai đó thì Tách–gộp lại mệnh đề để câu đầu nêu hành vi đại diện, câu sau triển khai tri ân cụ thể"
            )
        },
        {
            "id": "EP_END_THANH_LE_WORD",
            "text": (
                "Cách dùng từ: ưu tiên từ gợi cảm xúc phụng vụ và hiệp thông"
                "Thay thế cụm diễn đạt mô tả bằng cụm mang ý nghĩa bao quát và hài hòa hơn, thể hiện chiều sâu nội tâm hơn hình thức."
                "Rút gọn các cụm lặp hoặc ý trùng; dùng động từ chủ động, nhịp câu gọn, mạch lạc. "
                "Tránh liên từ hoặc dấu câu tạo cảm giác rời rạc; thay bằng kết nối tự nhiên."
            )
        },
        {
            "id": "EP_END_THANH_LE_TONE", #giọng văn
            "text": (
                "Chuẩn hoá văn phong tin tức Công giáo: trang trọng, súc tích, khách quan; tránh cảm thán;"
                "Luôn sử dụng ngôi thứ ba; Dùng giọng văn trung tính kết hợp với sắc thái mục vụ và hiệp thông"
                "Chọn những từ ngữ làm tăng tính “mục vụ” và bầu khí phụng vụ"
            )
        },
        {
            "id": "EP_END_THANH_LE_AIM",
            "text": (
                "Diễn đạt ý nghĩa: Làm nổi bật ý nghĩa phụng vụ nêu trong nguồn (ví dụ: tạ ơn, cầu xin…); không đổi trọng tâm ý nghĩa."
                "Nếu chưa có câu kết thể hiện ý nghĩa phụng vụ thì Thêm kết luận mang ý nghĩa phụng vụ để khép lại ý nghĩa của sự kiện."
            )
        },
        {
            "id": "EP_END_THANH_LE_CHECK",
            "text": (
            )
        },
        #========================================================kết thúc của Kết từ của tường thuật thánh lễ=========================================##
        #=========================================================bắt đầu của Kết từ-suy niệm=========================================#
        
        #========================================================kết thúc của Kết từ-suy niệm=========================================##
        #=========================================================bắt đầu của tường thuật hoạt động sau lễ=========================================#
        #========================================================kết thúc của tường thuật hoạt động sau lễ=========================================##
        {
            "id": "EP_BAI_GIANG_STRUC",
            "text": (
                "Thứ tự ưu tiên: Khung cảnh (địa điểm  hoặc  thời gian, nếu có) → Mệnh đề chính (nêu chủ thể giảng; nếu có đối tượng trọng tâm, đặt đồng vị ngắn gọn; tiếp theo là thông điệp trung tâm và (nếu có) một nhóm hành động song song để minh họa thực hành.) → Thông tin thứ cấp (thành phần hoặc diễn tiến hoặc bối cảnh phụ) → Mục đích hoặc Kết quả (chỉ nếu có trong nguồn).sắp xếp mạch ý thành các phần rõ ràng, theo khung:"
                "Mở ý chính → nêu bối cảnh hoặc thực trạng (nếu có) → mệnh đề hoặc nhận định cốt lõi → lời kêu gọi  hoặc  đối tượng thực hành → mục tiêu hoặc hoa trái mong muốn."
                "Mỗi ý 1–2 câu, tách câu khi chuỗi liệt kê dài. Tách ý thành nhiều câu thay vì dồn nén chi tiết trong một câu dài."
            )
        },
        {
            "id": "EP_BAI_GIANG_TONE",
            "text": (
                "Giọng văn: giữ sắc thái giảng lễ trang nghiêm, ấm áp, mang tính giáo huấn hoặc  mục vụ và khích lệ thực hành; tránh tường thuật khô khan  hoặc  cảm tính quá mức."
            )
        },
        {
            "id": "EP_BAI_GIANG_WORD",
            "text": (
                "Cách dùng từ: khái quát các danh sách dài thành nhóm; ưu tiên động từ kêu gọi–khích lệ; dùng thuật ngữ thần học  hoặc  phụng vụ ở mức cần thiết; ưu tiên cấu trúc song song (2–3 vế) thay cho liệt kê dàn trải"
                "nếu nguồn có mệnh đề then chốt, giữ ở dạng trích dẫn; không sáng tác khẩu hiệu hoặc ẩn dụ mới."
            )
        },
        {
            "id": "EP_BAI_GIANG_AIM",
            "text": (
                "Diễn đạt ý nghĩa: làm nổi bật chiều kích thiêng liêng của bài giảng (nuôi dưỡng đức tin, hướng tới đời sống tốt lành), gắn kết với tâm tình người tham dự; theo đúng nội dung nguồn. "
            )
        },
        {
            "id": "EP_BAI_GIANG_CHECK",
            "text": (
                "không thêm hoặc bớt số liệu, không thêm chủ thể mới; không đổi trọng tâm"
            )
        },
    ],

    # 3) Ánh xạ N–N: mỗi label_key -> nhiều edit_prompt_ids
    "map": [
        {
            "label_key": "tittle",
            "edit_prompt_ids": ["EP_TITTLE"]
        },
        {
            "label_key": "mo_bai_tom_tat_thanh_le",
            "edit_prompt_ids": ["EP_STRUC_LEAD", "EP_LEAD_HOI_DOAN_TONE", "EP_LEAD_HOI_DOAN_WORD","EP_LEAD_HOI_DOAN_AIM", "EP_CHUAN_HOA"]
        },
        {
            "label_key": "tuong_thuat_su_kien_bai_giang",
            "edit_prompt_ids": ["EP_BAI_GIANG_STRUC", "EP_BAI_GIANG_TONE", "EP_BAI_GIANG_WORD", "EP_BAI_GIANG_AIM", "EP_CHUAN_HOA", "EP_BAI_GIANG_CHECK"]
        },
        {
            "label_key": "tuong_thuat_su_kien_thanh_le",
            "edit_prompt_ids": ["EP_REPORT_THANH_LE_STRUC", "EP_REPORT_THANH_LE_TONE", "EP_REPORT_THANH_LE_WORD",  "EP_REPORT_THANH_LE_AIM", "EP_CHUAN_HOA", "EP_REPORT_THANH_LE_CHECK"]
        },
         {
            "label_key": "tuong_thuat_su_kien_ngoai_thanh_le",
            "edit_prompt_ids": ["EP_REPORT_THANH_LE_STRUC", "EP_REPORT_THANH_LE_TONE", "EP_REPORT_THANH_LE_WORD", "EP_REPORT_THANH_LE_AIM", "EP_CHUAN_HOA", "EP_REPORT_THANH_LE_CHECK"]
        },
        {
            "label_key": "ket_tu_tuong_thuat_thanh_le",
            "edit_prompt_ids": ["EP_END_THANH_LE_STRUC", "EP_END_THANH_LE_TONE", "EP_END_THANH_LE_WORD", "EP_END_THANH_LE_AIM", "EP_CHUAN_HOA", "EP_END_THANH_LE_CHECK"]
        },
        # {
        #     "label_key": "thong_bao_muc_vu_khan_dong",
        #     "edit_prompt_ids": ["EP_STYLE_TONE", "EP_STYLE_TONE_TLKNKD", "EP_STRUC_LEAD_KNKD", "EP_WORD_LEAD", "EP_CHUAN_HOA"]
        # },
        {
            "label_key": "gioi_thieu_nhan_su",
            "edit_prompt_ids": ["EP_PROFILE_HOI_DOAN_STRUC", "EP_PROFILE_HOI_DOAN_TONE","EP_PROFILE_HOI_DOAN_WORD", "EP_PROFILE_ALL_AIM", "EP_CHUAN_HOA"]
        },
        # {
        #     "label_key": "tuong_thuat_su_kien",
        #     "edit_prompt_ids": ["EP_EVENT_REPORT", "EP_STYLE_TONE", "EP_CHUAN_HOA"]
        # },
        # {
        #     "label_key": "ket_tu_tong_ket",
        #     "edit_prompt_ids": ["EP_CONCLUSION_SUMMARY", "EP_STYLE_TONE"]
        # },
        # {
        #     "label_key": "ket_tu_suy_niem",
        #     "edit_prompt_ids": ["EP_CONCLUSION_REFLECTION", "EP_STYLE_TONE"]
        # },
    ],

    # 4) compose: điều khiển cách ghép quy tắc khi đa nhãn
    "compose": {
        # Khung system chung cho LLM
        "base_system_prompt": (
            "Bạn là biên tập viên tin tức mục vụ. Chỉ trả về nội dung đã chỉnh sửa theo yêu cầu. "
            "Giữ trung thực dữ kiện; có thể bổ sung thông tin nếu đoạn văn chưa có; tôn trọng bối cảnh mục vụ."
        ),

        # Chiến lược **duy nhất** theo yêu cầu của bạn
        "multi_label_strategy": "union",      # lấy HỢP các quy tắc của mọi nhãn
        "deduplicate": True,                  # loại trùng (gặp trước giữ trước)

        # Thứ tự cuối cùng (ổn định): theo bảng ưu tiên toàn cục
        "ordering": "by_global_order",
        "global_prompt_order": [
            "EP_TITTLE",
            "EP_STRUC_LEAD",
            "EP_BAI_GIANG_STRUC",
            "EP_REPORT_THANH_LE_STRUC",
            "EP_END_THANH_LE_STRUC",
            "EP_PROFILE_HOI_DOAN_STRUC",    
            "EP_LEAD_HOI_DOAN_TONE",
            "EP_BAI_GIANG_TONE",
            "EP_REPORT_THANH_LE_TONE", 
            "EP_END_THANH_LE_TONE",
            "EP_PROFILE_HOI_DOAN_TONE",
            "EP_LEAD_HOI_DOAN_WORD",
            "EP_BAI_GIANG_WORD",
            "EP_REPORT_THANH_LE_WORD",
            "EP_END_THANH_LE_WORD",
            "EP_PROFILE_HOI_DOAN_WORD",
            "EP_LEAD_HOI_DOAN_AIM", 
            "EP_BAI_GIANG_AIM",
            "EP_REPORT_THANH_LE_AIM",
            "EP_END_THANH_LE_AIM"
            "EP_PROFILE_ALL_AIM",
            "EP_CHUAN_HOA",
            "EP_BAI_GIANG_CHECK",
            "EP_REPORT_THANH_LE_CHECK",
            "EP_END_THANH_LE_CHECK",
        ]
    }
}
# === Derived label configuration ===
def _normalize_label_name(value):
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFC", value).strip()


_LABEL_NAME_TO_KEY = {}
_LABEL_KEY_TO_NAME = {}
for item in REGISTRY_DICT.get("labels", []):
    key = _normalize_label_name(item.get("key", ""))
    name = _normalize_label_name(item.get("name", ""))
    if key and name and name not in _LABEL_NAME_TO_KEY:
        _LABEL_NAME_TO_KEY[name] = key
        _LABEL_KEY_TO_NAME.setdefault(key, name)

LABEL_NAME_TO_KEY = _LABEL_NAME_TO_KEY
LABEL_KEY_TO_NAME = _LABEL_KEY_TO_NAME
ALLOWED_LABELS_DEFAULT = list(LABEL_NAME_TO_KEY.keys())
print(f"[Config] Nhãn hợp lệ: {ALLOWED_LABELS_DEFAULT}")
