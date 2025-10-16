# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8") 

import os, json, uuid, time
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from pydantic import BaseModel, Field
import uvicorn

from editor import Config
from editor.Registry import PromptRegistry
from editor.pipeline import EditorPipeline
from editor.llm import OpenAIChatLLM, OllamaChatLLM
from editor.docx_load import document_to_big_text

# --- Khá»Ÿi táº¡o FastAPI ---
app = FastAPI(title="MucVu Editor Pipeline API", version="1.4.0")
  

@app.get("/", include_in_schema=False)
def read_root():
    return {"status": "ok", "message": "Use POST /process to run the editor pipeline."}


@app.get("/favicon.ico", include_in_schema=False)
def favicon_placeholder():
    return Response(status_code=204)

# ====== Schemas ======
class ProcessRequest(BaseModel):
    big_text: Optional[str] = Field(None, description="chuỗi văn bản (đã ghép đoạn bằng \\n\\n).")
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


# ====== Helper: Tạo 1 LLM duy nháº¥t theo Config.py ======
def _make_llm_from_Config():
    """Chọn LLM từ Config.py."""
    if getattr(Config, "USE_OLLAMA", True):
        # Dùng Ollama cho cả classifier + editor
        return OllamaChatLLM(
            model=Config.OLLAMA_MODEL,
            api_url=Config.OLLAMA_API_URL,
        )
    # hoặc dùng OpenAI
    if not getattr(Config, "OPENAI_API_KEY", ""):
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY chưa có trong Config.py.")
    return OpenAIChatLLM(
        model=Config.OPENAI_MODEL,
        api_key=Config.OPENAI_API_KEY,
        api_url=Config.OPENAI_API_URL,
    )


def _run_pipeline(big_text: Optional[str], docx_path: Optional[str]) -> ProcessResponse:
    if big_text and big_text.strip():
        working_text = big_text.strip()
    elif docx_path and docx_path.strip():
        Config.DOCUMENT = docx_path.strip()
        try:
            working_text = document_to_big_text()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Loi doc .docx: {e}")
    else:
        raise HTTPException(status_code=400, detail="Thieu dau vao. Can 'big_text' hoac 'docx_path'.")

    registry = PromptRegistry.from_dict(Config.REGISTRY_DICT)

    try:
        llm = _make_llm_from_Config()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Loi khoi tao LLM: {e}")

    pipe = EditorPipeline(classifier_llm=llm, editor_llm=llm, registry=registry)
    try:
        final_text, results = pipe.process(working_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi khi xu ly pipeline: {e}")

    audit = [
        ChunkAudit(
            chunk_id=r.chunk_id,
            order=r.order,
            labels=r.labels,
            edit_prompt_ids=r.edit_prompt_ids,
            latency_ms=r.latency_ms,
        )
        for r in results
    ]
    return ProcessResponse(final_text=final_text, audit=audit)

# ================= Background job ================ #
def run_default_pipeline_and_save(job_id: str):
    try:
        start = time.time()
        default_doc = getattr(Config, "DOCUMENT", "").strip()
        if not default_doc:
            raise Exception("Config.DOCUMENT chưa được cấu hình.")
        result = _run_pipeline(None, default_doc)
        elapsed = round(time.time() - start, 2)
        data = {"status": "done", "elapsed_sec": elapsed, "result": result.dict()}
    except Exception as e:
        data = {"status": "error", "message": str(e)}

    os.makedirs("jobs", exist_ok=True)
    with open(f"jobs/{job_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ====== Endpoints ======
@app.get("/", include_in_schema=False)
def read_root():
    default_doc = getattr(Config, "DOCUMENT", "").strip()
    if not default_doc:
        raise HTTPException(status_code=400, detail="Config.DOCUMENT chua duoc cau hinh.")
    return _run_pipeline(None, default_doc)


@app.get("/favicon.ico", include_in_schema=False)
def favicon_placeholder():
    return Response(status_code=204)


@app.post("/process", response_model=ProcessResponse)
def process(req: ProcessRequest):
    return _run_pipeline(req.big_text, req.docx_path)


@app.post("/process/default", response_model=ProcessTextResponse)
def process_default():
    default_doc = getattr(Config, "DOCUMENT", "").strip()
    if not default_doc:
        raise HTTPException(status_code=400, detail="Config.DOCUMENT chua duoc cau hinh.")
    response = _run_pipeline(None, default_doc)
    return ProcessTextResponse(final_text=response.final_text)


@app.post("/process/default_async")
def process_default_async(background_tasks: BackgroundTasks):
    default_doc = getattr(Config, "DOCUMENT", "").strip()
    if not default_doc:
        raise HTTPException(status_code=400, detail="Config.DOCUMENT chưa được cấu hình.")

    job_id = str(uuid.uuid4())
    background_tasks.add_task(run_default_pipeline_and_save, job_id)
    return {"job_id": job_id, "status": "processing"}

@app.get("/result/{job_id}")
def get_result(job_id: str):
    path = f"jobs/{job_id}.json"
    if not os.path.exists(path):
        return {"status": "processing"}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/result/{job_id}/text")
def get_result_text(job_id: str):
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


#  python api.py
if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)




