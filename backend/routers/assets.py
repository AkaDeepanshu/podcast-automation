"""Speaker/logo asset upload and serve endpoints (data/assets/)."""

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from core.config_loader import PROJECT_ROOT, load_config

router = APIRouter(prefix="/api/assets", tags=["assets"])

ALLOWED = {
    "speaker_a": "speaker_a.png",
    "speaker_b": "speaker_b.png",
    "logo": "logo.png",
}


def _assets_dir() -> Path:
    return PROJECT_ROOT / load_config()["paths"].get("assets_dir", "data/assets")


def _asset_path(name: str) -> Path:
    if name not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown asset. Allowed: {', '.join(ALLOWED)}",
        )
    return _assets_dir() / ALLOWED[name]


async def _save_png(name: str, file: UploadFile) -> dict:
    if file.content_type and file.content_type not in (
        "image/png",
        "image/x-png",
        "application/octet-stream",
    ):
        # Still allow if filename ends with .png
        filename = (file.filename or "").lower()
        if not filename.endswith(".png"):
            raise HTTPException(status_code=400, detail="Only PNG uploads are supported")

    dest = _asset_path(name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    # Basic PNG magic check
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="File is not a valid PNG")
    dest.write_bytes(data)
    return {"name": name, "path": str(dest.relative_to(PROJECT_ROOT)), "bytes": len(data)}


@router.post("/speaker_a")
async def upload_speaker_a(file: UploadFile = File(...)):
    return await _save_png("speaker_a", file)


@router.post("/speaker_b")
async def upload_speaker_b(file: UploadFile = File(...)):
    return await _save_png("speaker_b", file)


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    return await _save_png("logo", file)


@router.get("/{name}")
def get_asset(name: str):
    path = _asset_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Asset not found: {name}")
    return FileResponse(path, media_type="image/png", filename=path.name)
