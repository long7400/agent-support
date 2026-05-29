import re
import unicodedata
from collections.abc import Mapping

SECRET_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "passwd",
    "credential",
    "apikey",
    "privatekey",
    "accesskey",
    "clientsecret",
    "authorization",
    "authheader",
    "bearer",
)
SECRET_VALUE_PARTS = (
    "authorization:",
    "bearer ",
    "basic ",
    "api-key",
    "x-api-key",
    "private_key",
    "access_key",
    "password=",
    "token=",
)

NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def normalized_key_text(key: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(key)).casefold()
    return NON_ALNUM_PATTERN.sub("", normalized)


def has_non_ascii_text(value: object) -> bool:
    normalized = unicodedata.normalize("NFKC", str(value))
    return any(ord(character) > 127 for character in normalized)


def is_secret_like_key(key: object) -> bool:
    key_text = normalized_key_text(key)
    return has_non_ascii_text(key) or any(part in key_text for part in SECRET_KEY_PARTS)


def is_secret_like_string(value: str) -> bool:
    value_text = unicodedata.normalize("NFKC", value).casefold()
    return any(part in value_text for part in SECRET_VALUE_PARTS)


def secret_like_paths(value: object, *, prefix: str = "") -> list[str]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if is_secret_like_key(key):
                paths.append(path)
            paths.extend(secret_like_paths(item, prefix=path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            paths.extend(secret_like_paths(item, prefix=path))
        return paths
    if isinstance(value, str) and is_secret_like_string(value):
        return [prefix or "<value>"]
    return []


def redact_sensitive_value(value: object) -> object:
    if isinstance(value, Mapping):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if is_secret_like_key(key):
                redacted[key_text] = "[REDACTED]"
            else:
                redacted[key_text] = redact_sensitive_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]
    if isinstance(value, str) and is_secret_like_string(value):
        return "[REDACTED]"
    return value
