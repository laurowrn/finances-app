from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Mongo
    mongo_uri: str = "mongodb://localhost:27018"
    mongo_db: str = "group_finance"

    # Auth
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 1 semana

    # Usuários seedados (o casal). Senha compartilhada simples para uso local.
    # Salários ficam em REAIS no .env (é config escrita por humano) e viram
    # centavos na borda, em seed.py. Decimal, não float: a conversão é exata.
    user_a_name: str = "Pessoa A"
    user_a_salary: Decimal = Decimal("5000")
    user_b_name: str = "Pessoa B"
    user_b_salary: Decimal = Decimal("3000")
    login_password: str = "casal"  # senha única para os dois usuários (uso local)
    admin_user_ids: str = ""
    secrets_encryption_key: str = ""

    # OIDC/Keycloak
    oidc_issuer_url: str = "https://finances.tail1ebd6.ts.net/auth/realms/group-finance"
    oidc_internal_issuer_url: str = "http://keycloak:8080/auth/realms/group-finance"
    oidc_client_id: str = "group-finance-web"
    oidc_enabled: bool = False
    oidc_redirect_uri: str = "https://finances.tail1ebd6.ts.net/login"
    oidc_allowed_emails: str = "laurowrn@gmail.com,nayarapaolat@gmail.com"
    oidc_email_user_map: str = ""

    # IA (opcional). Sem chave, o fluxo de sugestão de regras fica desabilitado.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # CORS
    cors_origins: str = "http://localhost:3009,http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def admin_user_id_list(self) -> set[str]:
        return {user_id.strip() for user_id in self.admin_user_ids.split(",") if user_id.strip()}

    @property
    def oidc_allowed_email_list(self) -> set[str]:
        return {email.strip().lower() for email in self.oidc_allowed_emails.split(",") if email.strip()}

    @property
    def oidc_email_map(self) -> dict[str, str]:
        result = {}
        for pair in self.oidc_email_user_map.split(","):
            if ":" in pair:
                email, user_id = pair.split(":", 1)
                result[email.strip().lower()] = user_id.strip()
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()
