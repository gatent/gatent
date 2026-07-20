"""Vault adapters: envelope encryption, KMS clients, cloud vault.

Cloud vault deps (cryptography, boto3, asyncpg) are optional - install with
`pip install -e ".[cloud]"`. Importing this package directly requires them;
solo_local profile never imports it.
"""
