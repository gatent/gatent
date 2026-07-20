"""Local Python runner: httpx + lxml. No browser.

Supports navigate steps: goto, api_call, wait_for, submit_form (form-encoded
POST), extract_inline. Does NOT support: click, scroll_to_bottom, screenshot,
pdf_render, anything requiring DOM events. For those, use the Modal/browser
runners (later packs).
"""
from __future__ import annotations

import asyncio

import httpx

from gatent.adapters.base import Runner
from gatent.adapters.registry import registry
from gatent.core.types import (
    Module,
    NavigationResult,
    PipelineContext,
    PermanentError,
    RunnerCapabilityError,
    TransientError,
)

_SUPPORTED_STEPS = {"goto", "api_call", "wait_for", "submit_form", "extract_inline"}


@registry.runner("local_python")
class LocalPythonRunner(Runner):
    def __init__(self):
        self._timeout = httpx.Timeout(30.0, connect=10.0)

    def supports(self, navigate_step: dict) -> bool:
        return navigate_step.get("type") in _SUPPORTED_STEPS

    async def navigate(
        self, module: Module, ctx: PipelineContext
    ) -> NavigationResult:
        steps = module.config.get("navigate", {}).get("steps", [])
        for step in steps:
            if not self.supports(step):
                raise RunnerCapabilityError(
                    f"local_python runner does not support step type "
                    f"'{step.get('type')}'. Supported: {sorted(_SUPPORTED_STEPS)}"
                )

        result = NavigationResult()
        headers = self._build_headers(module, ctx)
        cookies: dict = {}

        async with httpx.AsyncClient(
            timeout=self._timeout,
            cookies=cookies,
            follow_redirects=True,
        ) as client:
            for step in steps:
                stype = step["type"]
                if stype == "goto":
                    result = await self._step_goto(client, step, result, headers)
                elif stype == "api_call":
                    result = await self._step_api(client, step, result, headers)
                elif stype == "submit_form":
                    result = await self._step_submit(client, step, result, headers)
                elif stype == "wait_for":
                    await asyncio.sleep(float(step.get("seconds", 0.5)))
                elif stype == "extract_inline":
                    pass  # extractor handles it
            result.cookies = dict(client.cookies)

        return result

    @staticmethod
    def _build_headers(module: Module, ctx: PipelineContext) -> dict:
        headers = {"User-Agent": "gatent/0.1 (+https://gatent.app)"}
        extra = module.config.get("navigate", {}).get("headers", {})
        headers.update(extra)
        if ctx.auth and ctx.auth.kind == "api_key":
            token_header = ctx.auth.metadata.get("token_header", "Authorization")
            token_prefix = ctx.auth.metadata.get("token_prefix", "Bearer ")
            headers[token_header] = f"{token_prefix}{ctx.auth.secrets['token']}"
        return headers

    @staticmethod
    async def _step_goto(client, step, result, headers) -> NavigationResult:
        url = step["url"]
        try:
            resp = await client.get(url, headers=headers)
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            raise TransientError(f"GET {url} failed: {e}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise TransientError(f"GET {url} returned {resp.status_code}")
        if resp.status_code >= 400:
            raise PermanentError(f"GET {url} returned {resp.status_code}")
        result.rendered_html = resp.text
        result.final_url = str(resp.url)
        return result

    @staticmethod
    async def _step_api(client, step, result, headers) -> NavigationResult:
        method = step.get("method", "GET").upper()
        url = step["url"]
        try:
            resp = await client.request(
                method, url, headers=headers,
                json=step.get("body") if method in ("POST", "PUT", "PATCH") else None,
            )
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            raise TransientError(f"{method} {url} failed: {e}")
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise TransientError(f"{method} {url} returned {resp.status_code}")
        if resp.status_code >= 400:
            raise PermanentError(f"{method} {url} returned {resp.status_code}")
        try:
            result.api_response = resp.json()
        except Exception:
            result.api_response = {"_text": resp.text}
        result.final_url = str(resp.url)
        return result

    @staticmethod
    async def _step_submit(client, step, result, headers) -> NavigationResult:
        url = step["url"]
        form_data = step.get("form_data", {})
        try:
            resp = await client.post(url, headers=headers, data=form_data)
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            raise TransientError(f"POST {url} failed: {e}")
        if resp.status_code >= 500:
            raise TransientError(f"POST {url} returned {resp.status_code}")
        result.rendered_html = resp.text
        result.final_url = str(resp.url)
        return result
