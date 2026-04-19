"""Typed error hierarchy."""

from __future__ import annotations


class HetznerDDNSError(Exception):
    """Base exception for all project errors."""


class ConfigError(HetznerDDNSError):
    """Invalid or missing configuration."""


class ValidationError(HetznerDDNSError):
    """Input failed validation (zone/record/IP format)."""


class APIError(HetznerDDNSError):
    """Hetzner API returned an error response."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class AuthError(APIError):
    """API token invalid or lacks permission."""


class RateLimitError(APIError):
    """API rate-limit hit (HTTP 429)."""


class TransientAPIError(APIError):
    """Temporary API failure worth retrying."""


class IPLookupError(HetznerDDNSError):
    """Public IP could not be determined."""
