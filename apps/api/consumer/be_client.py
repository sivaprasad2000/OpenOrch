"""HTTP client for communicating with the BE internal API"""

from typing import Any, cast

import httpx

from consumer.config import settings


class BEClient:
    """Async HTTP client for the BE internal API"""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.BE_BASE_URL,
            headers={"X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET},
            timeout=30.0,
        )

    async def get_test_run(self, run_id: str) -> dict[str, Any]:
        """
        Fetch full test run details including the test case payload.
        Called immediately after picking up a message from the queue.
        """
        response = await self._client.get(f"/api/v1/internal/test-runs/{run_id}")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def update_run_result(self, run_id: str, payload: dict[str, Any]) -> None:
        """Write step-by-step execution results back to the BE"""
        response = await self._client.patch(
            f"/api/v1/internal/test-runs/{run_id}/result",
            json=payload,
        )
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
