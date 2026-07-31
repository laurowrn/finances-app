from fastapi import APIRouter, Depends

from app.auth import current_user_id
from app.repositories import categories as cat_repo
from app.repositories import transactions as tx_repo
from app.repositories import users as users_repo
from app.schemas.reports import MonthlyReport
from app.services.settlement import TxInput, UserInput, compute_report

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(current_user_id)])


@router.get("/{period}", response_model=MonthlyReport)
async def monthly_report(period: str):
    users = await users_repo.list_users()
    incomes = {i["user_id"]: i["amount"] for i in await users_repo.list_incomes(period)}
    user_inputs = [
        UserInput(
            id=u["id"],
            name=u["name"],
            income=incomes.get(u["id"], u.get("base_salary", 0.0)),
        )
        for u in users
    ]

    categories = {c["id"]: c["name"] for c in await cat_repo.list_categories()}
    tx_inputs = [
        TxInput(
            owner_user_id=t["owner_user_id"],
            amount=t["amount"],
            is_shared=t["is_shared"],
            category_id=t.get("category_id"),
            category_name=categories.get(t.get("category_id"), "Sem categoria"),
        )
        for t in await tx_repo.transactions_for_report(period)
    ]

    return compute_report(period, user_inputs, tx_inputs)
