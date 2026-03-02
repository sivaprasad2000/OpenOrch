"""Message handler — processes a single test run message from the queue"""

import json
import logging
from typing import Any

import httpx
from aio_pika import IncomingMessage

from consumer.be_client import BEClient
from consumer.executor import execute_test
from consumer.storage import StorageBackend

logger = logging.getLogger(__name__)


async def handle_message(
    message: IncomingMessage,
    client: BEClient,
    storage: StorageBackend | None = None,
) -> None:
    """
    Process one test run message.

    Message format: {"run_id": "...", "test_case_id": "..."}

    Error handling strategy:
    - Malformed message (bad JSON or missing fields): nack without requeue — the
      message is unprocessable and requeueing it would cause an infinite loop.
    - Infrastructure errors (BE unreachable, RabbitMQ issues): let the exception
      propagate so aio_pika nacks with requeue=True — the message stays in the
      queue and will be retried once the dependency recovers.
    """
    try:
        body: dict[str, Any] = json.loads(message.body)
        run_id: str = body["run_id"]
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Malformed message — %s | raw body: %s", exc, message.body)
        await message.nack(requeue=False)
        return

    try:
        run_detail = await client.get_test_run(run_id)
    except httpx.HTTPStatusError as exc:
        if 400 <= exc.response.status_code < 500:
            logger.error(
                "Run %s not found on BE (status=%s) — discarding message",
                run_id, exc.response.status_code,
            )
            await message.nack(requeue=False)
        else:
            await message.nack(requeue=True)
        raise
    except Exception:
        await message.nack(requeue=True)
        raise

    async with message.process(requeue=True):
        logger.info("Processing test run %s", run_id)

        result = await execute_test(run_detail, storage=storage)

        await client.update_run_result(run_id, result)

        logger.info(
            "Test run %s finished — status: %s | trace: %s",
            run_id,
            result["status"],
            result.get("recording_url") or "none",
        )
