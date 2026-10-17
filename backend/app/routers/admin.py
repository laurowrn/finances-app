import json
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import current_admin_user_id
from app.settings import get_settings
from app.runtime_config import EDITABLE_KEYS, SECRET_KEYS, clear_runtime_config, save_runtime_config

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(current_admin_user_id)],
)


class ConfigUpdate(BaseModel):
    value: str | None = Field(default=None, max_length=10000)
    clear: bool = False

STATE_DIR = Path(os.getenv("ADMIN_STATE_DIR", "/run/finances-admin"))
STATUS_FILE = STATE_DIR / "deploy-status.json"
TRIGGER_FILE = STATE_DIR / "deploy.trigger"


def _read_status() -> dict:
    if not STATUS_FILE.exists():
        return {"status": "idle", "message": "Nenhum deploy registrado neste servidor."}
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "unknown", "message": "Não foi possível ler o status do deploy."}


@router.get("/status")
async def deploy_status() -> dict:
    return _read_status()


@router.post("/deploy", status_code=status.HTTP_202_ACCEPTED)
async def trigger_deploy(user_id: str = Depends(current_admin_user_id)) -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if _read_status().get("status") == "running":
        raise HTTPException(status_code=409, detail="Já existe um deploy em andamento")
    now = datetime.now(UTC).isoformat()
    TRIGGER_FILE.write_text(f"requested_by={user_id}\nrequested_at={now}\n", encoding="utf-8")
    return {"status": "queued", "requested_at": now}


@router.get("/config")
async def admin_config() -> dict:
    settings = get_settings()
    return {
        "environment": "production",
        "ai_enabled": settings.ai_enabled,
        "ai_model": settings.anthropic_model if settings.ai_enabled else None,
        "cors_origins": settings.cors_origin_list,
        "values": {
            key: {
                "secret": key in SECRET_KEYS,
                "configured": bool(getattr(settings, key, "")),
                "value": None if key in SECRET_KEYS else getattr(settings, key, ""),
            }
            for key in sorted(EDITABLE_KEYS)
        },
        "note": "Valores secretos nunca são retornados pela API.",
    }


@router.patch("/config/{key}")
async def update_admin_config(key: str, body: ConfigUpdate) -> dict:
    if key not in EDITABLE_KEYS:
        raise HTTPException(status_code=404, detail="Configuração não editável")
    if body.clear:
        await clear_runtime_config(key)
        return {"key": key, "configured": False}
    if body.value is None:
        raise HTTPException(status_code=422, detail="Informe um valor ou use clear")
    try:
        await save_runtime_config(key, body.value)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"key": key, "configured": True}
