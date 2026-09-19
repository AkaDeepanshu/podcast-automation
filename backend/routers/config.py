"""GET/PUT /api/config — read/write config.yaml + speakers.yaml."""

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config_loader import PROJECT_ROOT

router = APIRouter(prefix="/api/config", tags=["config"])

CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
SPEAKERS_PATH = PROJECT_ROOT / "config" / "speakers.yaml"


class AppConfigPayload(BaseModel):
    config: dict = Field(..., description="Contents of config/config.yaml")
    speakers: dict = Field(..., description="The speakers map from speakers.yaml")


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Missing file: {path.name}")
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail=f"Invalid YAML in {path.name}")
    return data


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(
            data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


@router.get("")
def get_config():
    config = _read_yaml(CONFIG_PATH)
    speakers_doc = _read_yaml(SPEAKERS_PATH)
    speakers = speakers_doc.get("speakers", speakers_doc)
    return {"config": config, "speakers": speakers}


@router.put("")
def put_config(body: AppConfigPayload):
    if "paths" not in body.config:
        raise HTTPException(status_code=400, detail="config.paths is required")
    if not isinstance(body.speakers, dict) or not body.speakers:
        raise HTTPException(status_code=400, detail="speakers map is required")

    _write_yaml(CONFIG_PATH, body.config)
    _write_yaml(SPEAKERS_PATH, {"speakers": body.speakers})
    return {"status": "ok"}
