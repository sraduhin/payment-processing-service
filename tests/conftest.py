import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, engine
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


@pytest.fixture
def api_key() -> str:
    return settings.api_key


@pytest.fixture
def auth_headers(api_key: str) -> dict:
    return {"X-API-Key": api_key}


@pytest.fixture
def idempotency_key() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def payment_payload() -> dict:
    return {
        "amount": 1500.00,
        "currency": "RUB",
        "description": "Test payment",
        "metadata": {"order_id": 42},
        "webhook_url": "http://localhost:9000",
    }


@pytest.fixture(autouse=True)
async def cleanup_db():
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM outbox"))
        await conn.execute(text("DELETE FROM payments"))
