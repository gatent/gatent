"""Postgres-backed vault storage. asyncpg.

Schema migrates on first connect.
"""
from __future__ import annotations

from typing import Optional

import asyncpg

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_profiles (
    profile_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    wrapped_secret_json JSONB NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rotated_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_vault_kind ON vault_profiles(kind);
"""


class PostgresVaultStorage:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def _ensure(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=10)
            async with self._pool.acquire() as conn:
                await conn.execute(_SCHEMA)
        return self._pool

    async def write_profile(
        self, profile_id, kind, wrapped_secret_json, metadata_json
    ) -> None:
        pool = await self._ensure()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO vault_profiles
                    (profile_id, kind, wrapped_secret_json, metadata_json)
                VALUES ($1, $2, $3::jsonb, $4::jsonb)
                ON CONFLICT (profile_id) DO UPDATE SET
                    kind = EXCLUDED.kind,
                    wrapped_secret_json = EXCLUDED.wrapped_secret_json,
                    metadata_json = EXCLUDED.metadata_json,
                    rotated_at = NOW()
                """,
                profile_id, kind, wrapped_secret_json, metadata_json,
            )

    async def read_profile(self, profile_id):
        pool = await self._ensure()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM vault_profiles WHERE profile_id = $1", profile_id
            )
            return dict(row) if row else None

    async def update_last_used(self, profile_id, when):
        pool = await self._ensure()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE vault_profiles SET last_used_at = $1 WHERE profile_id = $2",
                when, profile_id,
            )

    async def update_rotated(self, profile_id, wrapped_secret_json, when):
        pool = await self._ensure()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE vault_profiles
                SET wrapped_secret_json = $1::jsonb, rotated_at = $2
                WHERE profile_id = $3
                """,
                wrapped_secret_json, when, profile_id,
            )

    async def delete_profile(self, profile_id):
        pool = await self._ensure()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM vault_profiles WHERE profile_id = $1", profile_id
            )

    async def list_profiles(self):
        pool = await self._ensure()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM vault_profiles ORDER BY created_at DESC")
            return [dict(r) for r in rows]
