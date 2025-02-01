from abc import ABC, abstractmethod
from typing import Any, Optional, Type

import requests
from pydantic import BaseModel
from requests.exceptions import RequestException

from .config import BaseAPIConfig


class BaseAPIClient(ABC):
    """Abstract base class for API clients."""

    def __init__(self, config: BaseAPIConfig):
        self.config = config
        self.headers = self._get_headers()

    @abstractmethod
    def _get_headers(self) -> dict[str, str]:
        """Return headers required for API requests."""
        pass

    def _handle_response(
        self, response: requests.Response, response_model: Type[BaseModel] = None
    ) -> BaseModel | dict[str, Any]:
        """Handle API response and return parsed data."""
        response.raise_for_status()
        return response_model(**response.json()) if response_model else response.json()

    def _get_base_url(self) -> str:
        """Implementation of abstract method for base URL."""
        return self.config.base_url

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        response_model: Type[BaseModel] = None,
    ) -> BaseModel | dict[str, Any]:
        """Make HTTP request to the API with error handling."""
        url = f"{self._get_base_url()}/{endpoint.lstrip('/')}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
            )
            return self._handle_response(response, response_model)
        except RequestException as e:
            raise Exception(f"API request failed: {str(e)}") from e

    def _get_data_or_raise(
        self, response_data: BaseModel, key: str, error_message: str
    ) -> Any:
        """Extract data from response or raise if not found."""
        if not hasattr(response_data, key):
            raise Exception(error_message)

        data = getattr(response_data, key)
        if not data:
            raise Exception(error_message)

        return data
