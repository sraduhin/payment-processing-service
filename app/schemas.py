import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import Currency, PaymentStatus


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: Currency
    description: str = Field(min_length=1, max_length=500)
    metadata: dict | None = None
    webhook_url: str = Field(min_length=1)


class PaymentCreated(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatus
    created_at: datetime


class PaymentDetail(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict | None = Field(validation_alias="metadata_")
    status: PaymentStatus
    idempotency_key: uuid.UUID
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
