import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxMessage, OutboxStatus, Payment, PaymentStatus


class TestAuth:
    """Аутентификация через X-API-Key."""

    @pytest.mark.asyncio
    async def test_no_api_key(self, client: AsyncClient):
        response = await client.get(f"/api/v1/payments/{uuid.uuid4()}")
        assert response.status_code in (403, 422)

    @pytest.mark.asyncio
    async def test_wrong_api_key(self, client: AsyncClient):
        response = await client.get(
            f"/api/v1/payments/{uuid.uuid4()}",
            headers={"X-API-Key": "wrong"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_valid_api_key(self, client: AsyncClient, auth_headers: dict):
        response = await client.get(
            f"/api/v1/payments/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestCreatePayment:
    """POST /api/v1/payments — создание платежа."""

    @pytest.mark.asyncio
    async def test_create_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        idempotency_key: str,
        payment_payload: dict,
        session: AsyncSession,
    ):
        response = await client.post(
            "/api/v1/payments",
            headers={**auth_headers, "Idempotency-Key": idempotency_key},
            json=payment_payload,
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert "payment_id" in data
        assert "created_at" in data

        # Проверяем запись в БД
        result = await session.execute(
            select(Payment).where(Payment.id == data["payment_id"])
        )
        payment = result.scalar_one()
        assert str(payment.amount) == "1500.00"
        assert payment.currency.value == "RUB"
        assert payment.description == "Test payment"
        assert payment.status == PaymentStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_outbox_entry(
        self,
        client: AsyncClient,
        auth_headers: dict,
        idempotency_key: str,
        payment_payload: dict,
        session: AsyncSession,
    ):
        """При создании платежа должна создаваться запись в outbox."""
        response = await client.post(
            "/api/v1/payments",
            headers={**auth_headers, "Idempotency-Key": idempotency_key},
            json=payment_payload,
        )
        payment_id = response.json()["payment_id"]

        result = await session.execute(
            select(OutboxMessage).where(OutboxMessage.payment_id == payment_id)
        )
        outbox = result.scalar_one()
        assert outbox.status == OutboxStatus.PENDING

    @pytest.mark.asyncio
    async def test_negative_amount(
        self,
        client: AsyncClient,
        auth_headers: dict,
        idempotency_key: str,
        payment_payload: dict,
    ):
        payment_payload["amount"] = -100
        response = await client.post(
            "/api/v1/payments",
            headers={**auth_headers, "Idempotency-Key": idempotency_key},
            json=payment_payload,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_unsupported_currency(
        self,
        client: AsyncClient,
        auth_headers: dict,
        idempotency_key: str,
        payment_payload: dict,
    ):
        payment_payload["currency"] = "GBP"
        response = await client.post(
            "/api/v1/payments",
            headers={**auth_headers, "Idempotency-Key": idempotency_key},
            json=payment_payload,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_idempotency_key(
        self,
        client: AsyncClient,
        auth_headers: dict,
        payment_payload: dict,
    ):
        response = await client.post(
            "/api/v1/payments",
            headers=auth_headers,
            json=payment_payload,
        )
        assert response.status_code == 422


class TestIdempotency:
    """Идемпотентность по Idempotency-Key."""

    @pytest.mark.asyncio
    async def test_duplicate_request_returns_same_payment(
        self,
        client: AsyncClient,
        auth_headers: dict,
        idempotency_key: str,
        payment_payload: dict,
    ):
        headers = {**auth_headers, "Idempotency-Key": idempotency_key}

        r1 = await client.post("/api/v1/payments", headers=headers, json=payment_payload)
        r2 = await client.post("/api/v1/payments", headers=headers, json=payment_payload)

        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json()["payment_id"] == r2.json()["payment_id"]

    @pytest.mark.asyncio
    async def test_different_keys_create_different_payments(
        self,
        client: AsyncClient,
        auth_headers: dict,
        payment_payload: dict,
    ):
        r1 = await client.post(
            "/api/v1/payments",
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
            json=payment_payload,
        )
        r2 = await client.post(
            "/api/v1/payments",
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
            json=payment_payload,
        )

        assert r1.json()["payment_id"] != r2.json()["payment_id"]


class TestGetPayment:
    """GET /api/v1/payments/{payment_id}."""

    @pytest.mark.asyncio
    async def test_get_existing(
        self,
        client: AsyncClient,
        auth_headers: dict,
        idempotency_key: str,
        payment_payload: dict,
    ):
        create_resp = await client.post(
            "/api/v1/payments",
            headers={**auth_headers, "Idempotency-Key": idempotency_key},
            json=payment_payload,
        )
        payment_id = create_resp.json()["payment_id"]

        response = await client.get(
            f"/api/v1/payments/{payment_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == payment_id
        assert data["amount"] == "1500.00"
        assert data["currency"] == "RUB"
        assert data["description"] == "Test payment"
        assert data["metadata"] == {"order_id": 42}
        assert data["status"] == "pending"
        assert data["idempotency_key"] == idempotency_key
        assert data["webhook_url"] == "http://localhost:9000"
        assert data["processed_at"] is None

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient, auth_headers: dict):
        response = await client.get(
            f"/api/v1/payments/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Payment not found"
