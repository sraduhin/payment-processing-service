import asyncio
import logging

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models import OutboxMessage, OutboxStatus

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1.0

payments_exchange = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)


async def publish_pending_messages() -> None:
    broker = RabbitBroker(settings.rabbitmq_url)
    await broker.start()

    try:
        while True:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(OutboxMessage)
                    .where(OutboxMessage.status == OutboxStatus.PENDING)
                    .with_for_update(skip_locked=True)
                    .limit(100)
                )
                messages = result.scalars().all()

                for msg in messages:
                    try:
                        await broker.publish(
                            str(msg.payment_id),
                            exchange=payments_exchange,
                            routing_key=f"{settings.payment_broker_name}.new",
                        )
                        msg.status = OutboxStatus.SENT
                    except Exception:
                        logger.exception("Failed to publish outbox message %s", msg.id)
                        msg.status = OutboxStatus.FAILED

                await session.commit()

            await asyncio.sleep(POLL_INTERVAL)
    finally:
        await broker.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(publish_pending_messages())


if __name__ == "__main__":
    main()
