# -*- coding: utf-8 -*-
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import os
import json
import uuid
import time
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
import uvicorn

from editor.Registry import PromptRegistry
from editor.docx_load import document_to_big_text
from editor.llm import OpenAIChatLLM, OllamaChatLLM

from finetune_v2 import Config as ConfigV2
from finetune_v2.label_matcher import LabelSemanticIndex, LabelSemanticMatcher, SentenceTransformerEmbedder
from finetune_v2.pipeline import SemanticEditorPipeline

# --- FastAPI setup -------------------------------------------------------
app_v2 = FastAPI(title="MucVu Editor Pipeline API (finetune-v2)", version="2.0.0")


# ====== Schemas ======
class ProcessRequest(BaseModel):
    big_text: Optional[str] = Field(None, description="Chuỗi văn bản (đã ghép đoạn bằng \\n\\n).")
    docx_path: Optional[str] = Field(None, description="Đường dẫn file .docx (nếu chưa ghép big_text).")


class ChunkAudit(BaseModel):
    chunk_id: str
    order: int
    labels: List[str]
    edit_prompt_ids: List[str]
    latency_ms: int


class ProcessResponse(BaseModel):
    final_text: str
    audit: List[ChunkAudit]


class ProcessTextResponse(BaseModel):
    final_text: str


# ====== Helpers ==========================================================
def _make_llm_from_config():
    if getattr(ConfigV2, "USE_OLLAMA", True):
        return OllamaChatLLM(
            model=ConfigV2.OLLAMA_MODEL,
            api_url=ConfigV2.OLLAMA_API_URL,
        )
    if not getattr(ConfigV2, "OPENAI_API_KEY", ""):
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY chưa có trong Config.py.")
    return OpenAIChatLLM(
        model=ConfigV2.OPENAI_MODEL,
        api_key=ConfigV2.OPENAI_API_KEY,
        api_url=ConfigV2.OPENAI_API_URL,
    )


_MATCHER_SINGLETON: Optional[LabelSemanticMatcher] = None


def _load_label_matcher() -> LabelSemanticMatcher:
    global _MATCHER_SINGLETON
    if _MATCHER_SINGLETON is not None:
        return _MATCHER_SINGLETON
    try:
        index = LabelSemanticIndex.load(ConfigV2.FAISS_INDEX_PATH, ConfigV2.FAISS_METADATA_PATH)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Không tìm thấy FAISS index ({exc}). "
                "Vui lòng chuẩn bị mô tả nhãn và chạy `python -m finetune_v2.build_label_index`."
            ),
        ) from exc
    embedder = SentenceTransformerEmbedder(
        ConfigV2.EMBEDDING_MODEL_NAME,
        device=ConfigV2.EMBEDDING_DEVICE,
    )
    _MATCHER_SINGLETON = LabelSemanticMatcher(
        index=index,
        embedder=embedder,
        top_k=ConfigV2.SIMILARITY_TOP_K,
        threshold=ConfigV2.SIMILARITY_THRESHOLD,
    )
    return _MATCHER_SINGLETON


def _run_pipeline(big_text: Optional[str], docx_path: Optional[str]) -> ProcessResponse:
    if big_text and big_text.strip():
        working_text = big_text.strip()
    elif docx_path and docx_path.strip():
        ConfigV2.DOCUMENT = docx_path.strip()
        try:
            working_text = document_to_big_text()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Lỗi đọc .docx: {exc}") from exc
    else:
        raise HTTPException(status_code=400, detail="Thiếu đầu vào. Cần 'big_text' hoặc 'docx_path'.")

    registry = PromptRegistry.from_dict(ConfigV2.REGISTRY_DICT)
    matcher = _load_label_matcher()

    try:
        llm = _make_llm_from_config()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Lỗi khởi tạo LLM: {exc}") from exc

    pipeline = SemanticEditorPipeline(
        editor_llm=llm,
        registry=registry,
        matcher=matcher,
    )

    try:
        final_text, results = pipeline.process(working_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý pipeline: {exc}") from exc

    audit = [
        ChunkAudit(
            chunk_id=result.chunk_id,
            order=result.order,
            labels=result.labels,
            edit_prompt_ids=result.edit_prompt_ids,
            latency_ms=result.latency_ms,
        )
        for result in results
    ]
    return ProcessResponse(final_text=final_text, audit=audit)


# ================= Background job =================
def run_default_pipeline_and_save_v2(job_id: str):
    try:
        start = time.time()
        default_doc = getattr(ConfigV2, "DOCUMENT", "").strip()
        if not default_doc:
            raise RuntimeError("Config.DOCUMENT chưa được cấu hình.")
        result = _run_pipeline(None, default_doc)
        elapsed = round(time.time() - start, 2)
        data = {"status": "done", "elapsed_sec": elapsed, "result": result.dict()}
    except Exception as exc:  # noqa: BLE001
        data = {"status": "error", "message": str(exc)}

    os.makedirs("jobs", exist_ok=True)
    with open(f"jobs/{job_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ====== Endpoints ======
@app_v2.get("/", include_in_schema=False)
def read_root_v2():
    default_doc = getattr(ConfigV2, "DOCUMENT", "").strip()
    if not default_doc:
        raise HTTPException(status_code=400, detail="Config.DOCUMENT chưa được cấu hình.")
    return _run_pipeline(None, default_doc)


@app_v2.get("/favicon.ico", include_in_schema=False)
def favicon_placeholder_v2():
    return Response(status_code=204)


@app_v2.post("/process", response_model=ProcessResponse)
def process_v2(req: ProcessRequest):
    return _run_pipeline(req.big_text, req.docx_path)


@app_v2.post("/process/default", response_model=ProcessTextResponse)
def process_default_v2():
    default_doc = getattr(ConfigV2, "DOCUMENT", "").strip()
    if not default_doc:
        raise HTTPException(status_code=400, detail="Config.DOCUMENT chưa được cấu hình.")
    response = _run_pipeline(None, default_doc)
    return ProcessTextResponse(final_text=response.final_text)


@app_v2.post("/process/default_async")
def process_default_async_v2(background_tasks: BackgroundTasks):
    default_doc = getattr(ConfigV2, "DOCUMENT", "").strip()
    if not default_doc:
        raise HTTPException(status_code=400, detail="Config.DOCUMENT chưa được cấu hình.")

    job_id = str(uuid.uuid4())
    background_tasks.add_task(run_default_pipeline_and_save_v2, job_id)
    return {"job_id": job_id, "status": "processing"}


@app_v2.get("/result/{job_id}")
def get_result_v2(job_id: str):
    path = f"jobs/{job_id}.json"
    if not os.path.exists(path):
        return {"status": "processing"}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app_v2.get("/result/{job_id}/text")
def get_result_text_v2(job_id: str):
    path = f"jobs/{job_id}.json"
    if not os.path.exists(path):
        return Response(content="processing", media_type="text/plain", status_code=202)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    status = data.get("status")
    if status != "done":
        message = data.get("message", "")
        content = message or status or "error"
        http_code = 500 if status == "error" else 202
        return Response(content=content, media_type="text/plain", status_code=http_code)
    result = data.get("result") or {}
    final_text = result.get("final_text", "")
    return Response(content=str(final_text), media_type="text/plain")


if __name__ == "__main__":
    uvicorn.run("api_v2:app_v2", host="0.0.0.0", port=8100, reload=False)

