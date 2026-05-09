"""LoginPage — sanmar.com /login form.

Captured selectors (verified against live HTML 2026-05-09):

* Username:    ``input#j_username``
* Password:    ``input#j_password``
* Submit:      ``button[type=submit]`` with text "Log In"
* Success URL: ``https://www.sanmar.com/`` (landing page)
* Logged-in proof element: ``div.customer-info`` containing
  the literal text "Welcome,".
"""

from __future__ import annotations

from playwright.sync_api import expect

from skills.sanmar_returns.pages.base import BasePage

LOGIN_URL = "https://www.sanmar.com/login"
POST_LOGIN_URL = "https://www.sanmar.com/"


class LoginPage(BasePage):
    def goto(self) -> None:
        self._log("login.goto", url=LOGIN_URL)
        self.page.goto(LOGIN_URL, wait_until="domcontentloaded")
        self.page.locator("#j_username").wait_for(state="visible")

    def submit(self, username: str, password: str) -> None:
        """Fill the form and click Log In. Waits for the post-login
        landing URL plus the welcome banner before returning so the
        caller can assume an authenticated session."""
        self._log("login.submit")
        self.page.locator("#j_username").fill(username)
        self.page.locator("#j_password").fill(password)
        self.page.get_by_role("button", name="Log In").click()
        self.page.wait_for_url(POST_LOGIN_URL, wait_until="domcontentloaded")
        expect(
            self.page.locator("div.customer-info").get_by_text("Welcome,")
        ).to_be_visible()

    def is_logged_in(self) -> bool:
        """Lightweight check used to skip ``submit`` when an existing
        ``storage_state`` file already authenticated us."""
        try:
            return (
                self.page.locator("div.customer-info")
                .get_by_text("Welcome,")
                .is_visible(timeout=2_000)
            )
        except Exception:
            return False
