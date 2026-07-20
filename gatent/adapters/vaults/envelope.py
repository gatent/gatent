"""Envelope encryption: AES-256-GCM with KMS-wrapped DEK."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class WrappedSecret:
    """What gets persisted: ciphertext + metadata. DEK is NOT here - it's wrapped."""
    ciphertext_b64: str
    nonce_b64: str
    wrapped_dek_b64: str
    kek_id: str
    aad_b64: str

    def to_dict(self) -> dict:
        return {
            "ciphertext_b64": self.ciphertext_b64,
            "nonce_b64": self.nonce_b64,
            "wrapped_dek_b64": self.wrapped_dek_b64,
            "kek_id": self.kek_id,
            "aad_b64": self.aad_b64,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WrappedSecret":
        return cls(
            ciphertext_b64=data["ciphertext_b64"],
            nonce_b64=data["nonce_b64"],
            wrapped_dek_b64=data["wrapped_dek_b64"],
            kek_id=data["kek_id"],
            aad_b64=data["aad_b64"],
        )


class KmsClient(Protocol):
    """KMS interface. AwsKmsClient and LocalKmsClient both implement this."""

    @property
    def kek_id(self) -> str: ...

    async def wrap_dek(self, dek: bytes) -> bytes:
        """Encrypt a DEK with the KEK. Never returns the KEK itself."""
        ...

    async def unwrap_dek(self, wrapped_dek: bytes) -> bytes:
        """Decrypt a wrapped DEK using the KEK. The KEK never leaves KMS."""
        ...


class EnvelopeEncryption:
    """Encrypt/decrypt secrets using envelope pattern with a KMS.

    Each call to `encrypt` generates a fresh DEK, encrypts the plaintext, then
    asks KMS to wrap the DEK. Decryption reverses: KMS unwraps the DEK,
    AES-256-GCM decrypts the ciphertext.
    """

    def __init__(self, kms: KmsClient):
        self.kms = kms

    async def encrypt(self, plaintext: bytes, aad: bytes = b"") -> WrappedSecret:
        """Encrypt plaintext, returning a WrappedSecret safe to persist.

        `aad` (additional authenticated data) is bound to the ciphertext but not
        encrypted. Used to defend against ciphertext substitution: pass the
        profile_id so a ciphertext for profile A can't be swapped to profile B.
        """
        dek = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(12)
        cipher = AESGCM(dek)
        ciphertext = cipher.encrypt(nonce, plaintext, aad)
        wrapped_dek = await self.kms.wrap_dek(dek)
        return WrappedSecret(
            ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
            nonce_b64=base64.b64encode(nonce).decode("ascii"),
            wrapped_dek_b64=base64.b64encode(wrapped_dek).decode("ascii"),
            kek_id=self.kms.kek_id,
            aad_b64=base64.b64encode(aad).decode("ascii"),
        )

    async def decrypt(self, wrapped: WrappedSecret) -> bytes:
        """Decrypt a WrappedSecret back to plaintext.

        Raises if AAD doesn't match - protects against ciphertext substitution.
        """
        wrapped_dek = base64.b64decode(wrapped.wrapped_dek_b64)
        dek = await self.kms.unwrap_dek(wrapped_dek)
        try:
            cipher = AESGCM(dek)
            ciphertext = base64.b64decode(wrapped.ciphertext_b64)
            nonce = base64.b64decode(wrapped.nonce_b64)
            aad = base64.b64decode(wrapped.aad_b64)
            return cipher.decrypt(nonce, ciphertext, aad)
        finally:
            # Best-effort scrub of the DEK from local memory.
            del dek
