from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user_id
from app.repositories import users as users_repo
from app.schemas.auth import UserOut
from app.schemas.entities import IncomeOut, IncomeUpsert, UserUpdate

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(current_user_id)])


@router.get("", response_model=list[UserOut])
async def list_users():
    return [
        UserOut(id=u["id"], name=u["name"], base_salary_cents=u.get("base_salary_cents", 0))
        for u in await users_repo.list_users()
    ]


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: str, body: UserUpdate):
    u = await users_repo.update_user(user_id, body.model_dump(exclude_none=True))
    if u is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return UserOut(id=u["id"], name=u["name"], base_salary_cents=u.get("base_salary_cents", 0))


# ---------- incomes (salário por período) ----------


@router.get("/incomes/{period}", response_model=list[IncomeOut])
async def list_incomes(period: str):
    return [IncomeOut(**i) for i in await users_repo.list_incomes(period)]


@router.put("/incomes", response_model=IncomeOut)
async def upsert_income(body: IncomeUpsert):
    await users_repo.upsert_income(body.user_id, body.period, body.amount_cents)
    return IncomeOut(user_id=body.user_id, period=body.period, amount_cents=body.amount_cents)
