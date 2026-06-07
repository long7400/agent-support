"""Harness runtime errors.

All errors are typed so middleware and the runner can handle them by type
without inspecting string messages.
"""


class HarnessError(Exception):
    """Base error for all harness runtime errors."""


class TenantIdImmutableError(HarnessError):
    """Raised when code attempts to change tenant_id after hydration."""


class HarnessRunError(HarnessError):
    """Raised when a harness run fails irrecoverably."""


class TenantDisabledError(HarnessError):
    """Raised when processing is attempted for a disabled/suspended tenant."""


class PolicyDeniedError(HarnessError):
    """Raised when a policy check fails (model, tool, outbound, etc.)."""


class CapabilityDeniedError(HarnessError):
    """Raised when a capability/tool is not allowed for the current run."""
