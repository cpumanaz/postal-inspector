"""Custom exceptions for Postal Inspector.

This module defines the exception hierarchy used throughout the
Postal Inspector package for error handling and reporting.
"""


class PostalInspectorError(Exception):
    """Base exception for all Postal Inspector errors.

    All custom exceptions in the postal_inspector package inherit from
    this class, allowing for broad exception catching when needed.

    Attributes:
        message: A human-readable description of the error.
    """

    def __init__(self, message: str = "An error occurred in Postal Inspector") -> None:
        """Initialize the exception with an optional message.

        Args:
            message: A description of the error that occurred.
        """
        self.message = message
        super().__init__(self.message)


class ConfigurationError(PostalInspectorError):
    """Raised when there is an error in the configuration.

    This exception is raised when configuration files are missing,
    malformed, or contain invalid values.
    """

    def __init__(self, message: str = "Configuration error") -> None:
        """Initialize the exception with an optional message.

        Args:
            message: A description of the configuration error.
        """
        super().__init__(message)


class DeliveryError(PostalInspectorError):
    """Raised when email delivery fails.

    This exception is raised when there are issues delivering
    or processing email messages.
    """

    def __init__(self, message: str = "Email delivery error") -> None:
        """Initialize the exception with an optional message.

        Args:
            message: A description of the delivery error.
        """
        super().__init__(message)


class ScanError(PostalInspectorError):
    """Raised when email scanning fails.

    This exception is raised when the security scanning process
    encounters an error or cannot complete successfully.
    """

    def __init__(self, message: str = "Email scan error") -> None:
        """Initialize the exception with an optional message.

        Args:
            message: A description of the scan error.
        """
        super().__init__(message)


class RateLimitError(PostalInspectorError):
    """Raised when a rate limit is exceeded.

    This exception is raised when API rate limits or other
    throttling mechanisms are triggered.

    Attributes:
        retry_after: Optional number of seconds to wait before retrying.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
    ) -> None:
        """Initialize the exception with an optional message and retry time.

        Args:
            message: A description of the rate limit error.
            retry_after: Optional number of seconds to wait before retrying.
        """
        self.retry_after = retry_after
        super().__init__(message)
