from fastapi import APIRouter, HTTPException, status

from app.auth import create_access_token
from app.repositories import users as users_repo
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/users", response_model=list[UserOut])
async def public_users():
    """Lista pública (id + nome) para a tela de login escolher quem está entrando."""
    return [
        UserOut(id=u["id"], name=u["name"], base_salary_cents=u.get("base_salary_cents", 0))
        for u in await users_repo.list_users()
    ]


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    settings = get_settings()
    user = await users_repo.get_user(body.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    if body.password != settings.login_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Senha incorreta")
    token = create_access_token(user["id"])
    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user["id"],
            name=user["name"],
            base_salary_cents=user.get("base_salary_cents", 0),
        ),
    )
