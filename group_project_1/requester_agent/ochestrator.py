import sys
from pathlib import Path
from typing import Dict, Any, Optional

from requester_agent.a2a_client import A2AClient, A2ATimeoutError, A2ATaskFailedError
from requester_agent.browser_automation import SupportFormAutomator, BrowserAutomationError

class RequesterOchestrator:
    """
    Coordinates the Requester Agent workflow:
    User Request -> A2A Task Submission -> Polling Specialist Agent -> Receiving RAG Results -> Playwright Form Automation -> Verification
    """

    def __init__(
            self,
            specialist_url: str = "http://127.0.0.1:8000",
            mock_app_path: Optional[Path] = None,
            poll_interval: float = 1.0,
            max_timeout: float = 30.0,
            headless: bool = True
    ):
        """
        Initialize the orchestrator with required client settings.
        """
        if mock_app_path is None:
            base_dir = Path(__file__).parent.parent
            mock_app_path = base_dir / "mock_support_app" / "support_form.html"

        self.a2a_client = A2AClient(
            base_url=specialist_url,
            poll_interval=poll_interval,
            max_timeout=max_timeout
        )
        self.automator = SupportFormAutomator(
            html_path=mock_app_path,
            headless=headless
        )

    async def process_user_request(self, user_query: str) -> Dict[str, Any]:
        """
        Executes the end-to-end workflow for a given user request.
        
        Args:
            user_query (str): The natural language request from the user.
        Returns:
            Execution summary dictionary.

        """
        print("\n==================================================")
        print(f"[Requester Agent] Received User Request: '{user_query}'")
        print("==================================================")

        try:
            print("\n[Step 1] Submitting task to Specialist Agent...")
            task_id = await self.a2a_client.submit_task(query=user_query)

            print("\n[Step 2] Polling Specialist Agent for results...")
            task_resulst = await self.a2a_client.poll_until_complete(task_id=task_id)

            result_payload = task_resulst.get("result", {})
            print("\n[Requester Agent] RAG Resolution Output Retrieved:")
            print(f"  - Category: {result_payload.get('category')}")
            print(f"  - Resolution: {result_payload.get('resolution')}")
            if "sources" in result_payload:
                print(f"  - Sources Used: {result_payload.get('sources')}")

            print("\n[Step 3] Automating browser form submission with Playwright...")
            automation_success = await self.automator.submit_support_ticket(
                agent_resolution=result_payload
            )

            if automation_success:
                print("\n[Requester Agent] Workflow Completed Successfully!")
                return{
                    "status": "success",
                    "task_id": task_id,
                    "resolution": result_payload,
                    "verification": "Form submitted and verified successfully."
                }
        except A2ATimeoutError as e:
            print(f"\n[ERROR - Timeout] Specialist Agent timed out: {e}")
            return {
                "status": "error",
                "error_type": "TimeoutError",
                "message": str(e)
            }

        except A2ATaskFailedError as e:
            print(f"\n[ERROR - Task Failed] Specialist Agent failed processing: {e}")
            return {
                "status": "error",
                "error_type": "TaskFailedError",
                "message": str(e)
            }

        except BrowserAutomationError as e:
            print(f"\n[ERROR - Browser Automation] Playwright script failed: {e}")
            return {
                "status": "error",
                "error_type": "BrowserAutomationError",
                "message": str(e)
            }

        except Exception as e:
            print(f"\n[ERROR - Unexpected] An unexpected error occurred: {e}")
            return {
                "status": "error",
                "error_type": "UnexpectedError",
                "message": str(e)
            }