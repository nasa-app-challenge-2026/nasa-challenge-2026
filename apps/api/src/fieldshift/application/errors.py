"""Errors the application reports to its callers. Messages are safe to show to users."""

from __future__ import annotations


class ApplicationError(Exception):
    code = "application_error"

    def __init__(self, message_fr: str) -> None:
        super().__init__(message_fr)
        self.message_fr = message_fr


class InvalidAnalysisRequestError(ApplicationError):
    code = "invalid_request"


class UnsupportedLocationError(ApplicationError):
    code = "unsupported_location"


class ClimateDataUnavailableError(ApplicationError):
    """No usable climate data: provider down and no verified snapshot, or empty response."""

    code = "climate_data_unavailable"


class ClimateProviderRateLimitedError(ClimateDataUnavailableError):
    code = "climate_provider_rate_limited"
