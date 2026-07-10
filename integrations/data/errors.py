"""Data provider errors."""


class DataClientError(Exception):
    """Infrastructure failure from a data provider (auth, rate limit, network)."""

    def __init__(self, message: str, *, status_code: int | None = None, path: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.path = path
