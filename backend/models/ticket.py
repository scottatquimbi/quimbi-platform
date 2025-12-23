"""
Ticket System Database Models

Provides SQLAlchemy models for the ticketing system including:
- Tickets: Main support tickets
- TicketMessages: Customer and agent messages
- TicketNotes: Internal agent notes
- TicketAIRecommendations: Cached AI recommendations
"""

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime, timedelta

from backend.core.database import Base


class Ticket(Base):
    """
    Main ticket model representing a customer support interaction.

    A ticket represents a single support conversation that may span multiple messages
    across one or more channels (email, SMS, chat, phone, etc.).
    """
    __tablename__ = "tickets"
    __table_args__ = {"schema": "support_app"}

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_number = Column(String(20), unique=True, nullable=False, index=True)

    # Customer relationship
    customer_id = Column(String(255), nullable=False, index=True)

    # Channel and routing
    channel = Column(String(50), nullable=False)  # email, sms, phone, chat, whatsapp, etc.
    assigned_to = Column(String(255), index=True)  # agent_id or null if unassigned

    # Status and priority
    status = Column(String(50), nullable=False, default="open", index=True)  # open, pending, closed
    priority = Column(String(50), nullable=False, default="normal")  # urgent, high, normal, low

    # Content
    subject = Column(String(500))

    # Metadata
    tags = Column(JSONB, default=list)  # ["vip", "shipping_issue", "resolved"]
    custom_fields = Column(JSONB, default=dict)  # Flexible storage for custom fields

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    closed_at = Column(DateTime)

    # Relationships
    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")
    notes = relationship("TicketNote", back_populates="ticket", cascade="all, delete-orphan")
    ai_recommendations = relationship("TicketAIRecommendation", back_populates="ticket", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Ticket {self.ticket_number} - {self.status} - {self.customer_id}>"

    def to_dict(self):
        """Convert ticket to dictionary for API responses."""
        return {
            "id": str(self.id),
            "ticket_number": self.ticket_number,
            "customer_id": self.customer_id,
            "channel": self.channel,
            "status": self.status,
            "priority": self.priority,
            "subject": self.subject,
            "assigned_to": self.assigned_to,
            "tags": self.tags or [],
            "metadata": self.custom_fields or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }


class TicketMessage(Base):
    """
    Individual message within a ticket conversation.

    Messages can be from customers or agents. All messages are stored chronologically
    and displayed as a conversation thread.
    """
    __tablename__ = "ticket_messages"
    __table_args__ = {"schema": "support_app"}

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey('support_app.tickets.id', ondelete='CASCADE'), nullable=False, index=True)

    # Message metadata
    from_agent = Column(Boolean, nullable=False, default=False)
    content = Column(Text, nullable=False)

    # Author information
    author_name = Column(String(255))
    author_email = Column(String(255))
    author_id = Column(String(255))  # agent_id or customer_id

    # Additional data
    custom_fields = Column(JSONB, default=dict)  # attachments, formatting, etc.

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    # Relationships
    ticket = relationship("Ticket", back_populates="messages")

    def __repr__(self):
        author_type = "Agent" if self.from_agent else "Customer"
        return f"<TicketMessage {author_type} - {self.author_name}>"

    def to_dict(self):
        """Convert message to dictionary for API responses."""
        return {
            "id": str(self.id),
            "ticket_id": str(self.ticket_id),
            "from_agent": self.from_agent,
            "content": self.content,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "author_id": self.author_id,
            "metadata": self.custom_fields or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TicketNote(Base):
    """
    Internal notes for tickets (not visible to customers).

    Notes allow agents to share context, document actions taken, or leave
    instructions for other team members without customer visibility.
    """
    __tablename__ = "ticket_notes"
    __table_args__ = {"schema": "support_app"}

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey('support_app.tickets.id', ondelete='CASCADE'), nullable=False, index=True)

    # Note content
    content = Column(Text, nullable=False)

    # Author information
    author_name = Column(String(255), nullable=False)
    author_id = Column(String(255), nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    ticket = relationship("Ticket", back_populates="notes")

    def __repr__(self):
        return f"<TicketNote by {self.author_name}>"

    def to_dict(self):
        """Convert note to dictionary for API responses."""
        return {
            "id": str(self.id),
            "ticket_id": str(self.ticket_id),
            "content": self.content,
            "author_name": self.author_name,
            "author_id": self.author_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TicketAIRecommendation(Base):
    """
    AI-generated recommendations for tickets (cached).

    Stores AI-generated next best actions, talking points, warnings, and draft
    responses. Cached to avoid regenerating on every page load.
    """
    __tablename__ = "ticket_ai_recommendations"
    __table_args__ = {"schema": "support_app"}

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey('support_app.tickets.id', ondelete='CASCADE'), nullable=False, index=True)

    # Recommendation content
    priority = Column(String(50))  # urgent, high, normal, low
    actions = Column(JSONB, nullable=False)  # List of action objects
    talking_points = Column(JSONB)  # List of talking points
    warnings = Column(JSONB)  # List of warnings
    estimated_impact = Column(JSONB)  # retention_probability, revenue_at_risk

    # Draft response
    draft_response = Column(Text)
    draft_tone = Column(String(50))  # empathetic, friendly, professional, apologetic
    draft_personalization = Column(JSONB)  # List of personalization applied

    # Cache metadata
    generated_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=False, index=True)  # Auto-expire after 1 hour
    message_count = Column(Integer)  # Track message count to invalidate on new messages

    # Relationships
    ticket = relationship("Ticket", back_populates="ai_recommendations")

    def __repr__(self):
        return f"<TicketAIRecommendation for ticket {self.ticket_id}>"

    def to_dict(self):
        """Convert AI recommendation to dictionary for API responses."""
        return {
            "id": str(self.id),
            "ticket_id": str(self.ticket_id),
            "priority": self.priority,
            "actions": self.actions or [],
            "talking_points": self.talking_points or [],
            "warnings": self.warnings or [],
            "estimated_impact": self.estimated_impact or {},
            "draft_response": self.draft_response,
            "draft_tone": self.draft_tone,
            "draft_personalization": self.draft_personalization or [],
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @property
    def is_expired(self):
        """Check if recommendation has expired."""
        return datetime.utcnow() > self.expires_at

    @classmethod
    def create_with_expiry(cls, ticket_id, **kwargs):
        """Create recommendation with automatic 1-hour expiry."""
        expires_at = datetime.utcnow() + timedelta(hours=1)
        return cls(ticket_id=ticket_id, expires_at=expires_at, **kwargs)
