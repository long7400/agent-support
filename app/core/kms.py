"""KMS provider interface and phase-0 provider stubs."""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from typing import Protocol

from app.core.config import (
    Environment,
    settings,
)


class KMSProvider(Protocol):
    """Interface for envelope encryption provider implementations."""

    async def encrypt(self, plaintext: bytes) -> str:
        """Encrypt plaintext and return an opaque handle."""
        ...

    async def decrypt(self, handle: str) -> bytes:
        """Decrypt an opaque handle returned by ``encrypt``."""
        ...


class KMSConfigurationError(RuntimeError):
    """Raised when KMS configuration is unsafe or incomplete."""


def _derive_stream(secret: bytes, nonce: bytes, length: int) -> bytes:
    """Derive a deterministic byte stream for the local development provider."""
    blocks: list[bytes] = []
    counter = 0
    while sum(len(block) for block in blocks) < length:
        counter_bytes = counter.to_bytes(4, "big")
        blocks.append(hmac.new(secret, nonce + counter_bytes, hashlib.sha256).digest())
        counter += 1
    return b"".join(blocks)[:length]


@dataclass(frozen=True)
class LocalKMSProvider:
    """Development-only KMS provider.

    This provider prevents accidental plaintext persistence during local work,
    but it is intentionally rejected in production by runtime guardrails.
    """

    secret: str

    def _secret_bytes(self) -> bytes:
        return self.secret.encode("utf-8")

    async def encrypt(self, plaintext: bytes) -> str:
        """Encrypt plaintext with a local development key."""
        nonce = secrets.token_bytes(16)
        secret_bytes = self._secret_bytes()
        stream = _derive_stream(secret_bytes, nonce, len(plaintext))
        ciphertext = bytes(left ^ right for left, right in zip(plaintext, stream, strict=True))
        tag = hmac.new(secret_bytes, nonce + ciphertext, hashlib.sha256).digest()
        payload = {
            "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
            "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
            "tag": base64.urlsafe_b64encode(tag).decode("ascii"),
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode("utf-8")).decode("ascii")
        return f"local:v1:{encoded}"

    async def decrypt(self, handle: str) -> bytes:
        """Decrypt a handle produced by the local development provider."""
        if not handle.startswith("local:v1:"):
            raise KMSConfigurationError("unsupported local kms handle")
        try:
            payload_raw = base64.urlsafe_b64decode(handle.removeprefix("local:v1:").encode("ascii"))
            payload = json.loads(payload_raw.decode("utf-8"))
            nonce = base64.urlsafe_b64decode(payload["nonce"].encode("ascii"))
            ciphertext = base64.urlsafe_b64decode(payload["ciphertext"].encode("ascii"))
            tag = base64.urlsafe_b64decode(payload["tag"].encode("ascii"))
        except (binascii.Error, KeyError, TypeError, UnicodeDecodeError, ValueError) as exc:
            raise KMSConfigurationError("invalid local kms handle") from exc
        secret_bytes = self._secret_bytes()
        expected = hmac.new(secret_bytes, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise KMSConfigurationError("local kms handle failed authentication")
        stream = _derive_stream(secret_bytes, nonce, len(ciphertext))
        return bytes(left ^ right for left, right in zip(ciphertext, stream, strict=True))


@dataclass(frozen=True)
class CloudKMSProvider:
    """GCP Cloud KMS provider placeholder.

    Phase 0 establishes the provider boundary. The concrete GCP client is wired
    when production credential handling is implemented.
    """

    key_name: str

    async def encrypt(self, plaintext: bytes) -> str:
        """Encrypt plaintext with GCP Cloud KMS."""
        raise NotImplementedError("cloud kms encryption is not wired in phase 0")

    async def decrypt(self, handle: str) -> bytes:
        """Decrypt a handle with GCP Cloud KMS."""
        raise NotImplementedError("cloud kms decryption is not wired in phase 0")


def get_kms_provider() -> KMSProvider:
    """Build the configured KMS provider."""
    if settings.KMS_PROVIDER == "local":
        secret = settings.LOCAL_KMS_SECRET or settings.JWT_SECRET_KEY or "dev-only-insecure-local-kms-key"
        return LocalKMSProvider(secret=secret)

    if settings.KMS_PROVIDER == "gcp":
        if not settings.GCP_KMS_KEY_NAME:
            raise KMSConfigurationError("GCP_KMS_KEY_NAME is required when KMS_PROVIDER=gcp")
        return CloudKMSProvider(key_name=settings.GCP_KMS_KEY_NAME)

    raise KMSConfigurationError("unsupported kms provider")


def validate_kms_configuration() -> None:
    """Validate KMS settings for the current runtime environment."""
    if settings.ENVIRONMENT == Environment.PRODUCTION and settings.KMS_PROVIDER == "local":
        raise KMSConfigurationError("local kms provider is not allowed in production")
    get_kms_provider()
