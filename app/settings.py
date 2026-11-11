from functools import lru_cache

from pydantic import PostgresDsn, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings read from environment variables (and an optional .env file)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # General
    APP_NAME: str = "cvariant"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_ROOT_PATH: str = ""

    # CORS - the React dev server runs on Vite's default port
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "cvariant"
    POSTGRES_PASSWORD: SecretStr = SecretStr("cvariant")
    POSTGRES_DB: str = "cvariant"
    DB_POOL_SIZE: int = 5
    DB_POOL_MAX_OVERFLOW: int = 5
    DB_ECHO: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD.get_secret_value(),
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            ),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
