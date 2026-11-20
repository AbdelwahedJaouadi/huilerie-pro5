class UnsupportedProtocolError(ValueError):
    """Raised when no explicitly registered driver supports a configured protocol."""


class InvalidScaleSampleError(ValueError):
    """Raised when a device driver returns a malformed or unsafe sample."""
