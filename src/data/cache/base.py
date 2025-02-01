from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


class AbstractCache(ABC, Generic[T]):
    """Abstract base class for cache implementations."""

    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        pass

    @abstractmethod
    def set(self, key: str, value: T) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

    @abstractmethod
    def remove(self, key: str) -> None:
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        pass
