from unittest.mock import patch
from pydantic import ValidationError
import pytest
from app.config import Settings
from app import storage


def test_s3_uses_default_credential_chain():
    with patch("app.storage.boto3.client") as factory:
        storage.client()
    args, kwargs = factory.call_args
    assert args == ("s3",)
    assert kwargs["region_name"] == "us-east-1"
    assert "aws_access_key_id" not in kwargs
    assert "aws_secret_access_key" not in kwargs
    assert "endpoint_url" not in kwargs
    assert kwargs["config"].signature_version == "s3v4"


def test_production_requires_secure_cookie_and_https():
    with pytest.raises(ValidationError, match="Production requires"):
        Settings(app_env="production", cookie_secure=False, app_origin="http://localhost:3000")
    valid = Settings(app_env="production", cookie_secure=True, app_origin="https://notes.example.com")
    assert valid.cookie_secure


def test_configuration_errors_hide_values():
    secret = "test-password-must-not-appear"
    with pytest.raises(ValidationError) as error:
        Settings(database_url=secret)
    assert secret not in str(error.value)


def test_bucket_is_never_created_by_api_startup():
    from fastapi.testclient import TestClient
    from app.api import app
    with patch("app.storage.boto3.client", side_effect=AssertionError("No AWS calls on startup/health")):
        with TestClient(app) as api:
            assert api.get("/health").json() == {"status": "ok"}


def test_database_outage_is_sanitized():
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import SQLAlchemyError
    from app.api import app
    from app.database import get_db
    class Unavailable:
        def execute(self, *args):
            raise SQLAlchemyError("private-database-password")
    app.dependency_overrides[get_db] = lambda: Unavailable()
    try:
        with TestClient(app) as api:
            response = api.get("/health")
            assert response.status_code == 503
            assert "private-database-password" not in response.text
    finally:
        app.dependency_overrides.clear()
