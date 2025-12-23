"""Unified Segmentation - Database Models"""

from .ticket import Ticket, TicketMessage, TicketNote, TicketAIRecommendation
from .tenant import Tenant

__all__ = [
    "Ticket",
    "TicketMessage",
    "TicketNote",
    "TicketAIRecommendation",
    "Tenant",
]
