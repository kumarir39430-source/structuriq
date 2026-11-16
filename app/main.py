"""StructurIQ API + web UI.  Run:  uvicorn app.main:app --reload"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__, config, storage
from .exporters import EXPORTERS
from .extractors import run_extraction
from .filereader import UnsupportedFile, read_upload
from .schemas import ExportRequest, ExtractRequest

STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.init_db()
    yield


app = FastAPI(title="StructurIQ", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/samples", StaticFiles(directory=Path(__file__).parent.parent / "samples"), name="samples")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__, "llm_enabled": config.LLM_ENABLED, "model": config.ANTHROPIC_MODEL if config.LLM_ENABLED else None}


def _process(text: str, fields: list[str], mode: str) -> dict:
    if not text.strip():
        raise HTTPException(status_code=400, detail="No text found to extract from.")
    result = run_extraction(text, fields, mode)
    result["id"] = storage.save(text, result)
    return result


@app.post("/api/extract")
def extract(req: ExtractRequest):
    return _process(req.text, req.fields, req.mode)


@app.post("/api/extract/file")
async def extract_file(file: UploadFile = File(...), fields: str = Form(""), mode: str = Form("auto")):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 5 MB.")
    if mode not in {"auto", "rules", "llm"}:
        raise HTTPException(status_code=400, detail="mode must be auto, rules or llm")
    try:
        text = read_upload(file.filename or "", data)
    except UnsupportedFile as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:  # corrupted pdf/docx etc.
        raise HTTPException(status_code=422, detail=f"Could not read file: {exc}") from exc
    field_list = [f for f in (x.strip() for x in fields.replace("\n", ",").split(",")) if f]
    result = _process(text, field_list, mode)
    result["source_text"] = text
    return result


@app.post("/api/export")
def export(req: ExportRequest):
    func, media, ext = EXPORTERS[req.format]
    return Response(
        content=func(req.result),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="structuriq-result.{ext}"'},
    )


@app.get("/api/history")
def history():
    return storage.list_items()


@app.get("/api/history/{item_id}")
def history_item(item_id: int):
    item = storage.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@app.delete("/api/history/{item_id}")
def history_delete(item_id: int):
    if not storage.delete(item_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": item_id}
