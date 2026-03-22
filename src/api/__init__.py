class APIRequestError(Exception):
    """Raised when a network-level failure occurs and no response is received."""


class APIResponseError(Exception):
    """Raised when the API returns an HTTP error response."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
