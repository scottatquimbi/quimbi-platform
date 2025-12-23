"""
Gorgias Integration

Create and manage tickets in Gorgias from customer analytics.
Gorgias is a helpdesk platform designed for e-commerce companies.
"""
import logging
from typing import Dict, Any, Optional, List
import httpx

from .base_ticketing import TicketingSystem, TicketStatus

logger = logging.getLogger(__name__)


class GorgiasIntegration(TicketingSystem):
    """
    Gorgias ticketing system integration.

    Gorgias API Documentation: https://developers.gorgias.com/reference/introduction

    Usage:
        gorgias = GorgiasIntegration(
            domain="your-company",
            username="your-email@company.com",
            api_key="your-api-key"
        )

        # Create churn ticket
        customer_data = {...}
        ticket = await gorgias.create_churn_ticket(customer_data)
    """

    def __init__(self, domain: str, username: str, api_key: str):
        """
        Initialize Gorgias integration.

        Args:
            domain: Gorgias domain (e.g., "yourcompany")
            username: Account email for authentication
            api_key: Gorgias API key
        """
        self.base_url = f"https://{domain}.gorgias.com/api"
        self.auth = (username, api_key)  # HTTP Basic Auth
        self.client = httpx.AsyncClient(timeout=30.0)

    async def create_ticket(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a Gorgias ticket.

        Args:
            data: Ticket data with subject, description, priority, tags

        Returns:
            Created ticket with ID and URL
        """
        # Map priority to Gorgias values
        priority_map = {
            "urgent": "high",
            "high": "high",
            "medium": "medium",
            "normal": "medium",
            "low": "low"
        }

        priority = priority_map.get(data.get("priority", "medium"), "medium")

        # Build ticket payload
        ticket_payload = {
            "channel": "api",  # Source of the ticket
            "via": "api",
            "customer": {
                "email": data.get("customer_email", "noreply@customeranalytics.com")
            },
            "messages": [
                {
                    "channel": "api",
                    "via": "api",
                    "source": {
                        "type": "api",
                        "to": [{"address": data.get("customer_email", "support@company.com")}],
                        "from": {"address": "analytics@company.com"}
                    },
                    "body_text": data.get("description", ""),
                    "subject": data.get("subject", "Customer Analytics Alert")
                }
            ],
            "tags": [{"name": tag} for tag in data.get("tags", [])],
            "priority": priority
        }

        # Add custom fields if provided
        if "custom_fields" in data:
            # Gorgias stores metadata in the ticket's meta field
            ticket_payload["meta"] = data["custom_fields"]

        try:
            response = await self.client.post(
                f"{self.base_url}/tickets",
                json=ticket_payload,
                auth=self.auth
            )
            response.raise_for_status()
            result = response.json()

            return {
                "id": str(result.get("id")),
                "url": f"https://{self.base_url.split('//')[1].split('.')[0]}.gorgias.com/app/ticket/{result.get('id')}",
                "status": result.get("status"),
                "priority": result.get("priority"),
                "created_at": result.get("created_datetime")
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to create Gorgias ticket: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            raise

    async def update_ticket(
        self,
        ticket_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a Gorgias ticket.

        Args:
            ticket_id: Ticket ID
            data: Fields to update (status, priority, tags, etc.)

        Returns:
            Updated ticket details
        """
        update_payload = {}

        # Map status to Gorgias values
        if "status" in data:
            status_map = {
                "solved": "closed",
                "closed": "closed",
                "open": "opened",
                "pending": "opened",
                "hold": "opened"
            }
            update_payload["status"] = status_map.get(data["status"], "opened")

        # Map priority
        if "priority" in data:
            priority_map = {
                "urgent": "high",
                "high": "high",
                "medium": "medium",
                "normal": "medium",
                "low": "low"
            }
            update_payload["priority"] = priority_map.get(data["priority"], "medium")

        # Update tags
        if "tags" in data:
            update_payload["tags"] = [{"name": tag} for tag in data["tags"]]

        try:
            response = await self.client.put(
                f"{self.base_url}/tickets/{ticket_id}",
                json=update_payload,
                auth=self.auth
            )
            response.raise_for_status()
            result = response.json()

            # If there's a comment to add, create a message
            if "comment" in data:
                await self.add_comment(ticket_id, data["comment"], internal=True)

            return {
                "id": str(result.get("id")),
                "status": result.get("status"),
                "updated_at": result.get("updated_datetime")
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to update Gorgias ticket: {e}")
            raise

    async def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """
        Get Gorgias ticket details.

        Args:
            ticket_id: Ticket ID

        Returns:
            Ticket details
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/tickets/{ticket_id}",
                auth=self.auth
            )
            response.raise_for_status()
            ticket = response.json()

            # Extract tags
            tags = [tag.get("name") for tag in ticket.get("tags", [])]

            # Get initial message subject and body
            messages = ticket.get("messages", [])
            subject = messages[0].get("subject", "") if messages else ""
            description = messages[0].get("body_text", "") if messages else ""

            return {
                "id": str(ticket.get("id")),
                "subject": subject,
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "tags": tags,
                "created_at": ticket.get("created_datetime"),
                "updated_at": ticket.get("updated_datetime"),
                "description": description
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to get Gorgias ticket: {e}")
            raise

    async def close_ticket(
        self,
        ticket_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Close a Gorgias ticket.

        Args:
            ticket_id: Ticket ID
            reason: Optional closing comment

        Returns:
            Updated ticket details
        """
        update_data = {"status": "closed"}

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
        Add a comment (message) to a ticket.

        Args:
            ticket_id: Ticket ID
            comment: Comment text
            internal: Whether comment is internal note

        Returns:
            Message details
        """
        message_payload = {
            "channel": "api",
            "via": "api",
            "source": {
                "type": "api",
                "to": [],
                "from": {"address": "analytics@company.com"}
            },
            "body_text": comment,
            "is_note": internal  # Gorgias uses is_note for internal comments
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/tickets/{ticket_id}/messages",
                json=message_payload,
                auth=self.auth
            )
            response.raise_for_status()
            result = response.json()

            return {
                "id": str(result.get("id")),
                "success": True
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to add comment to Gorgias ticket: {e}")
            raise

    async def list_tickets(
        self,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority: Optional[str] = None,
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """
        List tickets with optional filters.

        Args:
            status: Filter by status (new, open, pending, closed)
            tags: Filter by tags
            priority: Filter by priority (high, medium, low)
            limit: Maximum number of tickets to return

        Returns:
            List of ticket summaries
        """
        # Build query parameters
        params = {
            "limit": limit,
            "order_by": "updated_datetime:desc"
        }

        # Map status to Gorgias values
        if status:
            status_map = {
                "new": "opened",
                "open": "opened",
                "pending": "opened",
                "hold": "opened",
                "solved": "closed",
                "closed": "closed"
            }
            params["status"] = status_map.get(status, "opened")

        # Gorgias doesn't support tag filtering in list endpoint
        # We'll fetch and filter client-side
        try:
            response = await self.client.get(
                f"{self.base_url}/tickets",
                params=params,
                auth=self.auth
            )
            response.raise_for_status()
            result = response.json()

            tickets = []
            for ticket in result.get("data", []):
                # Extract tags
                ticket_tags = [tag.get("name") for tag in ticket.get("tags", [])]

                # Filter by tags if specified
                if tags and not any(tag in ticket_tags for tag in tags):
                    continue

                # Filter by priority if specified
                if priority:
                    priority_map = {
                        "urgent": "high",
                        "high": "high",
                        "medium": "medium",
                        "normal": "medium",
                        "low": "low"
                    }
                    mapped_priority = priority_map.get(priority, priority)
                    if ticket.get("priority") != mapped_priority:
                        continue

                # Extract subject from first message
                messages = ticket.get("messages", [])
                subject = messages[0].get("subject", "No subject") if messages else "No subject"
                description = messages[0].get("body_text", "") if messages else ""

                tickets.append({
                    "id": str(ticket.get("id")),
                    "subject": subject,
                    "status": ticket.get("status"),
                    "priority": ticket.get("priority"),
                    "tags": ticket_tags,
                    "created_at": ticket.get("created_datetime"),
                    "updated_at": ticket.get("updated_datetime"),
                    "description": description
                })

            return tickets[:limit]  # Ensure we don't exceed limit after filtering

        except httpx.HTTPError as e:
            logger.error(f"Failed to list Gorgias tickets: {e}")
            raise

    async def get_ticket_with_comments(self, ticket_id: str) -> Dict[str, Any]:
        """
        Get full ticket details including all messages.

        Args:
            ticket_id: Ticket ID

        Returns:
            Ticket with messages and metadata
        """
        try:
            # Get ticket with all messages
            response = await self.client.get(
                f"{self.base_url}/tickets/{ticket_id}",
                auth=self.auth
            )
            response.raise_for_status()
            ticket = response.json()

            # Extract tags
            tags = [tag.get("name") for tag in ticket.get("tags", [])]

            # Extract messages
            messages = ticket.get("messages", [])
            subject = messages[0].get("subject", "") if messages else ""
            description = messages[0].get("body_text", "") if messages else ""

            # Format comments (skip first message which is the description)
            comments = []
            for msg in messages[1:]:  # Skip first message
                comments.append({
                    "id": str(msg.get("id")),
                    "body": msg.get("body_text", ""),
                    "author_id": str(msg.get("sender", {}).get("id", "")),
                    "created_at": msg.get("created_datetime"),
                    "public": not msg.get("is_note", False)  # is_note = internal
                })

            return {
                "id": str(ticket.get("id")),
                "subject": subject,
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "tags": tags,
                "created_at": ticket.get("created_datetime"),
                "updated_at": ticket.get("updated_datetime"),
                "description": description,
                "comments": comments
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to get Gorgias ticket with comments: {e}")
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

        # Add customer email if available
        if "customer_id" in customer_data:
            # In production, you'd look up the customer's email
            # For now, we'll use a placeholder
            ticket_data["customer_email"] = f"{customer_data['customer_id']}@customer.com"

        return await self.create_ticket(ticket_data)

    async def close(self):
        """Clean up resources"""
        await self.client.aclose()
