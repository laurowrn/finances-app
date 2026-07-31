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
    user_a_name: str = "Pessoa A"
    user_a_salary: float = 5000.0
    user_b_name: str = "Pessoa B"
    user_b_salary: float = 3000.0
    login_password: str = "casal"  # senha única para os dois usuários (uso local)

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
