import asyncio
import logging
from datetime import datetime, timezone

import httpx
from faststream import FastStream
from faststream.rabbit import (
    ExchangeType,
    RabbitBroker,
    RabbitExchange,
    RabbitQueue,
)
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models import Payment, PaymentStatus
from app.utils import emulate_payment_processing

logger = logging.getLogger(__name__)

broker = RabbitBroker(settings.rabbitmq_url)
app = FastStream(broker)

payments_exchange = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)

dlx_exchange = RabbitExchange(f"{settings.payment_broker_name}.dlx", type=ExchangeType.DIRECT, durable=True)
dlq = RabbitQueue(f"{settings.payment_broker_name}.dlq", durable=True, routing_key=f"{settings.payment_broker_name}.new")

payments_queue = RabbitQueue(
    f"{settings.payment_broker_name}.new",
    durable=True,
    routing_key=f"{settings.payment_broker_name}.new",
    arguments={
        "x-dead-letter-exchange": f"{settings.payment_broker_name}.dlx",
        "x-dead-letter-routing-key": f"{settings.payment_broker_name}.new",
        "x-queue-type": "quorum",
        "x-delivery-limit": settings.payment_x_delivery_limit,
    },
)


async def send_webhook(url: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(settings.webhook_max_retry):
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                if attempt == settings.webhook_max_retry - 1:
                    logger.error("Webhook delivery failed after %d attempts: %s", settings.webhook_max_retry, exc)
                    return
                delay = settings.webhook_retry_delay * (2 ** attempt)
                logger.warning("Webhook attempt %d failed, retrying in %.1fs", attempt + 1, delay)
                await asyncio.sleep(delay)


@broker.subscriber(payments_queue, payments_exchange)
async def process_payment(payment_id: str) -> None:
    logger.info("Processing payment %s", payment_id)

    async with async_session_factory() as session:
        result = await session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if payment is None:
            logger.error("Payment %s not found", payment_id)
            return

        if payment.status != PaymentStatus.PENDING:
            logger.info("Payment %s already processed, skipping", payment_id)
            return

        success = await emulate_payment_processing()

        if not success:
            raise RuntimeError(f"Payment {payment_id} processing failed")

        payment.status = PaymentStatus.SUCCEEDED
        payment.processed_at = datetime.now(timezone.utc)
        await session.commit()

        webhook_payload = {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "amount": str(payment.amount),
            "currency": payment.currency.value,
            "processed_at": payment.processed_at.isoformat(),
        }
        await send_webhook(payment.webhook_url, webhook_payload)

        logger.info("Payment %s processed: %s", payment_id, payment.status)


@broker.subscriber(dlq, dlx_exchange)
async def handle_dlq(payment_id: str) -> None:
    logger.error("DLQ: payment %s failed permanently", payment_id)

    async with async_session_factory() as session:
        result = await session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if payment and payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.FAILED
            payment.processed_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info("Payment %s marked as failed via DLQ", payment_id)
