import hashlib
import re
import unicodedata


def normalize_description(text: str) -> str:
    """Normaliza descrição: minúsculas, sem acentos, sem pontuação, espaços colapsados."""
    text = text or ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def merchant_key(text: str) -> str:
    """Chave de agrupamento por 'merchant': normaliza e remove números/datas soltos."""
    norm = normalize_description(text)
    norm = re.sub(r"\b\d+\b", "", norm)  # remove números isolados (parcelas, ids)
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm or "sem descricao"


def dedup_hash(date_iso: str, amount: float, owner_user_id: str, description: str) -> str:
    """Hash estável para detectar transações duplicadas em extratos sobrepostos."""
    base = f"{date_iso}|{round(amount, 2):.2f}|{owner_user_id}|{normalize_description(description)}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()
