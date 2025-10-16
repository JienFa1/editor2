from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
import uvicorn

APP_TITLE = "Docx Upload Gateway V2"
CONFIG_PATH = Path("editor/Config.py").resolve()
TARGET_DIR = Path("editor/data").resolve()

app = FastAPI(title=APP_TITLE, version="2.0.0")


def _rewrite_config_document_literal(raw_literal: str) -> None:
    """Rewrite Config.DOCUMENT assignment to use the provided raw literal."""
    text = CONFIG_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"^DOCUMENT\s*=.*$", re.MULTILINE)
    replacement = f'DOCUMENT =   r"{raw_literal}"'

    if not pattern.search(text):
        raise RuntimeError("Unable to locate DOCUMENT assignment in Config.py")

    CONFIG_PATH.write_text(pattern.sub(lambda _match: replacement, text), encoding="utf-8")


def _update_config_document(new_docx_path: Path) -> None:
    """Rewrite Config.DOCUMENT to point at the newly uploaded DOCX."""
    _rewrite_config_document_literal(str(new_docx_path))


def _build_destination_path(original_name: str) -> Path:
    stem = Path(original_name).stem or "uploaded"
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_stem = re.sub(r"[^A-Za-z0-9_-]", "_", stem)
    filename = f"{safe_stem}_{timestamp}.docx"
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    return TARGET_DIR / filename


@app.get("/health", include_in_schema=False)
def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/upload")
async def upload_docx(
    request: Request,
    filename: str = Query(..., description="Original DOCX file name from n8n workflow."),
) -> Response:
    """
    Receive raw DOCX bytes (application/octet-stream) sent from n8n and store them on disk.

    The n8n workflow must provide the original file name via query param `filename`.
    """
    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename query parameter")

    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    try:
        contents = await request.body()
    except Exception as exc:  # pragma: no cover - FastAPI already raises
        raise HTTPException(status_code=500, detail=f"Failed to read request body: {exc}") from exc

    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    destination = _build_destination_path(filename)
    destination.write_bytes(contents)

    try:
        _update_config_document(destination)
    except RuntimeError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    payload = {
        "detail": "Upload succeeded",
        "document_path": str(destination),
        "stored_bytes": len(contents),
    }
    return JSONResponse(payload)


@app.post("/clear-document")
async def clear_document() -> JSONResponse:
    try:
        _rewrite_config_document_literal("")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return JSONResponse({"detail": "Document reference cleared"})


if __name__ == "__main__":
    uvicorn.run("receive_docx_server_V2:app", host="0.0.0.0", port=9001, reload=False)

