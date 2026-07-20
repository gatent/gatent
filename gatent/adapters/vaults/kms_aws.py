"""AWS KMS-backed KMS client.

The KEK is an AWS KMS Customer Managed Key (CMK). KMS performs wrap/unwrap
server-side; the KEK never reaches Gatent's process memory.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import boto3


@dataclass
class AwsKmsClient:
    """AWS KMS-backed KEK.

    `kek_id` is the KMS key ARN or alias (e.g. `alias/gatent-vault-kek`).
    Region is inferred from environment / IAM role.
    """
    kek_arn: str
    region: str | None = None

    def __post_init__(self):
        kwargs = {"region_name": self.region} if self.region else {}
        self._client = boto3.client("kms", **kwargs)

    @property
    def kek_id(self) -> str:
        return self.kek_arn

    async def wrap_dek(self, dek: bytes) -> bytes:
        """KMS Encrypt API call. Returns CiphertextBlob."""
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: self._client.encrypt(KeyId=self.kek_arn, Plaintext=dek),
        )
        return resp["CiphertextBlob"]

    async def unwrap_dek(self, wrapped_dek: bytes) -> bytes:
        """KMS Decrypt API call. Returns the plaintext DEK."""
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: self._client.decrypt(
                CiphertextBlob=wrapped_dek,
                KeyId=self.kek_arn,
            ),
        )
        return resp["Plaintext"]
