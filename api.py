# -*- coding: utf-8 -*-
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import json
import os
import time
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
import uvicorn

from editor import Config
from editor.Registry import PromptRegistry
from editor.docx_load import ParagraphRecord, document_to_big_text_with_mapping
from editor.export_local import save_document_with_edits
from editor.llm import OpenAIChatLLM, OllamaChatLLM
from editor.pipeline import EditorPipeline

from finetune_v2.docx_utils import build_paragraph_updates

# --- FastAPI setup -------------------------------------------------------
app = FastAPI(title="MucVu Editor Pipeline API", version="1.5.0")


class ProcessRequest(BaseModel):
    big_text: Optional[str] = Field(None, description="Chuoi van ban (da ghep doan bang \\n\\n).")
    docx_path: Optional[str] = Field(None, description="Duong dan file .docx (neu chua ghep big_text).")


class ChunkAudit(BaseModel):
    chunk_id: str
    order: int
    labels: List[str]
    edit_prompt_ids: List[str]
    latency_ms: int


class ProcessResponse(BaseModel):
    final_text: str
    audit: List[ChunkAudit]
    docx_path: Optional[str] = Field(None, description="Duong dan file DOCX da duoc chinh sua.")


class ProcessTextResponse(BaseModel):
    final_text: str


def _make_llm_from_config():
    if getattr(Config, "USE_OLLAMA", True):
        return OllamaChatLLM(
            model=Config.OLLAMA_MODEL,
            api_url=Config.OLLAMA_API_URL,
        )
    if not getattr(Config, "OPENAI_API_KEY", ""):
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY chua co trong Config.py.")
    return OpenAIChatLLM(
        model=Config.OPENAI_MODEL,
        api_key=Config.OPENAI_API_KEY,
        api_url=Config.OPENAI_API_URL,
    )


def _resolve_docx_context(docx_path: Optional[str]) -> Tuple[str, Optional[Path], Optional[Tuple[object, List[ParagraphRecord]]]]:
    if docx_path and docx_path.strip():
        target = Path(docx_path.strip()).expanduser().resolve()
        Config.DOCUMENT = str(target)
    else:
        default_doc = getattr(Config, "DOCUMENT", "").strip()
        if not default_doc:
            return "", None, None
        Config.DOCUMENT = default_doc
        target = Path(default_doc).expanduser().resolve()

    try:
        big_text, document, paragraphs = document_to_big_text_with_mapping()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Loi doc .docx: {exc}") from exc

    return big_text, Path(Config.DOCUMENT), (document, paragraphs)


def _run_pipeline(big_text: Optional[str], docx_path: Optional[str]) -> ProcessResponse:
    document_context: Optional[Tuple[object, List[ParagraphRecord]]] = None
    docx_output_path: Optional[Path] = None

    if big_text and big_text.strip():
        working_text = big_text.strip()
    else:
        working_text, resolved_path, context = _resolve_docx_context(docx_path)
        if not working_text:
            raise HTTPException(status_code=400, detail="Thieu dau vao. Can 'big_text' hoac 'docx_path'.")
        document_context = context
        if resolved_path is not None:
            Config.DOCUMENT = str(resolved_path)

    registry = PromptRegistry.from_dict(Config.REGISTRY_DICT)

    try:
        llm = _make_llm_from_config()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Loi khoi tao LLM: {exc}") from exc

    pipeline = EditorPipeline(classifier_llm=llm, editor_llm=llm, registry=registry)

    try:
        final_text, results = pipeline.process(working_text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Loi khi xu ly pipeline: {exc}") from exc

    if document_context is not None:
        document, paragraphs = document_context
        paragraph_updates = build_paragraph_updates(results, paragraphs)
        docx_output_path = Path("outputs/result_v1.docx").resolve()
        save_document_with_edits(document, paragraph_updates, out_path=str(docx_output_path))

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
    return ProcessResponse(
        final_text=final_text,
        audit=audit,
        docx_path=str(docx_output_path) if docx_output_path else None,
    )


def run_default_pipeline_and_save(job_id: str):
    try:
        start = time.time()
        default_doc = getattr(Config, "DOCUMENT", "").strip()
        if not default_doc:
            raise RuntimeError("Config.DOCUMENT chua duoc cau hinh.")
        result = _run_pipeline(None, default_doc)
        elapsed = round(time.time() - start, 2)
        data = {"status": "done", "elapsed_sec": elapsed, "result": result.dict()}
    except Exception as exc:  # noqa: BLE001
        data = {"status": "error", "message": str(exc)}

    os.makedirs("jobs", exist_ok=True)
    with open(f"jobs/{job_id}.json", "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


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
        raise HTTPException(status_code=400, detail="Config.DOCUMENT chua duoc cau hinh.")

    job_id = str(uuid.uuid4())
    background_tasks.add_task(run_default_pipeline_and_save, job_id)
    return {"job_id": job_id, "status": "processing"}


@app.get("/result/{job_id}")
def get_result(job_id: str):
    path = Path("jobs") / f"{job_id}.json"
    if not path.exists():
        return {"status": "processing"}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@app.get("/result/{job_id}/text")
def get_result_text(job_id: str):
    path = Path("jobs") / f"{job_id}.json"
    if not path.exists():
        return Response(content="processing", media_type="text/plain", status_code=202)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
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
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
