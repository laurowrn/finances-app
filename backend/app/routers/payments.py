from fastapi import APIRouter, Depends

from app.auth import current_user_id
from app.repositories import payments as pay_repo
from app.schemas.entities import PaymentCreate, PaymentOut

router = APIRouter(prefix="/payments", tags=["payments"], dependencies=[Depends(current_user_id)])


@router.get("", response_model=list[PaymentOut])
async def list_payments(period: str | None = None):
    return [PaymentOut(**p) for p in await pay_repo.list_payments(period)]


@router.post("", response_model=PaymentOut)
async def create_payment(body: PaymentCreate):
    doc = await pay_repo.create_payment(body.model_dump())
    return PaymentOut(**doc)


@router.delete("/{payment_id}", status_code=204)
async def delete_payment(payment_id: str):
    await pay_repo.delete_payment(payment_id)
