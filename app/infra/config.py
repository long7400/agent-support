"""Application configuration management.

This module handles environment-specific configuration loading, parsing, and management
for the application. It includes environment detection, .env file loading, and
configuration value parsing.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


# Define environment types
class Environment(str, Enum):
    """Application environment types.

    Defines the possible environments the application can run in:
    development, staging, production, and test.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


# Determine environment
def get_environment() -> Environment:
    """Get the current environment.

    Returns:
        Environment: The current environment (development, staging, production, or test)
    """
    match os.getenv("APP_ENV", "development").lower():
        case "production" | "prod":
            return Environment.PRODUCTION
        case "staging" | "stage":
            return Environment.STAGING
        case "test":
            return Environment.TEST
        case _:
            return Environment.DEVELOPMENT


# Load appropriate .env file based on environment
def load_env_file():
    """Load environment-specific .env file."""
    env = get_environment()
    print(f"Loading environment: {env}")
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    # Define env files in priority order
    env_files = [
        os.path.join(base_dir, f".env.{env.value}.local"),
        os.path.join(base_dir, f".env.{env.value}"),
        os.path.join(base_dir, ".env.local"),
        os.path.join(base_dir, ".env"),
    ]

    # Load the first env file that exists
    for env_file in env_files:
        if os.path.isfile(env_file):
            load_dotenv(dotenv_path=env_file)
            print(f"Loaded environment from {env_file}")
            return env_file

    # Fall back to default if no env file found
    return None


ENV_FILE = load_env_file()


# Parse list values from environment variables
def parse_bool_from_env(env_key: str, default: bool = False) -> bool:
    """Parse a boolean value from an environment variable."""
    value = os.getenv(env_key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "t", "yes", "y", "on")


def parse_list_from_env(env_key, default=None):
    """Parse a comma-separated list from an environment variable."""
    value = os.getenv(env_key)
    if not value:
        return default or []

    # Remove quotes if they exist
    value = value.strip("\"'")
    # Handle single value case
    if "," not in value:
        return [value]
    # Split comma-separated values
    return [item.strip() for item in value.split(",") if item.strip()]


# Parse dict of lists from environment variables with prefix
def parse_dict_of_lists_from_env(prefix, default_dict=None):
    """Parse dictionary of lists from environment variables with a common prefix."""
    result = default_dict or {}

    # Look for all env vars with the given prefix
    for key, value in os.environ.items():
        if key.startswith(prefix):
            endpoint = key[len(prefix) :].lower()  # Extract endpoint name
            # Parse the values for this endpoint
            if value:
                value = value.strip("\"'")
                if "," in value:
                    result[endpoint] = [item.strip() for item in value.split(",") if item.strip()]
                else:
                    result[endpoint] = [value]

    return result


