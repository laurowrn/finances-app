import json
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import current_admin_user_id
from app.settings import get_settings

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(current_admin_user_id)],
)

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
        "secrets": {
            "jwt_secret": True,
            "login_password": bool(settings.login_password),
            "anthropic_api_key": bool(settings.anthropic_api_key),
        },
        "note": "Valores secretos nunca são retornados pela API.",
    }
