from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    database_url: str = Field(min_length=1, repr=False)
    aws_region: str = Field(min_length=1, pattern=r"^[a-z]{2}(?:-[a-z]+)+-\d+$")
    s3_bucket: str = Field(min_length=3, max_length=63, pattern=r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
    app_env: Literal["development", "production", "test"] = "development"
    app_origin: str = "http://localhost:3000"
    session_secret: str = Field(min_length=32, repr=False)
    cookie_secure: bool = False
    gnani_api_key: str = Field(default="", repr=False)
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-3.8-flash"
    github_repo_url: str = ""
    max_upload_bytes: int = Field(default=50 * 1024**3, gt=0, le=5 * 1024**4)
    chunk_seconds: int = Field(default=30, ge=2, le=30)
    chunk_overlap: int = Field(default=1, ge=0)
    lease_seconds: int = Field(default=180, ge=60)

    @model_validator(mode="after")
    def validate_settings(self):
        origin = urlsplit(self.app_origin)
        if origin.scheme not in ("http", "https") or not origin.hostname or origin.path or origin.query or origin.fragment or origin.username:
            raise ValueError("APP_ORIGIN must be an HTTP(S) origin without a path or credentials")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        if self.chunk_overlap >= self.chunk_seconds:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SECONDS")
        if self.session_secret.startswith(("replace-", "change-")):
            raise ValueError("Generate a random SESSION_SECRET before starting")
        if self.app_env == "production" and (origin.scheme != "https" or not self.cookie_secure):
            raise ValueError("Production requires HTTPS APP_ORIGIN and COOKIE_SECURE=true")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
