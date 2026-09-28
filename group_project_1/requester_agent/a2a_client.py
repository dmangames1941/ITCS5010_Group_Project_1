import asyncio
import math
from typing import Any, Dict

import httpx


class A2AError(Exception):
    """Base error for specialist communication."""


class A2ATimeoutError(A2AError):
    """The specialist did not respond before the deadline."""


class A2ATaskFailedError(A2AError):
    """The specialist explicitly reported failure."""


class A2ACommunicationError(A2AError):
    """An HTTP or network operation failed."""


class A2AProtocolError(A2AError):
    """The response does not follow the agreed protocol."""


class A2ANoInformationError(A2AError):
    """No supported resolution is available."""


class A2AClient:
    def __init__(
        self,
        base_url: str,
        poll_interval: float = 1.0,
        max_timeout: float = 30.0,
    ):
        if not all(
            math.isfinite(value) and value > 0
            for value in (poll_interval, max_timeout)
        ):
            raise ValueError(
                "Timeout and polling interval must be positive finite numbers."
            )

        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.max_timeout = max_timeout

    async def _request(
        self, method: str, path: str, **kwargs
    ) -> Dict[str, Any]:
        try:
            # Limit the entire request, including connection time.
            async with asyncio.timeout(min(5.0, self.max_timeout)):
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method,
                        self.base_url + path,
                        timeout=5.0,
                        **kwargs,
                    )
                    response.raise_for_status()
                    data = response.json()

        except (TimeoutError, httpx.TimeoutException) as exc:
            raise A2ATimeoutError(
                "Specialist HTTP request timed out."
            ) from exc

        except httpx.HTTPStatusError as exc:
            raise A2ACommunicationError(
                f"Specialist returned HTTP {exc.response.status_code}."
            ) from exc

        except httpx.RequestError as exc:
            raise A2ACommunicationError(
                "Cannot connect to the Specialist Agent."
            ) from exc

        except ValueError as exc:
            raise A2AProtocolError(
                "Specialist returned invalid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise A2AProtocolError(
                "Specialist response must be a JSON object."
            )

        return data

    async def submit_task(self, query: str) -> str:
        data = await self._request(
            "POST", "/tasks", json={"query": query}
        )
        task_id = data.get("task_id")

        if not isinstance(task_id, str) or not task_id.strip():
            raise A2AProtocolError(
                "Acknowledgment requires a nonempty string task_id."
            )

        return task_id

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/tasks/{task_id}")

    async def get_task_results(self, task_id: str) -> Dict[str, Any]:
        return await self._request(
            "GET", f"/tasks/{task_id}/results"
        )

    async def poll_until_complete(
        self, task_id: str
    ) -> Dict[str, Any]:
        try:
            # This deadline includes requests, sleeps, and fetching results.
            async with asyncio.timeout(self.max_timeout):
                while True:
                    data = await self.get_task_status(task_id)
                    status = data.get("status")

                    print(
                        f"[Requester Agent] Task {task_id} status: {status}"
                    )

                    if status == "completed":
                        return await self.get_task_results(task_id)

                    if status == "failed":
                        if (
                            data.get("error_code")
                            == "NO_RELEVANT_INFORMATION"
                        ):
                            raise A2ANoInformationError(
                                "No useful knowledge-base evidence was found."
                            )

                        raise A2ATaskFailedError(
                            str(
                                data.get("error")
                                or "Specialist task failed."
                            )
                        )

                    if status not in ("submitted", "working"):
                        raise A2AProtocolError(
                            f"Unknown task status: {status!r}."
                        )

                    await asyncio.sleep(self.poll_interval)

        except TimeoutError as exc:
            raise A2ATimeoutError(
                f"Task {task_id} exceeded the "
                f"{self.max_timeout:g}-second polling deadline."
            ) from exc