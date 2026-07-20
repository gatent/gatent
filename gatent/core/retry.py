"""Retry helpers used by per-stage retry semantics."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

from gatent.core.types import TransientError

T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: list[int] = field(default_factory=lambda: [1, 5, 30])
    retry_on: tuple[type, ...] = (TransientError,)


async def with_retry(fn: Callable[[], Awaitable[T]], policy: RetryPolicy) -> T:
    last_exc: Exception = RuntimeError("with_retry called with max_attempts < 1")
    for attempt in range(policy.max_attempts):
        try:
            return await fn()
        except policy.retry_on as e:
            last_exc = e
            if attempt == policy.max_attempts - 1:
                raise
            sleep_for = policy.backoff_seconds[
                min(attempt, len(policy.backoff_seconds) - 1)
            ]
            await asyncio.sleep(sleep_for)
    raise last_exc
