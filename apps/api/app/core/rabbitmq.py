
import json
import logging

import aio_pika
from aio_pika.abc import AbstractRobustConnection

from app.core.config import settings

logger = logging.getLogger(__name__)

_connection: AbstractRobustConnection | None = None


async def init_rabbitmq() -> None:
    global _connection
    try:
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        logger.info("RabbitMQ connection established")
    except Exception as e:
        logger.error("Failed to connect to RabbitMQ: %s", e)


async def close_rabbitmq() -> None:
    global _connection
    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("RabbitMQ connection closed")


async def publish_test_run(run_id: str, test_case_id: str) -> None:
    if _connection is None or _connection.is_closed:
        raise RuntimeError("RabbitMQ connection is not available")

    async with _connection.channel() as channel:
        queue = await channel.declare_queue(
            settings.RABBITMQ_TEST_RUNS_QUEUE,
            durable=True,
        )

        message_body = json.dumps({"run_id": run_id, "test_case_id": test_case_id}).encode()

        await channel.default_exchange.publish(
            aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=queue.name,
        )

        logger.info("Published test run %s (test_case=%s) to queue", run_id, test_case_id)
