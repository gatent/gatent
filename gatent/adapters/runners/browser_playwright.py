"""Playwright browser runner — the capable runner for real JS / login-walled sites.

Counterpart to local_python (httpx+lxml, static only). Implements the Runner
contract for DOM-driven navigation: goto, click, fill, submit_form, scroll,
scroll_to_bottom, wait_for, wait_for_selector, screenshot.

Auth: a browser auth profile carries a Playwright storage_state (cookies +
localStorage) in ctx.auth.secrets. The context is seeded with it so a stored
session is replayed instead of re-logging-in every run — the auth-vault
dependency vector made concrete.

Run-record: captures rendered_html + a full-page screenshot to an archive dir
(best-effort; never fails a run on archive I/O).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from gatent.adapters.base import Runner
from gatent.adapters.registry import registry
from gatent.core.types import (
    Module,
    NavigationResult,
    PermanentError,
    PipelineContext,
    RunnerCapabilityError,
    TransientError,
)

# Every step type the browser runner can execute. Superset of local_python.
_SUPPORTED_STEPS = {
    "goto", "wait_for", "wait_for_selector", "click", "fill", "type",
    "submit_form", "scroll", "scroll_to_bottom", "screenshot", "extract_inline",
}

_DEFAULT_NAV_TIMEOUT_MS = 30_000
_DEFAULT_ARCHIVE_DIR = "./run_archive"


@registry.runner("browser_playwright")
class BrowserPlaywrightRunner(Runner):
    """Headless-Chromium runner. One fresh context per run, seeded with the
    auth profile's storage_state for session reuse."""

    def __init__(self, runner_config: Optional[dict] = None):
        cfg = runner_config or {}
        self._headless: bool = cfg.get("headless", True)
        self._nav_timeout_ms: int = cfg.get("nav_timeout_ms", _DEFAULT_NAV_TIMEOUT_MS)
        # Env-driven archive dir (GATENT_ARCHIVE_DIR=/archive in the Modal cloud
        # profile lands snapshots on the persistent gatent-run-archive volume).
        archive_dir = cfg.get("archive_dir") or os.environ.get(
            "GATENT_ARCHIVE_DIR", _DEFAULT_ARCHIVE_DIR
        )
        self._archive_dir = Path(archive_dir).expanduser()

    def supports(self, navigate_step: dict) -> bool:
        return navigate_step.get("type") in _SUPPORTED_STEPS

    async def navigate(self, module: Module, ctx: PipelineContext) -> NavigationResult:
        nav = module.config.get("navigate", {})
        steps = nav.get("steps", [])
        for step in steps:
            if not self.supports(step):
                raise RunnerCapabilityError(
                    f"browser_playwright does not support step type "
                    f"'{step.get('type')}'. Supported: {sorted(_SUPPORTED_STEPS)}"
                )

        result = NavigationResult()
        storage_state = self._auth_storage_state(ctx)

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=self._headless)
                try:
                    context = await browser.new_context(
                        storage_state=storage_state,
                        user_agent=nav.get(
                            "user_agent", "gatent/0.1 (+https://gatent.app)"
                        ),
                    )
                    context.set_default_timeout(self._nav_timeout_ms)
                    page = await context.new_page()

                    for step in steps:
                        await self._run_step(page, step, module)

                    result.rendered_html = await page.content()
                    result.final_url = page.url
                    result.cookies = {
                        c["name"]: c["value"] for c in await context.cookies()
                    }
                    await self._snapshot(page, module, result)
                finally:
                    await browser.close()
        except PlaywrightTimeoutError as e:
            raise TransientError(f"browser navigation timed out: {e}")
        except PlaywrightError as e:
            # Network / navigation-level Playwright errors are usually transient.
            raise TransientError(f"browser navigation error: {e}")

        return result

    # ------------------------------------------------------------------ steps
    async def _run_step(self, page, step: dict, module: Module) -> None:
        stype = step["type"]
        try:
            if stype == "goto":
                resp = await page.goto(step["url"], wait_until=step.get("wait_until", "load"))
                if resp is not None and resp.status >= 400:
                    if resp.status == 429 or resp.status >= 500:
                        raise TransientError(f"GET {step['url']} -> {resp.status}")
                    raise PermanentError(f"GET {step['url']} -> {resp.status}")
            elif stype == "wait_for":
                await page.wait_for_timeout(float(step.get("seconds", 0.5)) * 1000)
            elif stype == "wait_for_selector":
                await page.wait_for_selector(step["selector"])
            elif stype == "click":
                await page.click(step["selector"])
            elif stype in ("fill", "type"):
                await page.fill(step["selector"], str(step.get("value", "")))
            elif stype == "submit_form":
                for field in step.get("fields", []):
                    await page.fill(field["selector"], str(field.get("value", "")))
                if step.get("submit_selector"):
                    await page.click(step["submit_selector"])
                else:
                    await page.keyboard.press("Enter")
                if step.get("wait_for_selector"):
                    await page.wait_for_selector(step["wait_for_selector"])
            elif stype == "scroll_to_bottom":
                await self._scroll_to_bottom(page, max_rounds=int(step.get("max_rounds", 20)))
            elif stype == "scroll":
                await page.mouse.wheel(0, int(step.get("pixels", 1000)))
            elif stype == "screenshot":
                await self._write_screenshot(page, module, label=step.get("label", "step"))
            elif stype == "extract_inline":
                pass  # the extractor consumes rendered_html
        except (TransientError, PermanentError, RunnerCapabilityError):
            raise
        except PlaywrightTimeoutError as e:
            raise TransientError(f"step '{stype}' timed out: {e}")
        except KeyError as e:
            raise PermanentError(f"step '{stype}' missing required key: {e}")

    @staticmethod
    async def _scroll_to_bottom(page, max_rounds: int) -> None:
        """Scroll until the page height stops growing (infinite-scroll pages)."""
        last_height = await page.evaluate("document.body.scrollHeight")
        for _ in range(max_rounds):
            await page.mouse.wheel(0, last_height)
            await page.wait_for_timeout(600)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                return
            last_height = new_height

    # ----------------------------------------------------------- run-record
    async def _snapshot(self, page, module: Module, result: NavigationResult) -> None:
        try:
            base = self._run_dir(module)
            (base / "page.html").write_text(result.rendered_html or "", encoding="utf-8")
            await page.screenshot(path=str(base / "page.png"), full_page=True)
        except Exception:
            pass  # snapshots are best-effort

    async def _write_screenshot(self, page, module: Module, label: str) -> None:
        try:
            base = self._run_dir(module)
            await page.screenshot(path=str(base / f"{label}.png"), full_page=True)
        except Exception:
            pass

    def _run_dir(self, module: Module) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        d = self._archive_dir / module.module_id / ts
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---------------------------------------------------------------- auth
    @staticmethod
    def _auth_storage_state(ctx: PipelineContext) -> Optional[dict]:
        """Pull a Playwright storage_state out of the auth profile, if present."""
        auth = getattr(ctx, "auth", None)
        if not auth:
            return None
        if getattr(auth, "kind", None) not in ("storage_state", "browser_session", "cookies"):
            return None
        raw = auth.secrets.get("storage_state")
        if raw is not None:
            return json.loads(raw) if isinstance(raw, str) else raw
        cookies = auth.secrets.get("cookies")  # cookies-only profile
        return {"cookies": cookies, "origins": []} if cookies else None
