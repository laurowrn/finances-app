from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user_id
from app.repositories import transactions as repo
from app.schemas.entities import TransactionCreate, TransactionOut, TransactionUpdate

router = APIRouter(
    prefix="/transactions", tags=["transactions"], dependencies=[Depends(current_user_id)]
)


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    period: str | None = None,
    owner_user_id: str | None = None,
    category_id: str | None = None,
    only_unclassified: bool = False,
):
    docs = await repo.list_transactions(period, owner_user_id, category_id, only_unclassified)
    return [TransactionOut(**d) for d in docs]


@router.get("/unmatched-groups")
async def unmatched_groups():
    return await repo.unmatched_groups()


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(body: TransactionCreate):
    return TransactionOut(**await repo.create_manual(body.model_dump()))


@router.patch("/{tx_id}", response_model=TransactionOut)
async def update_transaction(tx_id: str, body: TransactionUpdate):
    d = await repo.update_transaction(tx_id, body.model_dump(exclude_none=True))
    if d is None:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    return TransactionOut(**d)


@router.delete("/{tx_id}", status_code=204)
async def delete_transaction(tx_id: str):
    await repo.delete_transaction(tx_id)
