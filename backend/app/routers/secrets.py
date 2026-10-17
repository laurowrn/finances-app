import re
from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import current_admin_user_id
from app.db import get_db
from app.runtime_config import encrypt_secret

router = APIRouter(
    prefix="/admin/secrets",
    tags=["admin-secrets"],
    dependencies=[Depends(current_admin_user_id)],
)

NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


class SecretCreate(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    value: str = Field(min_length=1, max_length=10000)
    description: str = Field(default="", max_length=500)


class SecretUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=64)
    value: str | None = Field(default=None, min_length=1, max_length=10000)
    description: str | None = Field(default=None, max_length=500)


def _name(value: str) -> str:
    normalized = value.strip().upper()
    if not NAME_RE.fullmatch(normalized):
        raise HTTPException(
            status_code=422,
            detail="Nome deve usar apenas A-Z, números e _, começando por uma letra",
        )
    return normalized


def _out(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "description": doc.get("description", ""),
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
    }


@router.get("")
async def list_secrets() -> list[dict]:
    docs = await get_db().secrets.find({}, {"ciphertext": 0}).sort("name", 1).to_list(length=500)
    return [_out(doc) for doc in docs]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_secret(body: SecretCreate) -> dict:
    name = _name(body.name)
    now = datetime.now(UTC)
    if await get_db().secrets.find_one({"name": name}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Já existe um secret com esse nome")
    doc = {
        "_id": ObjectId(),
        "name": name,
        "description": body.description.strip(),
        "ciphertext": encrypt_secret(body.value),
        "created_at": now,
        "updated_at": now,
    }
    await get_db().secrets.insert_one(doc)
    return _out(doc)


@router.patch("/{secret_id}")
async def update_secret(secret_id: str, body: SecretUpdate) -> dict:
    try:
        oid = ObjectId(secret_id)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(status_code=422, detail="ID de secret inválido") from exc
    current = await get_db().secrets.find_one({"_id": oid})
    if current is None:
        raise HTTPException(status_code=404, detail="Secret não encontrado")
    changes: dict = {"updated_at": datetime.now(UTC)}
    if body.name is not None:
        name = _name(body.name)
        duplicate = await get_db().secrets.find_one({"name": name, "_id": {"$ne": oid}}, {"_id": 1})
        if duplicate:
            raise HTTPException(status_code=409, detail="Já existe um secret com esse nome")
        changes["name"] = name
    if body.value is not None:
        changes["ciphertext"] = encrypt_secret(body.value)
    if body.description is not None:
        changes["description"] = body.description.strip()
    await get_db().secrets.update_one({"_id": oid}, {"$set": changes})
    updated = await get_db().secrets.find_one({"_id": oid})
    return _out(updated)


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(secret_id: str) -> None:
    try:
        oid = ObjectId(secret_id)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(status_code=422, detail="ID de secret inválido") from exc
    result = await get_db().secrets.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Secret não encontrado")
