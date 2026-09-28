import asyncio
import unittest
from unittest.mock import AsyncMock, patch
import httpx
from requester_agent.a2a_client import *
from requester_agent.ochestrator import RequesterOchestrator


class Step7Tests(unittest.IsolatedAsyncioTestCase):
    def client(self):
        return A2AClient("http://specialist", poll_interval=0.005, max_timeout=0.03)

    async def test_success(self):
        c = self.client()
        c.get_task_status = AsyncMock(side_effect=[{"status":"working"}, {"status":"completed"}])
        c.get_task_results = AsyncMock(return_value={"result": {"resolution":"ok"}})
        self.assertEqual(await c.poll_until_complete("1"), {"result":{"resolution":"ok"}})

    async def test_failed(self):
        c = self.client()
        c.get_task_status = AsyncMock(return_value={"status":"failed", "error":"RAG failed"})
        with self.assertRaises(A2ATaskFailedError):
            await c.poll_until_complete("1")

    async def test_no_evidence_status(self):
        c = self.client()
        c.get_task_status = AsyncMock(return_value={"status":"failed", "error_code":"NO_RELEVANT_INFORMATION"})
        with self.assertRaises(A2ANoInformationError):
            await c.poll_until_complete("1")

    async def test_unknown_status(self):
        c = self.client()
        c.get_task_status = AsyncMock(return_value={"status":"surprise"})
        with self.assertRaises(A2AProtocolError):
            await c.poll_until_complete("1")

    async def test_deadline_includes_requests_and_sleep(self):
        async def slow(*args):
            await asyncio.sleep(10)
        for stage in ("working", "status", "results"):
            with self.subTest(stage=stage):
                c = self.client()
                c.poll_interval = 10
                c.get_task_status = AsyncMock(return_value={"status":"working"})
                if stage == "status":
                    c.get_task_status = slow
                if stage == "results":
                    c.get_task_status = AsyncMock(return_value={"status":"completed"})
                    c.get_task_results = slow
                with self.assertRaises(A2ATimeoutError):
                    await asyncio.wait_for(c.poll_until_complete("1"), timeout=1)

    async def test_http_errors(self):
        request = httpx.Request("POST", "http://specialist/tasks")
        cases = [(httpx.ConnectError("offline"), A2ACommunicationError),
                 (httpx.ReadTimeout("slow"), A2ATimeoutError),
                 (httpx.Response(500, request=request), A2ACommunicationError),
                 (httpx.Response(200, text="not json", request=request), A2AProtocolError),
                 (httpx.Response(200, json=[], request=request), A2AProtocolError),
                 (httpx.Response(200, json={}, request=request), A2AProtocolError)]
        for response, expected in cases:
            with self.subTest(expected=expected, response=str(response)):
                mock = AsyncMock()
                if isinstance(response, Exception):
                    mock.request.side_effect = response
                else:
                    mock.request.return_value = response
                with patch("requester_agent.a2a_client.httpx.AsyncClient") as factory:
                    factory.return_value.__aenter__.return_value = mock
                    with self.assertRaises(expected):
                        await self.client().submit_task("help")

    async def test_orchestrator_blocks_failure(self):
        for result in ({"result":{}}, {"result":{"has_useful_information":False}},
                       {"result":{"category":"Help", "resolution":"Try this", "sources":[]}}):
            o = RequesterOchestrator()
            o.a2a_client.submit_task = AsyncMock(return_value="1")
            o.a2a_client.poll_until_complete = AsyncMock(return_value=result)
            o.automator.submit_support_ticket = AsyncMock()
            self.assertEqual((await o.process_user_request("help"))["status"], "error")
            o.automator.submit_support_ticket.assert_not_awaited()
        for error in (A2ATimeoutError("deadline"), A2ATaskFailedError("failed"), A2ACommunicationError("offline")):
            o.a2a_client.poll_until_complete = AsyncMock(side_effect=error)
            self.assertEqual((await o.process_user_request("help"))["status"], "error")
            o.automator.submit_support_ticket.assert_not_awaited()

    async def test_verified_and_unverified_browser(self):
        o = RequesterOchestrator()
        o.a2a_client.submit_task = AsyncMock(return_value="1")
        payload = {"category":"Help", "resolution":"Try this", "sources":["guide.txt"]}
        o.a2a_client.poll_until_complete = AsyncMock(return_value={"result":payload})
        for verified in (True, False):
            o.automator.submit_support_ticket = AsyncMock(return_value=verified)
            result = await o.process_user_request("help")
            self.assertEqual(result["status"], "success" if verified else "error")
            o.automator.submit_support_ticket.assert_awaited_once_with(agent_resolution=payload)

if __name__ == "__main__":
    unittest.main()
