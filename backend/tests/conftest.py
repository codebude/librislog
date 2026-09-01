"""Shared pytest fixtures for all tests."""

import os
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

os.environ.setdefault("API_KEY_ENCRYPTION_KEY", "test-api-key-encryption-secret")
# Telemetry must never fire during the test suite (no network, no dev-DB writes).
os.environ["TELEMETRY_DISABLED"] = "true"

from app.auth import encrypt_api_key, generate_api_key, get_api_key_prefix, get_password_hash, hash_api_key
from app.models import ApiKey, User, UserRole, UserSettings
from app.main import app
from app.database import get_session


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Provide an in-memory SQLite session, isolated per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with the test session injected."""
    key_plain = generate_api_key()

    user = User(
        firstname="Test",
        lastname="User",
        email="test@example.com",
        role=UserRole.admin,
        hashed_password=get_password_hash("test-password"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    session.add(UserSettings(user_id=user.id, language="en"))
    session.add(
        ApiKey(
            user_id=user.id,
            key_prefix=get_api_key_prefix(key_plain),
            key_hash=hash_api_key(key_plain),
            key_encrypted=encrypt_api_key(key_plain),
            description="Test key",
        )
    )
    session.commit()

    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        client.headers.update({"X-API-Key": key_plain})
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="create_user_with_key")
def create_user_with_key_fixture(session: Session):
    """Return a factory that creates a user + API key and returns ``(user, key_plain)``."""
    def _create(
        *,
        firstname: str = "User",
        lastname: str = "Example",
        email: str,
        role: UserRole = UserRole.user,
        password: str = "secret123",
    ) -> tuple[User, str]:
        key_plain = generate_api_key()
        user = User(
            firstname=firstname,
            lastname=lastname,
            email=email,
            role=role,
            hashed_password=get_password_hash(password),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None

        session.add(UserSettings(user_id=user.id, language="en"))
        session.add(
            ApiKey(
                user_id=user.id,
                key_prefix=get_api_key_prefix(key_plain),
                key_hash=hash_api_key(key_plain),
                key_encrypted=encrypt_api_key(key_plain),
                description="Primary app key",
            )
        )
        session.commit()
        return user, key_plain

    return _create


@pytest.fixture(name="invalid_settings_kwargs")
def invalid_settings_kwargs_fixture(request: Any) -> tuple[dict[str, str], str]:
    """Parametrized fixture providing ``(kwargs, expected_error_substring)`` for Settings validation."""
    return request.param
