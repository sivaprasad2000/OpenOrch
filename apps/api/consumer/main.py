"""Consumer entry point — connects to RabbitMQ and processes test run messages"""

import asyncio
import logging
from pathlib import Path

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from consumer.be_client import BEClient
from consumer.config import settings
from consumer.storage import create_storage_backend
from consumer.worker import handle_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    storage = create_storage_backend(
        backend=settings.STORAGE_BACKEND,
        recordings_dir=Path(settings.LOCAL_RECORDINGS_DIR),
        base_url=settings.BE_BASE_URL,
        s3_bucket=settings.S3_BUCKET,
        s3_region=settings.S3_REGION,
    )
    logger.info("Storage backend: %s", settings.STORAGE_BACKEND)

    logger.info("Connecting to RabbitMQ at %s", settings.RABBITMQ_URL)
    connection = await aio_pika.connect(settings.RABBITMQ_URL)
    logger.info("Connected")

    client = BEClient()

    try:
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=1)

            queue = await channel.declare_queue(
                settings.RABBITMQ_TEST_RUNS_QUEUE,
                durable=True,
            )

            async def on_message(message: AbstractIncomingMessage) -> None:
                try:
                    from aio_pika import IncomingMessage
                    assert isinstance(message, IncomingMessage)
                    await handle_message(message, client, storage)
                except Exception:
                    logger.exception("Unhandled error processing message — consumer kept alive")

            await queue.consume(on_message)
            logger.info(
                "Consumer registered — waiting for messages on '%s'",
                settings.RABBITMQ_TEST_RUNS_QUEUE,
            )

            await asyncio.Future()
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
