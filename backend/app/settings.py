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


@lru_cache
def get_settings() -> Settings:
    return Settings()
