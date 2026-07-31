from datetime import date

from bson import ObjectId
from bson.errors import InvalidId


def period_of(d: date) -> str:
    return d.strftime("%Y-%m")


def oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise ValueError(f"id inválido: {value}") from exc


def is_oid(value: str | None) -> bool:
    return bool(value) and ObjectId.is_valid(value)


def doc_out(doc: dict | None) -> dict | None:
    """Converte _id ObjectId -> id str (raso)."""
    if doc is None:
        return None
    out = dict(doc)
    _id = out.pop("_id", None)
    if _id is not None:
        out["id"] = str(_id)
    return out
