import os
from pathlib import Path
from typing import Dict, Any
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

class BrowserAutomationError(Exception):
    """Custom exception for browser automation errors."""
    pass

class SupportFormAutomator:
    """Handles Playwright automation for the mock support web app"""

    def __init__(self, html_path: Path, headless: bool = True):
        """Initialize the browser automator.
        
        Args:
            html_path (Path): Path to the local HTML file for the mock support web app.
            headless (bool): Whether to run the browser in headless mode. Defaults to True.
        """
        self.html_path = html_path.resolve()
        self.headless = headless
        self.file_url = f"file://{self.html_path}"

    async def submit_support_ticket(self,  agent_resolution: Dict[str, Any]) -> bool:
        """
        Opens the mock app, fills in the category and resolution notes,
        submits the form, and verifies completion.

        Args:
            agent_resolution (Dict[str, Any]): A dictionary containing the category and resolution notes.
        Returns:
            bool: True if the form was submitted successfully, False otherwise.
        """
        if not self.html_path.exists():
            raise BrowserAutomationError(f"HTML file not found at {self.html_path}")

        category = agent_resolution.get("category", "General Inquiry")
        resolution_notes = agent_resolution.get("resolution", agent_resolution.get("resolution_notes",""))

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                print(f"[Playwright] Opening web application: {self.file_url}")
                await page.goto(self.file_url)

                category_input = page.locator("#category, select[name='category'], input[name='category']").first
                resolution_input = page.locator("#resolution, #resolution_notes, textarea[name='resolution']").first
                submit_button = page.locator("button[type='submit'], #submit-btn, input[type='submit']").first

                print(f"[Playwright] Filling Category: {category}")
                if await category_input.evaluate("el => el.tagName.toLowerCase() === 'select'"):
                    await category_input.select_option(category)
                else:
                    await category_input.fill(category)

                print(f"[Playwright] Filling Resolution Notes...")
                await resolution_input.fill(resolution_notes)

                print("[Playwright] Submitting form...")
                await submit_button.click()

                print("[Playwright] Verifying submission results...")

                confirmation_locator = page.locator("#confirmation, .success-message, #status-message").first
                await confirmation_locator.wait_for(state="visible", timeout=5000)
                
                confirmation_text = await confirmation_locator.inner_text()
                print(f"[Playwright] Verification Successful. Message: '{confirmation_text.strip()}'")

                await browser.close()
                return True
            except PlaywrightTimeoutError:
                await browser.close()
                raise BrowserAutomationError("Form submission verification failed: Confirmation message not found.")
            except Exception as e:
                await browser.close()
                raise BrowserAutomationError(f"An error occurred during form submission: {str(e)}")
                                              