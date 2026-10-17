from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import current_user_id
from app.models.enums import ClassifiedBy, Source, StatementType
from app.repositories import imports as batch_repo
from app.repositories import rules as rules_repo
from app.repositories import transactions as tx_repo
from app.schemas.entities import (
    CoverageOut,
    ImportCommitRequest,
    ImportPreview,
    ImportPreviewRow,
    ImportSummary,
)
from app.services.classifier import classify, split_flags
from app.services.dedup import dedup_hash
from app.services.parsers import ParseError, parse_file

router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(current_user_id)])


@router.post("/preview", response_model=ImportPreview)
async def preview_import(
    owner_user_id: str = Form(...),
    source: str | None = Form(None),
    file: UploadFile = File(...),
    statement_start: date | None = Form(None),
    statement_end: date | None = Form(None),
    institution: str | None = Form(None),
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
        dedup_hash(p.date.isoformat(), p.amount_cents, owner_user_id, p.description) for p in parsed
    ]
    existing = await tx_repo.existing_hashes(hashes)

    rows = []
    for p, h in zip(parsed, hashes, strict=True):
        match = classify(p.description, engine_rules)
        is_shared, is_ignored = split_flags(match.split) if match else (True, False)
        rows.append(
            ImportPreviewRow(
                date=p.date,
                description=p.description,
                amount_cents=p.amount_cents,
                category_id=match.category_id if match else None,
                is_shared=is_shared,
                is_ignored=is_ignored,
                classified_by=ClassifiedBy.RULE if match else ClassifiedBy.NONE,
                rule_id=match.rule_id if match else None,
                is_duplicate=h in existing,
            )
        )
    dates = [p.date for p in parsed]
    detected_start = min(dates) if dates else None
    detected_end = max(dates) if dates else None
    if statement_start and statement_end and statement_start > statement_end:
        raise HTTPException(status_code=400, detail="A data inicial deve ser anterior à data final")
    return ImportPreview(
        filename=filename,
        source=resolved_source,
        owner_user_id=owner_user_id,
        rows=rows,
        detected_start=statement_start or detected_start,
        detected_end=statement_end or detected_end,
    )


@router.post("/commit", response_model=ImportSummary)
async def commit_import(body: ImportCommitRequest):
    """Persiste as linhas já revisadas pelo usuário (categoria/divisão confirmadas)."""
    if body.statement_start and body.statement_end and body.statement_start > body.statement_end:
        raise HTTPException(status_code=400, detail="A data inicial deve ser anterior à data final")
    batch_id = await batch_repo.create_batch(
        body.filename, body.source.value, body.owner_user_id, body.statement_type.value,
        body.institution,
        body.statement_start, body.statement_end,
    )
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


@router.get("/batches")
async def batches():
    return await batch_repo.list_batches()


@router.get("/coverage", response_model=CoverageOut)
async def import_coverage(
    owner_user_id: str, statement_type: StatementType, institution: str = "unknown"
):
    return await batch_repo.coverage(owner_user_id, statement_type.value, institution)


def _infer(filename: str) -> Source:
    name = filename.lower()
    if name.endswith(".ofx"):
        return Source.OFX
    if name.endswith(".pdf"):
        return Source.PDF
    return Source.CSV
