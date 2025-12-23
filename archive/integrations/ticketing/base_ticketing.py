"""
Base Ticketing System Interface

Abstract base class for all ticketing system integrations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum


class TicketPriority(Enum):
    """Ticket priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(Enum):
    """Ticket status"""
    OPEN = "open"
    PENDING = "pending"
    SOLVED = "solved"
    CLOSED = "closed"


class TicketingSystem(ABC):
    """
    Abstract base class for ticketing system integrations.

    Provides common interface for creating, updating, and managing
    support tickets across different platforms.
    """

    @abstractmethod
    async def create_ticket(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new ticket.

        Args:
            data: Ticket data including subject, description, priority, etc.

        Returns:
            Created ticket details with ID and URL
        """
        pass

    @abstractmethod
    async def update_ticket(
        self,
        ticket_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing ticket.

        Args:
            ticket_id: Ticket identifier
            data: Fields to update

        Returns:
            Updated ticket details
        """
        pass

    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """
        Get ticket details.

        Args:
            ticket_id: Ticket identifier

        Returns:
            Ticket details
        """
        pass

    @abstractmethod
    async def close_ticket(
        self,
        ticket_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Close a ticket.

        Args:
            ticket_id: Ticket identifier
            reason: Optional reason for closing

        Returns:
            Updated ticket details
        """
        pass

    @abstractmethod
    async def add_comment(
        self,
        ticket_id: str,
        comment: str,
        internal: bool = False
    ) -> Dict[str, Any]:
        """
        Add a comment to a ticket.

        Args:
            ticket_id: Ticket identifier
            comment: Comment text
            internal: Whether comment is internal only

        Returns:
            Comment details
        """
        pass

    def create_churn_ticket_data(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create ticket data from churn analysis.

        Args:
            customer_data: Customer churn risk data

        Returns:
            Formatted ticket data
        """
        churn_risk = customer_data.get("churn_risk", 0)
        ltv = customer_data.get("ltv", 0)
        customer_id = customer_data.get("customer_id", "Unknown")

        # Determine priority based on risk + value
        if churn_risk > 0.7 and ltv > 1000:
            priority = TicketPriority.URGENT
        elif churn_risk > 0.7 or ltv > 500:
            priority = TicketPriority.HIGH
        else:
            priority = TicketPriority.MEDIUM

        # Get retention strategy
        strategy = self._get_retention_strategy(customer_data)

        return {
            "subject": f"High Churn Risk: {customer_id}",
            "description": self._format_churn_ticket_body(customer_data, strategy),
            "priority": priority.value,
            "tags": [
                "churn-risk",
                "retention",
                customer_data.get("archetype", ""),
                f"risk-{int(churn_risk*100)}"
            ],
            "custom_fields": {
                "customer_id": customer_id,
                "ltv": ltv,
                "churn_risk": churn_risk
            }
        }

    def _format_churn_ticket_body(
        self,
        customer_data: Dict[str, Any],
        strategy: str
    ) -> str:
        """Format ticket description for churn risk"""
        return f"""
Customer at high risk of churning.

**Customer Details:**
- ID: {customer_data.get('customer_id', 'Unknown')}
- Lifetime Value: ${customer_data.get('ltv', 0):,.2f}
- Churn Risk: {customer_data.get('churn_risk', 0)*100:.0f}%
- Risk Level: {customer_data.get('risk_level', 'unknown').upper()}
- Archetype: {customer_data.get('archetype', 'Unknown')}

**Recommended Actions:**
{strategy}

**Next Steps:**
1. Review customer interaction history
2. Reach out within 24-48 hours
3. Implement recommended retention strategy
4. Follow up in 7 days

**Internal Note:** Automatically generated from behavioral churn prediction model.
        """.strip()

    def _get_retention_strategy(self, customer_data: Dict[str, Any]) -> str:
        """Get recommended retention strategy based on risk level"""
        churn_risk = customer_data.get("churn_risk", 0)
        ltv = customer_data.get("ltv", 0)

        if churn_risk > 0.8:
            return """
• **URGENT**: Immediate personal outreach from account manager
• Offer premium support consultation
• Provide exclusive discount (15-20%) on next purchase
• Identify and address specific pain points
• Consider upgrade to premium tier with benefits
            """.strip()
        elif churn_risk > 0.6:
            return """
• Send personalized re-engagement email
• Check for product/service issues
• Offer help session or training
• Provide 10-15% retention discount
• Schedule check-in call
            """.strip()
        elif churn_risk > 0.4:
            return """
• Monitor activity closely
• Send value reminder email
• Share success stories/case studies
• Offer optional check-in
• Track engagement over next 30 days
            """.strip()
        else:
            return """
• Continue standard engagement
• Include in regular nurture campaigns
• Monitor for changes in behavior
            """.strip()
