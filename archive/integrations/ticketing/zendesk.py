"""
Zendesk Integration

Create and manage tickets in Zendesk from customer analytics.
"""
import logging
from typing import Dict, Any, Optional
import httpx

from .base_ticketing import TicketingSystem, TicketStatus

logger = logging.getLogger(__name__)


class ZendeskIntegration(TicketingSystem):
    """
    Zendesk ticketing system integration.

    Usage:
        zendesk = ZendeskIntegration(
            subdomain="your-company",
            email="agent@company.com",
            token="your-api-token"
        )

        # Create churn ticket
        customer_data = {...}
        ticket = await zendesk.create_churn_ticket(customer_data)
    """

    def __init__(self, subdomain: str, email: str, token: str):
        """
        Initialize Zendesk integration.

        Args:
            subdomain: Zendesk subdomain (e.g., "yourcompany")
            email: Agent email for authentication
            token: Zendesk API token
        """
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        self.auth = (f"{email}/token", token)
        self.client = httpx.AsyncClient(timeout=30.0)

    async def create_ticket(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a Zendesk ticket.

        Args:
            data: Ticket data with subject, description, priority, tags

        Returns:
            Created ticket with ID and URL
        """
        ticket_payload = {
            "ticket": {
                "subject": data.get("subject"),
                "comment": {"body": data.get("description")},
                "priority": data.get("priority", "medium"),
                "tags": data.get("tags", []),
                "custom_fields": self._format_custom_fields(data.get("custom_fields", {}))
            }
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/tickets",
                json=ticket_payload,
                auth=self.auth
            )
            response.raise_for_status()
            result = response.json()

            ticket = result.get("ticket", {})
            return {
                "id": str(ticket.get("id")),
                "url": ticket.get("url"),
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "created_at": ticket.get("created_at")
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to create Zendesk ticket: {e}")
            raise

    async def update_ticket(
        self,
        ticket_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a Zendesk ticket.

        Args:
            ticket_id: Ticket ID
            data: Fields to update (status, priority, comment, etc.)

        Returns:
            Updated ticket details
        """
        update_payload = {"ticket": {}}

        if "status" in data:
            update_payload["ticket"]["status"] = data["status"]
        if "priority" in data:
            update_payload["ticket"]["priority"] = data["priority"]
        if "comment" in data:
            update_payload["ticket"]["comment"] = {"body": data["comment"]}
        if "tags" in data:
            update_payload["ticket"]["tags"] = data["tags"]

        try:
            response = await self.client.put(
                f"{self.base_url}/tickets/{ticket_id}",
                json=update_payload,
                auth=self.auth
            )
            response.raise_for_status()
            result = response.json()

            ticket = result.get("ticket", {})
            return {
                "id": str(ticket.get("id")),
                "status": ticket.get("status"),
                "updated_at": ticket.get("updated_at")
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to update Zendesk ticket: {e}")
            raise

    async def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """Get Zendesk ticket details"""
        try:
            response = await self.client.get(
                f"{self.base_url}/tickets/{ticket_id}",
                auth=self.auth
            )
            response.raise_for_status()
            result = response.json()

            ticket = result.get("ticket", {})
            return {
                "id": str(ticket.get("id")),
                "subject": ticket.get("subject"),
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "tags": ticket.get("tags", []),
                "created_at": ticket.get("created_at"),
                "updated_at": ticket.get("updated_at")
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to get Zendesk ticket: {e}")
            raise

    async def close_ticket(
        self,
        ticket_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Close a Zendesk ticket.

        Args:
            ticket_id: Ticket ID
            reason: Optional closing comment

        Returns:
            Updated ticket details
        """
        update_data = {"status": "solved"}

        if reason:
            update_data["comment"] = f"Closing ticket: {reason}"

        return await self.update_ticket(ticket_id, update_data)

    async def add_comment(
        self,
        ticket_id: str,
        comment: str,
        internal: bool = False
    ) -> Dict[str, Any]:
        """
        Add a comment to a ticket.

        Args:
            ticket_id: Ticket ID
            comment: Comment text
            internal: Whether comment is internal note

        Returns:
            Comment details
        """
        comment_payload = {
            "ticket": {
                "comment": {
                    "body": comment,
                    "public": not internal
                }
            }
        }

        try:
            response = await self.client.put(
                f"{self.base_url}/tickets/{ticket_id}",
                json=comment_payload,
                auth=self.auth
            )
            response.raise_for_status()
            return {"success": True}

        except httpx.HTTPError as e:
            logger.error(f"Failed to add comment: {e}")
            raise

    async def create_churn_ticket(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a churn risk ticket from customer data.

        Args:
            customer_data: Customer churn analysis data

        Returns:
            Created ticket details
        """
        ticket_data = self.create_churn_ticket_data(customer_data)
        return await self.create_ticket(ticket_data)

    def _format_custom_fields(self, fields: Dict[str, Any]) -> list:
        """Format custom fields for Zendesk API"""
        # Zendesk custom fields require field IDs
        # This is a placeholder - actual IDs would come from Zendesk config
        formatted = []
        for key, value in fields.items():
            if key == "ltv" and isinstance(value, (int, float)):
                formatted.append({"id": 360000000001, "value": float(value)})
            elif key == "churn_risk" and isinstance(value, (int, float)):
                formatted.append({"id": 360000000002, "value": float(value)})
        return formatted

    async def list_tickets(
        self,
        status: Optional[str] = None,
        tags: Optional[list] = None,
        priority: Optional[str] = None,
        limit: int = 25
    ) -> list[Dict[str, Any]]:
        """
        List tickets with optional filters.

        Args:
            status: Filter by status (new, open, pending, hold, solved, closed)
            tags: Filter by tags (e.g., ["churn-risk", "retention"])
            priority: Filter by priority (urgent, high, normal, low)
            limit: Maximum number of tickets to return

        Returns:
            List of ticket summaries
        """
        # Build search query
        query_parts = []
        if status:
            query_parts.append(f"status:{status}")
        if tags:
            for tag in tags:
                query_parts.append(f"tags:{tag}")
        if priority:
            query_parts.append(f"priority:{priority}")

        query = " ".join(query_parts) if query_parts else "type:ticket"

        try:
            response = await self.client.get(
                f"{self.base_url}/search.json",
                params={"query": query, "per_page": limit},
                auth=self.auth
            )
            response.raise_for_status()
            result = response.json()

            tickets = []
            for ticket in result.get("results", []):
                tickets.append({
                    "id": str(ticket.get("id")),
                    "subject": ticket.get("subject"),
                    "status": ticket.get("status"),
                    "priority": ticket.get("priority"),
                    "tags": ticket.get("tags", []),
                    "created_at": ticket.get("created_at"),
                    "updated_at": ticket.get("updated_at"),
                    "description": ticket.get("description", "")
                })

            return tickets

        except httpx.HTTPError as e:
            logger.error(f"Failed to list Zendesk tickets: {e}")
            raise

    async def get_ticket_with_comments(self, ticket_id: str) -> Dict[str, Any]:
        """
        Get full ticket details including all comments.

        Args:
            ticket_id: Ticket ID

        Returns:
            Ticket with comments and metadata
        """
        try:
            # Get ticket details
            ticket_response = await self.client.get(
                f"{self.base_url}/tickets/{ticket_id}",
                auth=self.auth
            )
            ticket_response.raise_for_status()
            ticket_data = ticket_response.json().get("ticket", {})

            # Get comments
            comments_response = await self.client.get(
                f"{self.base_url}/tickets/{ticket_id}/comments",
                auth=self.auth
            )
            comments_response.raise_for_status()
            comments_data = comments_response.json().get("comments", [])

            return {
                "id": str(ticket_data.get("id")),
                "subject": ticket_data.get("subject"),
                "status": ticket_data.get("status"),
                "priority": ticket_data.get("priority"),
                "tags": ticket_data.get("tags", []),
                "created_at": ticket_data.get("created_at"),
                "updated_at": ticket_data.get("updated_at"),
                "description": ticket_data.get("description", ""),
                "comments": [
                    {
                        "id": str(comment.get("id")),
                        "body": comment.get("body"),
                        "author_id": str(comment.get("author_id")),
                        "created_at": comment.get("created_at"),
                        "public": comment.get("public", True)
                    }
                    for comment in comments_data
                ]
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to get ticket with comments: {e}")
            raise

    async def close(self):
        """Clean up resources"""
        await self.client.aclose()
