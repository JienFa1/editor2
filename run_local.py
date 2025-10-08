# run_local.py
# -*- coding: utf-8 -*-
<<<<<<< HEAD
=======
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

>>>>>>> b879383 (init: push code từ máy dùng chung)
"""
Chạy pipeline trực tiếp từ dòng lệnh (KHÔNG cần curl).
- Nếu Config.DOCUMENT có đường dẫn .docx hợp lệ → đọc file Word.
- Nếu không, bạn có thể gán BIG_TEXT ngay trong file này (demo).
- Provider được chọn theo Config.USE_OLLAMA (có thể in ra để kiểm tra).

Yêu cầu: bạn đã cấu hình trong editor_pipeline/Config.py:
  USE_OLLAMA, OLLAMA_MODEL, OLLAMA_API_URL, OPENAI_MODEL, OPENAI_API_URL, OPENAI_API_KEY
"""

<<<<<<< HEAD
import Config
from Registry import PromptRegistry
from pipeline import EditorPipeline
from llm import OpenAIChatLLM, OllamaChatLLM
from docx_load import document_to_big_text, paragraphs_to_big_text
from export_local import save_final_text_txt
=======
from editor import Config
from editor.Registry import PromptRegistry
from editor.pipeline import EditorPipeline
from editor.llm import OpenAIChatLLM, OllamaChatLLM
from editor.docx_load import document_to_big_text, paragraphs_to_big_text
from editor.export_local import save_final_text_txt
>>>>>>> b879383 (init: push code từ máy dùng chung)

def choose_llm():
    if getattr(Config, "USE_OLLAMA", True):
        print("[Runner] Provider: OLLAMA")
        return OllamaChatLLM(model=Config.OLLAMA_MODEL, api_url=Config.OLLAMA_API_URL)
    else:
        print("[Runner] Provider: OPENAI")
        if not Config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY chưa được đặt trong Config.py")
        return OpenAIChatLLM(model=Config.OPENAI_MODEL, api_key=Config.OPENAI_API_KEY, api_url=Config.OPENAI_API_URL)

def load_input_text() -> str:
    # Ưu tiên đọc từ .docx nếu DOCUMENT có đường dẫn
    if isinstance(Config.DOCUMENT, str) and Config.DOCUMENT.strip():
        print(f"[Runner] Đọc .docx từ: {Config.DOCUMENT}")
        return document_to_big_text()
    # Hoặc bạn có thể đặt demo BIG_TEXT tại đây (nếu chưa có file .docx)
    print("[Runner] Không thấy đường dẫn .docx trong Config.DOCUMENT → dùng BIG_TEXT demo.")
    big_text_demo = paragraphs_to_big_text([
        "Giáo xứ ABC thông báo chương trình tĩnh tâm Chúa nhật 19/10 tại Nhà thờ XYZ.",
        "Đồng thời, cha Phêrô được bổ nhiệm làm phụ tá từ ngày 01/11.",
        "Xin cộng đoàn hiệp ý cầu nguyện và tham dự đông đủ."
    ])
    return big_text_demo

def main():
    # 1) Chuẩn bị llm & registry
    llm = choose_llm()
    registry = PromptRegistry.from_dict(Config.REGISTRY_DICT)

    # 2) Tải dữ liệu đầu vào
    big_text = load_input_text()

    # 3) Chạy pipeline (cùng 1 llm cho classifier + editor, CHẠY TUẦN TỰ)
    pipe = EditorPipeline(classifier_llm=llm, editor_llm=llm, registry=registry)
    final_text, audit = pipe.process(big_text)

    # 4) In kết quả
    print("\n=== FINAL TEXT ===\n")
    print(final_text)

    print("\n=== AUDIT ===")
    for r in audit:
        print({
            "chunk_id": r.chunk_id,
            "order": r.order,
            "labels": r.labels,
            "edit_prompts": r.edit_prompt_ids,
            "latency_ms": r.latency_ms
        })
    save_final_text_txt(final_text, out_path="./outputs/result.txt")

if __name__ == "__main__":
    main()