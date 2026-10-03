"""Real isolated PostgreSQL and FFmpeg; S3 is in-process Moto, never AWS."""
import os
import pytest
from moto import mock_aws
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine, text

source_url = make_url(os.environ["DATABASE_URL"])
if source_url.host not in ("localhost", "127.0.0.1", "postgres", "db"):
    raise RuntimeError("Tests require an explicitly local PostgreSQL host")
if os.environ.get("APP_ENV") == "production":
    raise RuntimeError("Refusing to run destructive tests with APP_ENV=production")
test_name = source_url.database + "_test"
assert test_name.endswith("_test")
test_url = source_url.set(database=test_name)
os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
os.environ.update(APP_ENV="test", AWS_REGION="us-east-1", S3_BUCKET="audio-notes-test",
                  AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing",
                  AWS_SESSION_TOKEN="testing", AWS_EC2_METADATA_DISABLED="true")
os.environ.pop("AWS_PROFILE", None)
os.environ["GNANI_API_KEY"] = "test-key"
os.environ["GEMINI_API_KEY"] = "test-key"

from app.config import settings
settings.cache_clear()
from app.database import Base, engine
from app import models


@pytest.fixture(scope="session", autouse=True)
def database():
    admin = create_engine(source_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": test_name}):
            # Identifier escaped by the SQLAlchemy dialect, never interpolated unchecked.
            connection.exec_driver_sql("CREATE DATABASE " + admin.dialect.identifier_preparer.quote(test_name))
    Base.metadata.create_all(engine)
    yield
    admin.dispose()


@pytest.fixture(autouse=True)
def clean_database(database):
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    yield


@pytest.fixture(autouse=True)
def isolated_s3():
    import boto3
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="audio-notes-test")
        yield
