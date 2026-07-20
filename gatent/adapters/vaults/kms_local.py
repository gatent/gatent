"""Filesystem-backed KMS for development and single-tenant self-hosted.

DO NOT use this in production multi-tenant deployments. The KEK lives on disk
at `kek_path`; protect it with file permissions (0600) and full-disk encryption.

For production cloud, use AwsKmsClient (or equivalent KMS).
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class LocalKmsClient:
    """Filesystem KEK. Wraps DEKs with AES-256-GCM using the on-disk KEK.

    The 'kek_id' is the SHA-256 hash of the KEK bytes - stable across processes,
    changes iff the KEK is rotated.
    """

    def __init__(self, kek_path: str = "~/.gatent/kek.bin"):
        self.kek_path = Path(kek_path).expanduser()
        self.kek_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.kek_path.exists():
            self._generate_kek()
        self._kek = self.kek_path.read_bytes()
        if len(self._kek) != 32:
            raise ValueError(
                f"KEK at {self.kek_path} must be exactly 32 bytes; "
                f"got {len(self._kek)}. Delete and regenerate."
            )
        self._kek_id = "sha256:" + hashlib.sha256(self._kek).hexdigest()[:16]

    def _generate_kek(self) -> None:
        kek = AESGCM.generate_key(bit_length=256)
        self.kek_path.write_bytes(kek)
        os.chmod(self.kek_path, 0o600)

    @property
    def kek_id(self) -> str:
        return self._kek_id

    async def wrap_dek(self, dek: bytes) -> bytes:
        nonce = os.urandom(12)
        cipher = AESGCM(self._kek)
        ciphertext = cipher.encrypt(nonce, dek, b"gatent.kek.wrap")
        return nonce + ciphertext

    async def unwrap_dek(self, wrapped_dek: bytes) -> bytes:
        nonce = wrapped_dek[:12]
        ciphertext = wrapped_dek[12:]
        cipher = AESGCM(self._kek)
        return cipher.decrypt(nonce, ciphertext, b"gatent.kek.wrap")
