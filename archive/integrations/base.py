"""
Base Integration Classes

Abstract base classes for all external integrations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx


class BaseIntegration(ABC):
    """Base class for all external service integrations"""

    def __init__(self, api_base_url: str, api_key: Optional[str] = None):
        """
        Initialize integration.

        Args:
            api_base_url: URL of the analytics API
            api_key: API key for authentication (optional)
        """
        self.api_base_url = api_base_url
        self.api_key = api_key

        # Set up headers with API key if provided
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key

        self.client = httpx.AsyncClient(timeout=30.0, headers=headers)

    async def query_analytics_api(self, query: str) -> Dict[str, Any]:
        """
        Query the natural language analytics API.

        Args:
            query: Natural language question

        Returns:
            API response data
        """
        response = await self.client.post(
            f"{self.api_base_url}/api/mcp/query/natural-language",
            params={"query": query}
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Clean up resources"""
        await self.client.aclose()

    @abstractmethod
    async def setup(self) -> None:
        """Setup/initialize the integration"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if integration is healthy"""
        pass


class BaseFormatter(ABC):
    """Base class for response formatters"""

    @abstractmethod
    def format_churn_response(self, data: Dict[str, Any]) -> Any:
        """Format churn analysis response"""
        pass

    @abstractmethod
    def format_revenue_response(self, data: Dict[str, Any]) -> Any:
        """Format revenue forecast response"""
        pass

    @abstractmethod
    def format_seasonal_response(self, data: Dict[str, Any]) -> Any:
        """Format seasonal analysis response"""
        pass

    @abstractmethod
    def format_campaign_response(self, data: Dict[str, Any]) -> Any:
        """Format campaign targeting response"""
        pass
