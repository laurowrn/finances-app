import httpx
import logging
from fastapi import APIRouter, HTTPException, status
from jose import jwk, jwt

from app.auth import create_access_token
from app.repositories import users as users_repo
from app.schemas.auth import LoginRequest, OidcLoginRequest, TokenResponse, UserOut
from app.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.get("/oidc/config")
async def oidc_config():
    settings = get_settings()
    return {
        "enabled": settings.oidc_enabled and bool(settings.oidc_issuer_url and settings.oidc_client_id),
        "authorization_endpoint": f"{settings.oidc_issuer_url.rstrip('/')}/protocol/openid-connect/auth",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
    }


@router.post("/oidc/login", response_model=TokenResponse)
async def oidc_login(body: OidcLoginRequest):
    settings = get_settings()
    if not settings.oidc_enabled:
        raise HTTPException(status_code=404, detail="Login Google ainda não está habilitado")
    if body.redirect_uri != settings.oidc_redirect_uri:
        raise HTTPException(status_code=400, detail="Redirect URI inválido")
    token_url = f"{settings.oidc_internal_issuer_url.rstrip('/')}/protocol/openid-connect/token"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.oidc_client_id,
                    "code": body.code,
                    "redirect_uri": body.redirect_uri,
                    "code_verifier": body.code_verifier,
                },
            )
            response.raise_for_status()
            token_data = response.json()
            id_token = token_data.get("id_token")
            if not id_token:
                raise ValueError("id_token ausente")
            discovery = await client.get(f"{settings.oidc_internal_issuer_url.rstrip('/')}/.well-known/openid-configuration")
            discovery.raise_for_status()
            # Fetch JWKS through the internal issuer as well. The public issuer
            # is used for token validation, but the container should not depend
            # on a Tailscale hairpin to retrieve Keycloak's signing keys.
            jwks_url = f"{settings.oidc_internal_issuer_url.rstrip('/')}/protocol/openid-connect/certs"
            jwks = (await client.get(jwks_url)).json()["keys"]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("OIDC token exchange failed: %s", type(exc).__name__)
        raise HTTPException(status_code=401, detail="Não foi possível validar o login Google") from exc

    try:
        header = jwt.get_unverified_header(id_token)
        key_data = next(key for key in jwks if key["kid"] == header["kid"])
        claims = jwt.decode(
            id_token,
            jwk.construct(key_data),
            algorithms=[header.get("alg", "RS256")],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer_url,
        )
    except (StopIteration, ValueError, KeyError, Exception) as exc:
        logger.warning("OIDC token validation failed: %s - %s", type(exc).__name__, str(exc))
        raise HTTPException(status_code=401, detail="Token OIDC inválido") from exc

    email = str(claims.get("email", "")).strip().lower()
    if email not in settings.oidc_allowed_email_list:
        raise HTTPException(status_code=403, detail="Este e-mail não tem acesso à aplicação")
    user_id = settings.oidc_email_map.get(email)
    if not user_id:
        raise HTTPException(status_code=403, detail="E-mail autorizado sem usuário associado")
    user = await users_repo.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=403, detail="Usuário associado ao e-mail não encontrado")
    return TokenResponse(
        access_token=create_access_token(user_id),
        user=UserOut(
            id=user["id"], name=user["name"], base_salary_cents=user.get("base_salary_cents", 0),
            is_admin=user["id"] in settings.admin_user_id_list,
        ),
    )


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
            is_admin=user["id"] in settings.admin_user_id_list,
        ),
    )
