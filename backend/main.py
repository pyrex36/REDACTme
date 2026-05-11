"""
main.py  –  FastAPI redaction service
Run:  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import tempfile, shutil, os, logging
from pathlib import Path

from redactor import redact_pdf_bytes, RedactionVerificationError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("api")

app = FastAPI(title="Bank-Grade PDF Redaction API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # tighten to your frontend origin in production
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.post("/redact")
async def redact_endpoint(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Only PDF files are accepted.")

    raw = await file.read()
    if len(raw) > 50 * 1024 * 1024:   # 50 MB guard
        raise HTTPException(status_code=413, detail="File too large (max 50 MB).")

    try:
        redacted_bytes, summary = redact_pdf_bytes(raw)
    except RedactionVerificationError as e:
        log.error("Verification failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Verification failed: {e}")
    except Exception as e:
        log.exception("Redaction error")
        raise HTTPException(status_code=500, detail=str(e))

    stem = Path(file.filename or "document").stem
    out_name = f"{stem}_redacted.pdf"

    return Response(
        content=redacted_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{out_name}"',
            "X-Redaction-Count": str(summary["total"]),
            "X-Redaction-Summary": _summary_header(summary),
        },
    )


def _summary_header(s: dict) -> str:
    parts = [f"{v} {k}" for k, v in s.items() if k != "total" and v > 0]
    return ", ".join(parts) if parts else "none"


@app.get("/health")
def health():
    return {"status": "ok"}
