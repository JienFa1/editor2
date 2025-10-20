# -*- coding: utf-8 -*-
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

"""
Run the editor pipeline locally without FastAPI.
"""

from pathlib import Path
from typing import List, Optional, Tuple

from editor import Config
from editor.Registry import PromptRegistry
from editor.docx_load import ParagraphRecord, document_to_big_text_with_mapping, paragraphs_to_big_text
from editor.export_local import save_document_with_edits, save_final_text_txt
from editor.llm import OpenAIChatLLM, OllamaChatLLM
from editor.pipeline import EditorPipeline

from finetune_v2.docx_utils import build_paragraph_updates


def choose_llm():
    if getattr(Config, "USE_OLLAMA", True):
        print("[Runner] Provider: OLLAMA")
        return OllamaChatLLM(model=Config.OLLAMA_MODEL, api_url=Config.OLLAMA_API_URL)
    print("[Runner] Provider: OPENAI")
    if not Config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY chua duoc dat trong Config.py")
    return OpenAIChatLLM(
        model=Config.OPENAI_MODEL,
        api_key=Config.OPENAI_API_KEY,
        api_url=Config.OPENAI_API_URL,
    )


def load_input_text() -> Tuple[str, Optional[object], List[ParagraphRecord]]:
    """
    Return big_text along with optional DOCX context (document, paragraphs).
    """
    doc_path = getattr(Config, "DOCUMENT", "")
    if isinstance(doc_path, str) and doc_path.strip():
        print(f"[Runner] Doc DOCX tu: {doc_path}")
        big_text, document, paragraphs = document_to_big_text_with_mapping()
        return big_text, document, paragraphs

    print("[Runner] Khong thay duong dan .docx trong Config.DOCUMENT -> dung BIG_TEXT demo.")
    demo_text = paragraphs_to_big_text(
        [
            "Giao xu ABC thong bao chuong trinh tinh tam Chu Nhat 19/10 tai Nha tho XYZ.",
            "Dong thoi, cha Phero duoc bo nhiem lam pho te tu ngay 01/11.",
            "Xin cong doan hiep y cau nguyen va tham du dong dao.",
        ]
    )
    return demo_text, None, []


def main():
    llm = choose_llm()
    registry = PromptRegistry.from_dict(Config.REGISTRY_DICT)

    big_text, document, paragraphs = load_input_text()

    pipeline = EditorPipeline(classifier_llm=llm, editor_llm=llm, registry=registry)
    final_text, audit = pipeline.process(big_text)

    print("\n=== FINAL TEXT ===\n")
    print(final_text)

    print("\n=== AUDIT ===")
    for entry in audit:
        print(
            {
                "chunk_id": entry.chunk_id,
                "order": entry.order,
                "labels": entry.labels,
                "edit_prompts": entry.edit_prompt_ids,
                "latency_ms": entry.latency_ms,
            }
        )

    save_final_text_txt(final_text, out_path="./outputs/result.txt")
    print("[Runner] Final text saved to outputs/result.txt")

    if document is not None and paragraphs:
        paragraph_updates = build_paragraph_updates(audit, paragraphs)
        docx_output_path = Path("./outputs/result_local.docx").resolve()
        save_document_with_edits(document, paragraph_updates, out_path=str(docx_output_path))
        print(f"[Runner] Edited DOCX saved to {docx_output_path}")


if __name__ == "__main__":
    main()
