import os

# Fast hashing in tests only. Must be set before settings are first read.
os.environ["BCRYPT_ROUNDS"] = "4"

from collections.abc import Callable, Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine  # noqa: E402
from sqlmodel import Session, create_engine  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.main import create_app  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    return _alembic_config(get_settings().test_database_url)


@pytest.fixture(scope="session")
def engine(alembic_config: Config) -> Iterator[Engine]:
    """Test database built by the real migrations, rebuilt from scratch each run."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    test_engine = create_engine(get_settings().test_database_url)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Session inside a transaction that is rolled back after each test.
    Commits made by application code only release a savepoint."""
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            yield db
        transaction.rollback()


@pytest.fixture
def make_client(session: Session) -> Iterator[Callable[..., TestClient]]:
    """Build a TestClient on the real app, sharing the test session.
    Extra routers (test-only routes) can be mounted to exercise dependencies."""
    clients: list[TestClient] = []

    def factory(
        *extra_routers: APIRouter,
        settings: Settings | None = None,
        client_ip: str = "testclient",
    ) -> TestClient:
        app: FastAPI = create_app(settings)
        for router in extra_routers:
            app.include_router(router)
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app, client=(client_ip, 50000))
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()
