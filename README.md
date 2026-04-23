# Payment Processing Service

Асинхронный микросервис для обработки платежей с использованием FastAPI, PostgreSQL, RabbitMQ.

## Архитектура

- **API** — FastAPI-приложение для создания и получения платежей
- **Consumer** — FastStream-обработчик, эмулирующий платежный шлюз и отправляющий webhook-уведомления
- **Outbox Worker** — фоновый процесс, реализующий Outbox pattern для гарантированной публикации событий в RabbitMQ
- **PostgreSQL** — хранение платежей и outbox-сообщений
- **RabbitMQ** — брокер сообщений с поддержкой DLQ

## Установка переменных окружения

```bash
cp example.env .env

```
## Запуск

```bash
docker compose up --build
```

Сервис будет доступен на `http://localhost:8000`.
RabbitMQ Management UI: `http://localhost:15672` (guest/guest).

## API

Все запросы требуют заголовок `X-API-Key: secret-api-key`, если в `.env` не указано другое значение.

### Создание платежа

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: secret-api-key" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "amount": 1500.00,
    "currency": "RUB",
    "description": "Order #42",
    "metadata": {"order_id": 42},
    "webhook_url": "https://example.com/webhook"
  }'
```

Ответ (202 Accepted):

```json
{
  "payment_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2025-01-01T12:00:00Z"
}
```

### Получение платежа

```bash
curl http://localhost:8000/api/v1/payments/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: secret-api-key"
```

Ответ (200 OK):

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 1500.00,
  "currency": "RUB",
  "description": "Order #42",
  "metadata": {"order_id": 42},
  "status": "succeeded",
  "idempotency_key": "unique-key-123",
  "webhook_url": "https://example.com/webhook",
  "created_at": "2025-01-01T12:00:00Z",
  "processed_at": "2025-01-01T12:00:04Z"
}
```

### Запуск на тестовой базе
```bash
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

## Стек

- FastAPI + Pydantic v2
- SQLAlchemy 2.0 (async)
- PostgreSQL
- RabbitMQ (FastStream)
- Alembic
- Docker + docker-compose

## Ключевые паттерны

- **Outbox Pattern** — платеж и outbox-сообщение сохраняются в одной транзакции; отдельный воркер публикует сообщения в RabbitMQ
- **Idempotency Key** — повторный запрос с тем же ключом возвращает существующий платеж
- **Dead Letter Queue** — сообщения, не обработанные после 3 попыток, попадают в `payments.dlq`
- **Webhook Retry** — отправка webhook с экспоненциальной задержкой (до 3 попыток)

## Важные замечания

При неудачной попытке отправки webhook платёж тем не менее считается **проведённым**.
Можно добавить статус вебхука и логику для повторной отправки.
Так же лишним не будет добавить PATCH-запрос для изменения webhook_url.