class Settings:
    """Application settings without using pydantic."""

    def __init__(self):
        """Initialize application settings from environment variables.

        Loads and sets all configuration values from environment variables,
        with appropriate defaults for each setting. Also applies
        environment-specific overrides based on the current environment.
        """
        # Set the environment
        self.ENVIRONMENT = get_environment()

        # Application Settings
        self.PROJECT_NAME = os.getenv("PROJECT_NAME", "Agent Support")
        self.VERSION = os.getenv("VERSION", "0.1.0")
        self.DESCRIPTION = os.getenv("DESCRIPTION", "Tenant-isolated FastAPI and LangGraph community support backend")
        self.API_V1_STR = os.getenv("API_V1_STR", "/api/v1")
        self.DEBUG = parse_bool_from_env("DEBUG", False)

        # CORS Settings
        self.ALLOWED_ORIGINS = parse_list_from_env("ALLOWED_ORIGINS", ["*"])

        # Langfuse Configuration
        self.LANGFUSE_TRACING_ENABLED = parse_bool_from_env("LANGFUSE_TRACING_ENABLED", True)
        self.LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        self.LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
        self.LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

        # LangGraph Configuration
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.REQUIRE_OPENAI_API_KEY = parse_bool_from_env(
            "REQUIRE_OPENAI_API_KEY", self.ENVIRONMENT == Environment.PRODUCTION
        )
        self.DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gpt-5-mini")
        self.SESSION_NAMING_ENABLED = parse_bool_from_env("SESSION_NAMING_ENABLED", True)
        self.DEFAULT_LLM_TEMPERATURE = float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.2"))
        self.MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2000"))
        self.MAX_LLM_CALL_RETRIES = int(os.getenv("MAX_LLM_CALL_RETRIES", "3"))
        self.LLM_TOTAL_TIMEOUT = int(os.getenv("LLM_TOTAL_TIMEOUT", "60"))
        self.WEB_SEARCH_ENABLED = parse_bool_from_env("WEB_SEARCH_ENABLED", False)

        # Long term memory Configuration
        self.LONG_TERM_MEMORY_ENABLED = parse_bool_from_env("LONG_TERM_MEMORY_ENABLED", False)
        self.LONG_TERM_MEMORY_WRITE_ENABLED = parse_bool_from_env("LONG_TERM_MEMORY_WRITE_ENABLED", False)
        self.LONG_TERM_MEMORY_MODEL = os.getenv("LONG_TERM_MEMORY_MODEL", "gpt-5-nano")
        self.LONG_TERM_MEMORY_EMBEDDER_MODEL = os.getenv("LONG_TERM_MEMORY_EMBEDDER_MODEL", "text-embedding-3-small")
        self.LONG_TERM_MEMORY_COLLECTION_NAME = os.getenv("LONG_TERM_MEMORY_COLLECTION_NAME", "longterm_memory")

        # Tenant platform infrastructure
        self.QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
        self.QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_chunks")
        self.QDRANT_VECTOR_SIZE = int(os.getenv("QDRANT_VECTOR_SIZE", "384"))
        self.QDRANT_BATCH_SIZE = int(os.getenv("QDRANT_BATCH_SIZE", "64"))
        self.QDRANT_TOP_K_LIMIT = int(os.getenv("QDRANT_TOP_K_LIMIT", "50"))

        # Worker Configuration
        self.WORKER_ROLE = os.getenv("WORKER_ROLE", "runtime")
        self.WORKER_POLL_INTERVAL_SECONDS = float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "2.0"))
        self.WORKER_SHUTDOWN_GRACE_SECONDS = float(os.getenv("WORKER_SHUTDOWN_GRACE_SECONDS", "10.0"))

        # P2 Platform Ingest Configuration
        self.PROCESSING_CLAIM_BATCH_SIZE = int(os.getenv("PROCESSING_CLAIM_BATCH_SIZE", "10"))
        self.DELIVERY_CLAIM_BATCH_SIZE = int(os.getenv("DELIVERY_CLAIM_BATCH_SIZE", "10"))
        self.MAX_INFLIGHT_PER_TENANT = int(os.getenv("MAX_INFLIGHT_PER_TENANT", "5"))
        self.MAX_CONCURRENT_DELIVERIES = int(os.getenv("MAX_CONCURRENT_DELIVERIES", "20"))
        self.PROCESSING_STALE_AFTER_SECONDS = int(os.getenv("PROCESSING_STALE_AFTER_SECONDS", "120"))
        self.OUTBOX_POLL_INTERVAL_SECONDS = float(os.getenv("OUTBOX_POLL_INTERVAL_SECONDS", "5.0"))
        self.RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "5"))
        self.RETRY_BACKOFF_BASE_SECONDS = int(os.getenv("RETRY_BACKOFF_BASE_SECONDS", "2"))
        self.RETRY_BACKOFF_MAX_SECONDS = int(os.getenv("RETRY_BACKOFF_MAX_SECONDS", "300"))

        # Secret Management Configuration
        self.KMS_PROVIDER = os.getenv("KMS_PROVIDER", "local").lower()
        self.LOCAL_KMS_SECRET = os.getenv("LOCAL_KMS_SECRET", "")
        self.GCP_KMS_KEY_NAME = os.getenv("GCP_KMS_KEY_NAME", "")

        # JWT Configuration
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_DAYS", "30"))

        # Tenant control-plane configuration
        self.OPERATOR_API_KEYS = parse_list_from_env("OPERATOR_API_KEYS", [])

        # Logging Configuration
        self.LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" or "console"

        # Profiling Configuration (DEBUG only)
        self.PROFILING_DIR = Path(os.getenv("PROFILING_DIR", "/tmp/fastapi_profiles"))
        self.PROFILING_THRESHOLD_SECONDS = float(os.getenv("PROFILING_THRESHOLD_SECONDS", "2.0"))

        # Postgres Configuration
        self.POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
        self.POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
        self.POSTGRES_DB = os.getenv("POSTGRES_DB", "agent_support")
        self.POSTGRES_USER = os.getenv("POSTGRES_USER", "agent_support")
        self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
        self.POSTGRES_POOL_SIZE = int(os.getenv("POSTGRES_POOL_SIZE", "20"))
        self.POSTGRES_MAX_OVERFLOW = int(os.getenv("POSTGRES_MAX_OVERFLOW", "10"))
        self.CHECKPOINT_TABLES = ["checkpoint_blobs", "checkpoint_writes", "checkpoints"]

        # Valkey/Redis Cache Configuration (optional — if host is set, caching is enabled)
        self.VALKEY_HOST = os.getenv("VALKEY_HOST", "")
        self.VALKEY_PORT = int(os.getenv("VALKEY_PORT", "6379"))
        self.VALKEY_DB = int(os.getenv("VALKEY_DB", "0"))
        self.VALKEY_PASSWORD = os.getenv("VALKEY_PASSWORD", "")
        self.VALKEY_MAX_CONNECTIONS = int(os.getenv("VALKEY_MAX_CONNECTIONS", "20"))
        self.CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "60"))

        # Rate Limiting Configuration
        self.RATE_LIMIT_DEFAULT = parse_list_from_env("RATE_LIMIT_DEFAULT", ["200 per day", "50 per hour"])

        # Rate limit endpoints defaults
        default_endpoints = {
            "chat": ["30 per minute"],
            "chat_stream": ["20 per minute"],
            "messages": ["50 per minute"],
            "register": ["10 per hour"],
            "login": ["20 per minute"],
            "root": ["10 per minute"],
            "health": ["20 per minute"],
        }

        # Update rate limit endpoints from environment variables
        self.RATE_LIMIT_ENDPOINTS = default_endpoints.copy()
        for endpoint in default_endpoints:
            env_key = f"RATE_LIMIT_{endpoint.upper()}"
            value = parse_list_from_env(env_key)
            if value:
                self.RATE_LIMIT_ENDPOINTS[endpoint] = value

        # Evaluation Configuration
        self.EVALUATION_LLM = os.getenv("EVALUATION_LLM", "gpt-5")
        self.EVALUATION_BASE_URL = os.getenv("EVALUATION_BASE_URL", "https://api.openai.com/v1")
        self.EVALUATION_API_KEY = os.getenv("EVALUATION_API_KEY", self.OPENAI_API_KEY)
        self.EVALUATION_SLEEP_TIME = int(os.getenv("EVALUATION_SLEEP_TIME", "10"))

        # Apply environment-specific settings
        self.apply_environment_settings()

    def apply_environment_settings(self):
        """Apply environment-specific settings based on the current environment."""
        env_settings = {
            Environment.DEVELOPMENT: {
                "DEBUG": True,
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "console",
                "RATE_LIMIT_DEFAULT": ["1000 per day", "200 per hour"],
            },
            Environment.STAGING: {
                "DEBUG": False,
                "LOG_LEVEL": "INFO",
                "RATE_LIMIT_DEFAULT": ["500 per day", "100 per hour"],
            },
            Environment.PRODUCTION: {
                "DEBUG": False,
                "LOG_LEVEL": "WARNING",
                "RATE_LIMIT_DEFAULT": ["200 per day", "50 per hour"],
            },
            Environment.TEST: {
                "DEBUG": True,
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "console",
                "RATE_LIMIT_DEFAULT": ["1000 per day", "1000 per hour"],  # Relaxed for testing
            },
        }

        # Get settings for current environment
        current_env_settings = env_settings.get(self.ENVIRONMENT, {})

        # Apply settings if not explicitly set in environment variables
        for key, value in current_env_settings.items():
            env_var_name = key.upper()
            # Only override if environment variable wasn't explicitly set
            if env_var_name not in os.environ:
                setattr(self, key, value)

    def insecure_defaults(self) -> dict[str, Any]:
        """Return security-sensitive defaults that should not survive production."""
        return {
            "jwt_secret_key": self.JWT_SECRET_KEY
            in {"", "supersecretkeythatshouldbechangedforproduction", "replace-with-a-long-random-value"},
            "postgres_password": self.POSTGRES_PASSWORD in {"", "postgres", "agent_support_dev_password"},
            "local_kms_provider": self.KMS_PROVIDER == "local",
            "wildcard_cors": "*" in self.ALLOWED_ORIGINS,
            "openai_api_key_missing": self.REQUIRE_OPENAI_API_KEY and not self.OPENAI_API_KEY,
            "langfuse_tracing_disabled": not self.LANGFUSE_TRACING_ENABLED,
            "langfuse_keys_missing": self.LANGFUSE_TRACING_ENABLED
            and (not self.LANGFUSE_PUBLIC_KEY or not self.LANGFUSE_SECRET_KEY),
        }


# Create settings instance
settings = Settings()
