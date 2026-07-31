from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import current_user_id
from app.models.enums import Source
from app.repositories import imports as batch_repo
from app.repositories import rules as rules_repo
from app.repositories import transactions as tx_repo
from app.schemas.entities import ImportSummary
from app.services.parsers import ParseError, parse_file

router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(current_user_id)])


@router.post("", response_model=ImportSummary)
async def import_file(
    owner_user_id: str = Form(...),
    source: str | None = Form(None),
    file: UploadFile = File(...),
):
    content = await file.read()
    filename = file.filename or "upload"
    src_enum = Source(source) if source else None
    try:
        parsed = parse_file(filename, content, src_enum)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resolved_source = src_enum or _infer(filename)
    batch_id = await batch_repo.create_batch(filename, resolved_source.value, owner_user_id)
    engine_rules = await rules_repo.load_engine_rules()
    counts = await tx_repo.insert_parsed(
        parsed, owner_user_id, resolved_source, batch_id, engine_rules
    )
    await batch_repo.set_counts(batch_id, counts)

    batch = next((b for b in await batch_repo.list_batches() if b["id"] == batch_id), None)
    created_at = batch["created_at"] if batch else None
    return ImportSummary(
        import_batch_id=batch_id,
        filename=filename,
        source=resolved_source,
        owner_user_id=owner_user_id,
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
