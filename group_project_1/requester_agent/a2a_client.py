import asyncio
import time
from typing import Any, Dict, Optional
import httpx

class A2AClient:
    def __init__(
            self,
            base_url: str,
            poll_interval: float = 1.0,
            max_timeout: float = 30.0,
    ):
        """
        Initialize the A2A Client.

        Args:
            base_url (str): The base URL of the A2A service.
            poll_interval (float): The interval in seconds between polling attempts.
            max_timeout (float): The maximum time in seconds to wait for a response.
        """
        self.base_url = base_url
        self.poll_interval = poll_interval
        self.max_timeout = max_timeout

    async def submit_task(self, query:str) -> str:
        """
        Submits a request to the Specialist Agent and expects an immediate acknowledgment with a task ID.
        
        Args:
            query (str): The query to be sent to the Specialist Agent.
        
        Returns:
            str: The task ID received from the Specialist Agent.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tasks",
                    json={"query": query},
                    timeout=5.0
                )
                response.raise_for_status()
                data = response.json()

                task_id = data.get("task_id")
                if not task_id:
                    raise ValueError("No task_id returned from the Specialist Agent.")

                print(f"[Requester Agent] Task submitted successfully. Task ID: {task_id}")
                return task_id
            except httpx.RequestError as e:
                raise RuntimeError(f"An error occurred while requesting {e.request.url!r}.") from e

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Checks the current status of a submitted task.
        
        Args:
            task_id (str): The ID of the task to check.
        
        Returns:
            Dict[str, Any]: The status information of the task.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/tasks/{task_id}",
                    timeout=5.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                raise RuntimeError(f"An error occurred while requesting {e.request.url!r}.") from e

    async def get_task_results(self, task_id: str) -> Dict[str, Any]:
        """
        Retrieves the completed results from the Specialist Agent.
        Args:
            task_id (str): The ID of the task to retrieve results for.
        Returns:
            Dict[str, Any]: The results of the task.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/tasks/{task_id}/results",
                    timeout=5.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                raise RuntimeError(f"An error occurred while requesting {e.request.url!r}.") from e

    async def poll_until_complete(self, task_id: str) -> Dict[str, Any]:
        """
        Polls the Specialist Agent periodically until the task reaches 'completed' or 'failed' status or until the maximum timeout is reached.
        
        Args:
            task_id (str): The ID of the task to poll.
        
        Returns:
            Dict[str, Any]: The final status of the task.
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.max_timeout:
                raise TimeoutError(f"Polling for task {task_id} exceeded maximum timeout of {self.max_timeout} seconds.")

            status_response = await self.get_task_status(task_id)
            status = status_response.get("status")

            print(f"[Requester Agent] Task {task_id} status: {status}")

            if status == "completed":
                return await self.get_task_results(task_id)
            elif status == "failed":
                raise RuntimeError(f"Task {task_id} failed. Details: {status_response.get('error', 'No error details provided.')}")
            elif status in ("submitted", "working"):
                await asyncio.sleep(self.poll_interval)
            else:
                raise RuntimeError(f"Unknown status '{status}' for task {task_id}.")