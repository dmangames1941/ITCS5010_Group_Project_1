from pathlib import Path
from typing import Any, Dict, Optional

from requester_agent.a2a_client import (
    A2AClient,
    A2ATimeoutError,
    A2ATaskFailedError,
    A2ACommunicationError,
    A2AProtocolError,
    A2ANoInformationError,
)
from requester_agent.browser_automation import (
    SupportFormAutomator,
    BrowserAutomationError,
)


class RequesterOchestrator:
    """Coordinates specialist requests and browser form submission."""

    def __init__(
        self,
        specialist_url: str = "http://127.0.0.1:8000",
        mock_app_path: Optional[Path] = None,
        poll_interval: float = 1.0,
        max_timeout: float = 30.0,
        headless: bool = True,
    ):
        if mock_app_path is None:
            base_dir = Path(__file__).parent.parent
            mock_app_path = (
                base_dir / "mock_support_app" / "support_form.html"
            )

        self.a2a_client = A2AClient(
            base_url=specialist_url,
            poll_interval=poll_interval,
            max_timeout=max_timeout,
        )

        self.automator = SupportFormAutomator(
            html_path=mock_app_path,
            headless=headless,
        )

    async def process_user_request(
        self, user_query: str
    ) -> Dict[str, Any]:
        print("\n==================================================")
        print(f"[Requester Agent] Received User Request: '{user_query}'")
        print("==================================================")

        try:
            print("\n[Step 1] Submitting task to Specialist Agent...")
            task_id = await self.a2a_client.submit_task(
                query=user_query
            )

            print("\n[Step 2] Polling Specialist Agent for results...")
            task_results = await self.a2a_client.poll_until_complete(
                task_id=task_id
            )

            result_payload = task_results.get("result")

            if not isinstance(result_payload, dict):
                raise A2AProtocolError(
                    "Specialist response is missing a valid result object."
                )

            if result_payload.get("has_useful_information") is False:
                raise A2ANoInformationError(
                    "The specialist found no useful knowledge-base information."
                )

            for field in ("category", "resolution"):
                value = result_payload.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise A2AProtocolError(
                        f"Specialist result is missing a valid {field}."
                    )

            sources = result_payload.get("sources", [])

            if not isinstance(sources, list):
                raise A2AProtocolError(
                    "Specialist sources must be a list."
                )

            if not sources:
                raise A2ANoInformationError(
                    "The specialist returned no supporting sources."
                )

            for source in sources:
                if not isinstance(source, (str, dict)) or not source:
                    raise A2AProtocolError(
                        "Specialist returned an invalid source."
                    )

                if isinstance(source, str) and not source.strip():
                    raise A2AProtocolError(
                        "Specialist returned an empty source."
                    )

            print("\n[Requester Agent] RAG Resolution Output Retrieved:")
            print(f"  - Category: {result_payload['category']}")
            print(f"  - Resolution: {result_payload['resolution']}")
            print(f"  - Sources Used: {sources}")

            print(
                "\n[Step 3] Automating browser form submission "
                "with Playwright..."
            )

            automation_success = await self.automator.submit_support_ticket(
                agent_resolution=result_payload
            )

            if not automation_success:
                raise BrowserAutomationError(
                    "Form submission could not be verified."
                )

            print("\n[Requester Agent] Workflow Completed Successfully!")

            return {
                "status": "success",
                "task_id": task_id,
                "resolution": result_payload,
                "verification": (
                    "Form submitted and verified successfully."
                ),
            }

        except A2ATimeoutError as e:
            print(f"\n[ERROR - Timeout] Specialist Agent timed out: {e}")
            return {
                "status": "error",
                "error_type": "TimeoutError",
                "message": str(e),
            }

        except A2ATaskFailedError as e:
            print(
                f"\n[ERROR - Task Failed] "
                f"Specialist Agent failed processing: {e}"
            )
            return {
                "status": "error",
                "error_type": "TaskFailedError",
                "message": str(e),
            }

        except (
            A2ACommunicationError,
            A2AProtocolError,
            A2ANoInformationError,
        ) as e:
            print(f"\n[ERROR - Specialist] {e}")
            print("[Requester Agent] No form was submitted.")
            return {
                "status": "error",
                "error_type": type(e).__name__,
                "message": str(e),
            }

        except BrowserAutomationError as e:
            print(
                f"\n[ERROR - Browser Automation] "
                f"Playwright script failed: {e}"
            )
            return {
                "status": "error",
                "error_type": "BrowserAutomationError",
                "message": str(e),
            }

        except Exception as e:
            print(
                f"\n[ERROR - Unexpected] "
                f"An unexpected error occurred: {e}"
            )
            return {
                "status": "error",
                "error_type": "UnexpectedError",
                "message": str(e),
            }