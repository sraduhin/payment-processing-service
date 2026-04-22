from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://payments:payments@localhost:5432/payments"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    api_key: str = "secret-api-key"
    payment_broker_name: str = "payment"
    payment_x_delivery_limit: int = 3

    webhook_max_retry: int = 3
    webhook_retry_delay: float = 1.0

    model_config = {"env_prefix": "APP_"}


settings = Settings()
