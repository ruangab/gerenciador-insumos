"""Configurações da aplicação utilizando Pydantic Settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parâmetros do sistema carregados de variáveis de ambiente ou arquivo .env."""

    MONGODB_URL: str = "mongodb://127.0.0.1:27017"
    DATABASE_NAME: str = "gestao_estoque"
    APP_ENV: str = "development"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    ALERTA_DIAS_VALIDADE: int = 30

    # Autenticação JWT
    JWT_SECRET: str = "troque-esta-chave-em-producao-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 dias

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância única em cache das configurações."""
    return Settings()


# Instância padrão para importação direta e prática: from app.config import settings
settings = get_settings()
