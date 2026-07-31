from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import current_user_id
from app.models.enums import ClassifiedBy, Source, Split
from app.repositories import imports as batch_repo
from app.repositories import rules as rules_repo
from app.repositories import transactions as tx_repo
from app.schemas.entities import (
    ImportCommitRequest,
    ImportPreview,
    ImportPreviewRow,
    ImportSummary,
)
from app.services.classifier import classify
from app.services.dedup import dedup_hash
from app.services.parsers import ParseError, parse_file

router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(current_user_id)])


@router.post("/preview", response_model=ImportPreview)
async def preview_import(
    owner_user_id: str = Form(...),
    source: str | None = Form(None),
    file: UploadFile = File(...),
):
    """Parseia o arquivo e aplica as regras, sem gravar nada — o usuário revisa
    e só persiste de fato via /imports/commit."""
    content = await file.read()
    filename = file.filename or "upload"
    src_enum = Source(source) if source else None
    try:
        parsed = parse_file(filename, content, src_enum)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resolved_source = src_enum or _infer(filename)
    engine_rules = await rules_repo.load_engine_rules()
    hashes = [
        dedup_hash(p.date.isoformat(), p.amount, owner_user_id, p.description) for p in parsed
    ]
    existing = await tx_repo.existing_hashes(hashes)

    rows = []
    for p, h in zip(parsed, hashes, strict=True):
        match = classify(p.description, engine_rules)
        rows.append(
            ImportPreviewRow(
                date=p.date,
                description=p.description,
                amount=p.amount,
                category_id=match.category_id if match else None,
                is_shared=(match.split == Split.SHARED) if match else True,
                classified_by=ClassifiedBy.RULE if match else ClassifiedBy.NONE,
                rule_id=match.rule_id if match else None,
                is_duplicate=h in existing,
            )
        )
    return ImportPreview(
        filename=filename, source=resolved_source, owner_user_id=owner_user_id, rows=rows
    )


@router.post("/commit", response_model=ImportSummary)
async def commit_import(body: ImportCommitRequest):
    """Persiste as linhas já revisadas pelo usuário (categoria/divisão confirmadas)."""
    batch_id = await batch_repo.create_batch(body.filename, body.source.value, body.owner_user_id)
    counts = await tx_repo.insert_reviewed(body.rows, body.owner_user_id, body.source, batch_id)
    await batch_repo.set_counts(batch_id, counts)

    batch = next((b for b in await batch_repo.list_batches() if b["id"] == batch_id), None)
    created_at = batch["created_at"] if batch else None
    return ImportSummary(
        import_batch_id=batch_id,
        filename=body.filename,
        source=body.source,
        owner_user_id=body.owner_user_id,
        created_at=created_at,
        **counts,
    )


def _infer(filename: str) -> Source:
    name = filename.lower()
    if name.endswith(".ofx"):
        return Source.OFX
    if name.endswith(".pdf"):
        return Source.PDF
    return Source.CSV
