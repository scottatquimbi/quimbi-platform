"""
Ticketing System Integrations

Support for various ticketing systems (Zendesk, Gorgias, etc.).

Usage:
    # Method 1: Use factory (recommended)
    from integrations.ticketing import create_ticketing_system

    ticketing = create_ticketing_system()  # Auto-detects from env vars

    # Method 2: Direct instantiation
    from integrations.ticketing import ZendeskIntegration, GorgiasIntegration

    zendesk = ZendeskIntegration(
        subdomain="your-company",
        email="agent@company.com",
        token="your-api-token"
    )

    gorgias = GorgiasIntegration(
        domain="your-company",
        username="your-email@company.com",
        api_key="your-api-key"
    )

    ticket = await ticketing.create_churn_ticket(customer_data)
"""

from .base_ticketing import TicketingSystem, TicketStatus, TicketPriority
from .zendesk import ZendeskIntegration
from .gorgias import GorgiasIntegration
from .factory import (
    TicketingSystemFactory,
    TicketingProvider,
    create_ticketing_system
)

__all__ = [
    "TicketingSystem",
    "TicketStatus",
    "TicketPriority",
    "ZendeskIntegration",
    "GorgiasIntegration",
    "TicketingSystemFactory",
    "TicketingProvider",
    "create_ticketing_system"
]
