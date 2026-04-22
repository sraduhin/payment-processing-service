import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import verify_api_key
from app.models import OutboxMessage, Payment
from app.schemas import PaymentCreate, PaymentCreated, PaymentDetail

router = APIRouter(
    prefix="/api/v1/payments",
    dependencies=[Depends(verify_api_key)],
)


@router.post("", status_code=202, response_model=PaymentCreated)
async def create_payment(
    body: PaymentCreate,
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> PaymentCreated:
    existing = await session.execute(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    existing_payment = existing.scalar_one_or_none()
    if existing_payment is not None:
        return PaymentCreated(
            payment_id=existing_payment.id,
            status=existing_payment.status,
            created_at=existing_payment.created_at,
        )

    payment_id = uuid.uuid4()
    payment = Payment(
        id=payment_id,
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        metadata_=body.metadata,
        idempotency_key=idempotency_key,
        webhook_url=body.webhook_url,
    )
    session.add(payment)
    await session.flush()

    outbox = OutboxMessage(payment_id=payment_id)
    session.add(outbox)

    await session.commit()
    await session.refresh(payment)

    return PaymentCreated(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get("/{payment_id}", response_model=PaymentDetail)
async def get_payment(
    payment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> PaymentDetail:
    result = await session.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentDetail.model_validate(payment)
