from __future__ import annotations

import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="vue_fastapi_phase9_tests_"))
TEST_DB_PATH = TEST_DB_DIR / "test.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["SCHEDULER_RUN_ON_STARTUP"] = "false"
os.environ["WS_ENABLED"] = "false"
os.environ["JWT_SECRET_KEY"] = "phase9_test_secret_key_with_32_chars"
os.environ["LLM_API_KEY"] = "test-key"
os.environ["LLM_BASE_URL"] = "http://llm.test.invalid"
os.environ["LLM_MODEL_NAME"] = "test-model"
os.environ["EMBEDDING_PROVIDER"] = "local-hash"

from app.db.session import Base, engine  # noqa: E402
from app.main import create_application  # noqa: E402


def _build_phone_number() -> str:
    suffix = str(uuid.uuid4().int % 1_0000_0000).zfill(8)
    return f"139{suffix}"


def assert_beijing_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(hours=8)
    return parsed


def register_user(
    client: TestClient,
    username: str,
    password: str,
    email: str,
    phone: str,
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "phone": phone,
            "password": password,
            "confirm_password": password,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def login_user(
    client: TestClient,
    username: str,
    password: str,
) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def app():
    return create_application()


@pytest.fixture
def client(app: TestClient):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def create_user(client: TestClient):
    def _create_user(prefix: str = "user", password: str = "Pass123456") -> dict:
        username = f"{prefix}_{uuid.uuid4().hex[:8]}"
        email = f"{username}@example.com"
        phone = _build_phone_number()
        user = register_user(
            client=client,
            username=username,
            password=password,
            email=email,
            phone=phone,
        )
        token = login_user(client, username, password)
        return {
            "user": user,
            "username": username,
            "password": password,
            "headers": {"Authorization": f"Bearer {token}"},
        }

    return _create_user


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TEST_DB_DIR, ignore_errors=True)
