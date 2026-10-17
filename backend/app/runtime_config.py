from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken

from app.db import get_db
from app.settings import get_settings

SECRET_KEYS = {"jwt_secret", "login_password", "anthropic_api_key"}
EDITABLE_KEYS = SECRET_KEYS | {"anthropic_model", "cors_origins"}


def _fernet() -> Fernet:
    key = get_settings().secrets_encryption_key.strip()
    if not key:
        raise RuntimeError("SECRETS_ENCRYPTION_KEY não configurada")
    return Fernet(key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Não foi possível descriptografar o secret") from exc


def _serialize(key: str, value: str) -> dict:
    if key in SECRET_KEYS:
        return {"kind": "secret", "value": encrypt_secret(value)}
    return {"kind": "plain", "value": value}


def _deserialize(key: str, entry: dict) -> str:
    value = str(entry.get("value", ""))
    if key not in SECRET_KEYS:
        return value
    try:
        return decrypt_secret(value)
    except RuntimeError as exc:
        raise RuntimeError(f"Não foi possível descriptografar {key}") from exc


async def load_runtime_config() -> None:
    doc = await get_db().app_config.find_one({"_id": "runtime"})
    if not doc:
        return
    settings = get_settings()
    for key, entry in doc.get("values", {}).items():
        if key in EDITABLE_KEYS:
            setattr(settings, key, _deserialize(key, entry))


async def save_runtime_config(key: str, value: str) -> None:
    if key not in EDITABLE_KEYS:
        raise ValueError("Configuração não editável")
    await get_db().app_config.update_one(
        {"_id": "runtime"},
        {
            "$set": {
                f"values.{key}": _serialize(key, value),
                "updated_at": datetime.now(UTC),
            }
        },
        upsert=True,
    )
    setattr(get_settings(), key, value)


async def clear_runtime_config(key: str) -> None:
    if key not in EDITABLE_KEYS:
        raise ValueError("Configuração não editável")
    await get_db().app_config.update_one(
        {"_id": "runtime"},
        {"$unset": {f"values.{key}": ""}, "$set": {"updated_at": datetime.now(UTC)}},
    )
