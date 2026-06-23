"""Shared helpers for classifying LLM provider failures in logs and fallback logic."""


def classify_provider_error(exc: Exception) -> str:
    """Return a short category label for logging: quota, transient, config, or other."""
    msg = str(exc).lower()
    code = getattr(exc, "code", None)
    status = getattr(exc, "status_code", None)

    if (
        code == 429
        or status == 429
        or "resource_exhausted" in msg
        or "rate limit" in msg
        or "rate-limit" in msg
        or "quota" in msg
        or "daily limit" in msg
    ):
        return "quota"

    if (
        code in (503, 500, 502, 504)
        or status in (503, 500, 502, 504)
        or "unavailable" in msg
        or "high demand" in msg
        or "timeout" in msg
        or "timed out" in msg
    ):
        return "transient"

    if (
        code == 400
        or status == 400
        or "invalid_request" in msg
        or "json_schema" in msg
        or "response_format" in msg
        or "does not support" in msg
    ):
        return "config"

    return "other"
