import os
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File

UPLOAD_DIR = Path("/tmp/qdata_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix if file.filename else ""
    name = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / name
    content = await file.read()
    path.write_bytes(content)
    return {"path": str(path), "filename": file.filename}
