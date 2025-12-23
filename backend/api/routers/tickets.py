"""
Tickets Router

Provides comprehensive ticketing system endpoints for:
- Listing tickets with filtering and pagination
- Getting ticket details with full conversation history
- Creating and updating tickets
- Sending messages and adding notes
- Retrieving AI recommendations and draft responses
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload

from backend.core.database import get_db_session
from backend.models import Ticket, TicketMessage, TicketNote, TicketAIRecommendation
from backend.api.dependencies import require_api_key
from backend.api.routers.swagger_examples import (
    TICKET_CREATE_EXAMPLE,
    MESSAGE_CREATE_EXAMPLE,
    NOTE_CREATE_EXAMPLE,
    TICKET_UPDATE_EXAMPLE,
    TICKET_LIST_RESPONSE_EXAMPLE,
    TICKET_LIST_SMART_ORDER_RESPONSE_EXAMPLE,
    SCORE_BREAKDOWN_RESPONSE_EXAMPLE,
    TICKET_DETAIL_RESPONSE_EXAMPLE,
    ERROR_NOT_FOUND_EXAMPLE,
    ERROR_VALIDATION_EXAMPLE
)

# Import smart scoring service
from backend.services.scoring_service import scoring_service

router = APIRouter(prefix="/api/tickets", tags=["tickets"], dependencies=[Depends(require_api_key)])


# ==================== Request/Response Models ====================

class MessageCreate(BaseModel):
    """Request model for creating a new ticket message."""
    content: str = Field(..., min_length=1, description="Message content")
    from_agent: bool = Field(..., description="Whether message is from agent or customer")
    author_name: str = Field(..., description="Name of message author")
    author_email: Optional[str] = Field(None, description="Email of message author")
    author_id: Optional[str] = Field(None, description="ID of message author (agent_id or customer_id)")
    send_to_customer: bool = Field(default=True, description="Whether to actually send message to customer")
    close_ticket: bool = Field(default=False, description="Whether to close ticket after sending")

    model_config = {"json_schema_extra": {"example": MESSAGE_CREATE_EXAMPLE}}


class NoteCreate(BaseModel):
    """Request model for creating a new ticket note."""
    content: str = Field(..., min_length=1, description="Note content")
    author_name: str = Field(..., description="Name of note author")
    author_id: str = Field(..., description="ID of note author (agent_id)")

    model_config = {"json_schema_extra": {"example": NOTE_CREATE_EXAMPLE}}


class TicketUpdate(BaseModel):
    """Request model for updating ticket metadata."""
    status: Optional[str] = Field(None, description="New status: open, pending, closed")
    priority: Optional[str] = Field(None, description="New priority: urgent, high, normal, low")
    assigned_to: Optional[str] = Field(None, description="Assign to agent_id")
    tags: Optional[List[str]] = Field(None, description="Replace all tags")
    add_tags: Optional[List[str]] = Field(None, description="Add these tags")
    remove_tags: Optional[List[str]] = Field(None, description="Remove these tags")

    model_config = {"json_schema_extra": {"example": TICKET_UPDATE_EXAMPLE}}


class TicketCreate(BaseModel):
    """Request model for creating a new ticket."""
    customer_id: str = Field(..., description="Customer ID")
    channel: str = Field(..., description="Channel: email, sms, phone, chat, etc.")
    subject: Optional[str] = Field(None, description="Ticket subject")
    priority: str = Field(default="normal", description="Priority: urgent, high, normal, low")
    initial_message: str = Field(..., description="Initial message content")
    author_name: str = Field(..., description="Customer name")
    author_email: Optional[str] = Field(None, description="Customer email")

    model_config = {"json_schema_extra": {"example": TICKET_CREATE_EXAMPLE}}


# ==================== Helper Functions ====================

async def get_ticket_with_relations(ticket_id: str, session):
    """
    Get ticket with all related data (messages, notes, AI recommendations).

    Supports lookup by either UUID or ticket_number (e.g., "T-005").
    """
    import uuid as uuid_module

    # Try to determine if it's a UUID or ticket_number
    try:
        # Try parsing as UUID
        uuid_obj = uuid_module.UUID(ticket_id)
        # It's a valid UUID, query by ID
        query = (
            select(Ticket)
            .options(
                selectinload(Ticket.messages),
                selectinload(Ticket.notes),
                selectinload(Ticket.ai_recommendations)
            )
            .where(Ticket.id == uuid_obj)
        )
    except (ValueError, AttributeError):
        # Not a UUID, assume it's a ticket_number
        query = (
            select(Ticket)
            .options(
                selectinload(Ticket.messages),
                selectinload(Ticket.notes),
                selectinload(Ticket.ai_recommendations)
            )
            .where(Ticket.ticket_number == ticket_id)
        )

    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_customer_profile(customer_id: str, session):
    """
    Get customer profile from customer_profiles table.

    Returns customer archetype, business metrics, and churn risk.
    Returns None if customer not found or error occurs.
    """
    try:
        from sqlalchemy import text
        import logging

        logger = logging.getLogger(__name__)

        # Query customer_profiles table directly
        result = await session.execute(
            text("""
                SELECT
                    customer_id,
                    archetype_id,
                    archetype_level,
                    segment_memberships,
                    dominant_segments,
                    lifetime_value,
                    total_orders,
                    avg_order_value,
                    churn_risk_score,
                    days_since_last_purchase,
                    customer_tenure_days
                FROM platform.customer_profiles
                WHERE customer_id = :customer_id
                LIMIT 1
            """),
            {"customer_id": customer_id}
        )

        row = result.fetchone()

        if not row:
            logger.info(f"Customer profile not found for {customer_id}")
            return None

        # Return in format matching expected structure
        return {
            "customer_id": row[0],
            "archetype": {
                "id": row[1],
                "level": row[2]
            },
            "business_metrics": {
                "lifetime_value": row[5],
                "total_orders": row[6],
                "avg_order_value": row[7],
                "days_since_last_purchase": row[9],
                "customer_tenure_days": row[10]
            },
            "churn_risk": {
                "churn_risk_score": row[8]
            },
            "segment_memberships": row[3],  # JSONB
            "dominant_segments": row[4]  # JSONB
        }

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading customer profile for {customer_id}: {str(e)}", exc_info=True)
        return None


# ==================== Endpoints ====================

@router.post(
    "",
    status_code=201,
    responses={
        201: {
            "description": "Ticket created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "ticket": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "ticket_number": "T-001",
                            "customer_id": "7827249201407",
                            "status": "open",
                            "priority": "urgent"
                        },
                        "messages": [
                            {
                                "id": "msg_001",
                                "content": "I ordered thread last week and it hasn't arrived",
                                "from_agent": False
                            }
                        ]
                    }
                }
            }
        },
        400: {
            "description": "Validation error",
            "content": {"application/json": {"example": ERROR_VALIDATION_EXAMPLE}}
        }
    }
)
async def create_ticket(ticket_data: TicketCreate):
    """
    Create a new ticket with initial message.

    Returns the created ticket with full details including:
    - Ticket metadata (ID, number, status, priority)
    - Initial message from customer
    - Empty notes array
    """
    async with get_db_session() as session:
        # Generate ticket number
        result = await session.execute(select(func.generate_ticket_number()))
        ticket_number = result.scalar()

        # Create ticket
        ticket = Ticket(
            ticket_number=ticket_number,
            customer_id=ticket_data.customer_id,
            channel=ticket_data.channel,
            subject=ticket_data.subject,
            priority=ticket_data.priority,
            status="open",
            tags=[],
            custom_fields={}
        )
        session.add(ticket)
        await session.flush()  # Get ticket.id

        # Create initial message
        message = TicketMessage(
            ticket_id=ticket.id,
            from_agent=False,
            content=ticket_data.initial_message,
            author_name=ticket_data.author_name,
            author_email=ticket_data.author_email,
            author_id=ticket_data.customer_id
        )
        session.add(message)

        await session.commit()
        await session.refresh(ticket)

        # Get ticket with relations
        ticket_with_relations = await get_ticket_with_relations(str(ticket.id), session)

        return {
            "ticket": ticket_with_relations.to_dict(),
            "messages": [m.to_dict() for m in ticket_with_relations.messages],
            "notes": []
        }


@router.get(
    "",
    responses={
        200: {
            "description": "List of tickets with pagination",
            "content": {
                "application/json": {
                    "examples": {
                        "regular": {
                            "summary": "Regular sorting",
                            "description": "Standard ticket list sorted by field",
                            "value": TICKET_LIST_RESPONSE_EXAMPLE
                        },
                        "smart_order": {
                            "summary": "Smart ordering with topic alerts",
                            "description": "AI-powered intelligent ordering based on customer value, churn risk, urgency, and topic alerts",
                            "value": TICKET_LIST_SMART_ORDER_RESPONSE_EXAMPLE
                        }
                    }
                }
            }
        }
    }
)
async def list_tickets(
    status: Optional[str] = Query(None, description="Filter by status", example="open"),
    priority: Optional[str] = Query(None, description="Filter by priority", example="urgent"),
    channel: Optional[str] = Query(None, description="Filter by channel", example="email"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned agent", example="agent_123"),
    customer_id: Optional[str] = Query(None, description="Filter by customer", example="7827249201407"),
    page: int = Query(1, ge=1, description="Page number", example=1),
    limit: int = Query(50, ge=1, le=100, description="Items per page", example=20),
    sort: str = Query("created_at", description="Sort field (ignored if smart_order=true)", example="created_at"),
    order: str = Query("desc", description="Sort order: asc or desc (ignored if smart_order=true)", example="desc"),
    smart_order: bool = Query(
        False,
        description="🤖 AI-powered smart ordering - automatically prioritizes tickets based on customer value, churn risk, urgency, age, sentiment, and topic alerts",
        example=True
    ),
    topic_alerts: Optional[str] = Query(
        None,
        description="🚨 Comma-separated keywords to boost (+5.0 score). Use during emerging issues (e.g., 'chargeback,fraud' during fraud wave)",
        example="cancel,urgent"
    )
):
    """
    List tickets with filtering, pagination, and sorting.

    ## Smart Ordering (NEW!)

    Enable AI-powered intelligent ordering with `smart_order=true`:
    - 🎯 **Churn Risk** (×3.0): Customers likely to leave get priority
    - 💰 **Customer Value** (×2.0): High LTV customers prioritized
    - ⚡ **Urgency** (×1.5): Ticket priority level
    - ⏱️ **Age**: Older tickets don't get buried
    - 🎓 **Difficulty**: Easy wins bubble up
    - 😤 **Sentiment**: Frustrated customers prioritized
    - 🚨 **Topic Alerts** (+5.0): Dynamic keyword boosting

    ### Example Use Cases:
    - **Holiday shipping crisis**: `?smart_order=true&topic_alerts=wrong address,delayed`
    - **Fraud wave**: `?smart_order=true&topic_alerts=chargeback,fraud`
    - **Product recall**: `?smart_order=true&topic_alerts=defective,broken`
    - **Normal operations**: `?smart_order=true&status=open`

    ## Regular Sorting

    Standard filters and sorting (default behavior):
    - `/api/tickets?status=open` - Only open tickets
    - `/api/tickets?priority=urgent&status=open` - Urgent open tickets
    - `/api/tickets?customer_id=7827249201407` - All tickets for customer
    - `/api/tickets?sort=updated_at&order=desc` - Sort by last updated

    ## Returns

    **Regular mode:**
    - `tickets`: List of ticket summaries
    - `pagination`: Pagination metadata
    - `filters_applied`: Active filters

    **Smart order mode (adds):**
    - `smart_order_enabled`: true
    - `topic_alerts_active`: ["cancel", "urgent"]
    - `matches`: Count of tickets matching alerts
    - Each ticket includes: `smart_score` and `matches_topic_alert`
    """
    async with get_db_session() as session:
        # Build query
        query = select(Ticket)

        # Apply filters
        filters = []
        if status:
            filters.append(Ticket.status == status)
        if priority:
            filters.append(Ticket.priority == priority)
        if channel:
            filters.append(Ticket.channel == channel)
        if assigned_to:
            filters.append(Ticket.assigned_to == assigned_to)
        if customer_id:
            filters.append(Ticket.customer_id == customer_id)

        if filters:
            query = query.where(and_(*filters))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar()

        # Apply sorting (skip if smart_order is enabled)
        if not smart_order:
            sort_column = getattr(Ticket, sort, Ticket.created_at)
            if order == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))

        # Execute query (without pagination if using smart_order)
        if smart_order:
            # Fetch all tickets for smart scoring, then paginate
            result = await session.execute(query)
            tickets = result.scalars().all()
        else:
            # Apply pagination for regular sorting
            query = query.offset((page - 1) * limit).limit(limit)
            result = await session.execute(query)
            tickets = result.scalars().all()

        # Parse topic alerts
        alert_list = None
        if topic_alerts:
            alert_list = [alert.strip() for alert in topic_alerts.split(",") if alert.strip()]

        # For each ticket, get message count and last message preview
        ticket_list = []
        for ticket in tickets:
            # Get message count
            msg_count_query = select(func.count()).where(TicketMessage.ticket_id == ticket.id)
            msg_count_result = await session.execute(msg_count_query)
            message_count = msg_count_result.scalar()

            # Get last message
            last_msg_query = (
                select(TicketMessage)
                .where(TicketMessage.ticket_id == ticket.id)
                .order_by(desc(TicketMessage.created_at))
                .limit(1)
            )
            last_msg_result = await session.execute(last_msg_query)
            last_message = last_msg_result.scalar_one_or_none()

            ticket_dict = ticket.to_dict()
            ticket_dict["message_count"] = message_count
            if last_message:
                ticket_dict["last_message_preview"] = last_message.content[:100] + "..." if len(last_message.content) > 100 else last_message.content
                ticket_dict["last_message_at"] = last_message.created_at.isoformat()
                ticket_dict["last_message_from_agent"] = last_message.from_agent
            else:
                ticket_dict["last_message_preview"] = None
                ticket_dict["last_message_at"] = None
                ticket_dict["last_message_from_agent"] = None

            ticket_list.append(ticket_dict)

        # Apply smart scoring if enabled
        if smart_order:
            # Calculate smart scores for each ticket
            for ticket_dict in ticket_list:
                # Get customer profile for this ticket
                customer_profile = await get_customer_profile(ticket_dict["customer_id"], session)

                if customer_profile:
                    # Build ticket dict for scoring service
                    ticket_for_scoring = {
                        "priority": ticket_dict.get("priority", "normal"),
                        "created_at": ticket_dict.get("created_at"),
                        "messages": [{"content": ticket_dict.get("last_message_preview", "")}] if ticket_dict.get("last_message_preview") else [],
                        "customer_sentiment": ticket_dict.get("customer_sentiment")
                    }

                    # Calculate smart score
                    ticket_dict["smart_score"] = scoring_service.calculate_ticket_score(
                        ticket=ticket_for_scoring,
                        customer=customer_profile,
                        topic_alerts=alert_list
                    )

                    # Mark if matches topic alert
                    if alert_list:
                        ticket_dict["matches_topic_alert"] = (
                            scoring_service._get_topic_alert_component(ticket_for_scoring, alert_list) > 0
                        )
                else:
                    # No customer profile, use default low score
                    ticket_dict["smart_score"] = 0.0
                    ticket_dict["matches_topic_alert"] = False

            # Sort by smart score (highest first)
            ticket_list.sort(key=lambda t: t.get("smart_score", 0), reverse=True)

            # Apply pagination after sorting
            start = (page - 1) * limit
            end = start + limit
            ticket_list = ticket_list[start:end]

            # Count topic alert matches
            matches_count = sum(1 for t in ticket_list if t.get("matches_topic_alert"))
        else:
            matches_count = 0

        # Build response
        response = {
            "tickets": ticket_list,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
                "has_next": page * limit < total,
                "has_prev": page > 1
            },
            "filters_applied": {
                "status": status,
                "priority": priority,
                "channel": channel,
                "assigned_to": assigned_to,
                "customer_id": customer_id
            }
        }

        # Add smart order info if enabled
        if smart_order:
            response["smart_order_enabled"] = True
            response["topic_alerts_active"] = alert_list if alert_list else []
            response["matches"] = matches_count

        return response


@router.get(
    "/{ticket_id}",
    responses={
        200: {
            "description": "Full ticket details",
            "content": {"application/json": {"example": TICKET_DETAIL_RESPONSE_EXAMPLE}}
        },
        404: {
            "description": "Ticket not found",
            "content": {"application/json": {"example": ERROR_NOT_FOUND_EXAMPLE}}
        }
    }
)
async def get_ticket(ticket_id: str):
    """
    Get full ticket details including:
    - Ticket metadata (status, priority, tags, timestamps)
    - All messages chronologically (customer + agent)
    - Customer profile with archetype and business metrics
    - Churn risk assessment
    - AI recommendations (if generated)
    - AI draft response (if generated)

    This is the primary endpoint for the ticket detail page.

    Returns comprehensive context for agents to handle the ticket effectively.
    """
    async with get_db_session() as session:
        # Get ticket with all relations
        ticket = await get_ticket_with_relations(ticket_id, session)

        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        # Get customer profile
        customer_profile = await get_customer_profile(ticket.customer_id, session)

        # Get AI recommendations (non-expired)
        ai_rec = None
        if ticket.ai_recommendations:
            # Get most recent non-expired recommendation
            for rec in sorted(ticket.ai_recommendations, key=lambda x: x.generated_at, reverse=True):
                if not rec.is_expired:
                    ai_rec = rec.to_dict()
                    break

        # Build response
        return {
            "id": str(ticket.id),
            "ticket_number": ticket.ticket_number,
            "customer_id": ticket.customer_id,
            "channel": ticket.channel,
            "status": ticket.status,
            "priority": ticket.priority,
            "subject": ticket.subject,
            "assigned_to": ticket.assigned_to,
            "tags": ticket.tags or [],
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
            "messages": [
                m.to_dict() for m in sorted(ticket.messages, key=lambda x: x.created_at)
            ],
            "customer_profile": customer_profile,
            "ai_recommendation": ai_rec
        }


@router.post("/{ticket_id}/messages")
async def send_message(ticket_id: str, message_data: MessageCreate):
    """
    Send a new message on a ticket.

    Supports lookup by UUID or ticket_number (e.g., "T-005").

    If send_to_customer is True, this will trigger actual message delivery
    via the appropriate channel (email, SMS, etc.).

    If close_ticket is True, ticket status will be set to "closed".
    """
    async with get_db_session() as session:
        # Get ticket (supports UUID or ticket_number)
        ticket = await get_ticket_with_relations(ticket_id, session)
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        # Create message
        message = TicketMessage(
            ticket_id=ticket.id,
            from_agent=message_data.from_agent,
            content=message_data.content,
            author_name=message_data.author_name,
            author_email=message_data.author_email,
            author_id=message_data.author_id
        )
        session.add(message)

        # Update ticket status if closing
        if message_data.close_ticket:
            ticket.status = "closed"
            ticket.closed_at = datetime.utcnow()

        # TODO: If send_to_customer is True, trigger actual message delivery
        # This would integrate with email/SMS services

        await session.commit()
        await session.refresh(message)
        await session.refresh(ticket)

        return {
            "message": message.to_dict(),
            "ticket_updated": {
                "id": str(ticket.id),
                "status": ticket.status,
                "updated_at": ticket.updated_at.isoformat()
            }
        }


@router.patch("/{ticket_id}")
async def update_ticket(ticket_id: str, update_data: TicketUpdate):
    """
    Update ticket metadata (status, priority, assignment, tags).

    Tag operations:
    - tags: Replace all tags
    - add_tags: Add tags to existing
    - remove_tags: Remove tags from existing
    """
    async with get_db_session() as session:
        # Get ticket
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        # Update fields
        if update_data.status is not None:
            ticket.status = update_data.status
            if update_data.status == "closed" and not ticket.closed_at:
                ticket.closed_at = datetime.utcnow()

        if update_data.priority is not None:
            ticket.priority = update_data.priority

        if update_data.assigned_to is not None:
            ticket.assigned_to = update_data.assigned_to

        # Handle tags
        current_tags = set(ticket.tags or [])

        if update_data.tags is not None:
            # Replace all tags
            current_tags = set(update_data.tags)

        if update_data.add_tags:
            current_tags.update(update_data.add_tags)

        if update_data.remove_tags:
            current_tags.difference_update(update_data.remove_tags)

        ticket.tags = list(current_tags)

        await session.commit()
        await session.refresh(ticket)

        return {
            "ticket": ticket.to_dict()
        }


@router.post("/{ticket_id}/notes")
async def add_note(ticket_id: str, note_data: NoteCreate):
    """
    Add an internal note to a ticket.

    Notes are only visible to agents, not customers.
    """
    async with get_db_session() as session:
        # Verify ticket exists
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        # Create note
        note = TicketNote(
            ticket_id=ticket.id,
            content=note_data.content,
            author_name=note_data.author_name,
            author_id=note_data.author_id
        )
        session.add(note)

        await session.commit()
        await session.refresh(note)

        return {
            "note": note.to_dict()
        }


@router.post("/{ticket_id}/reset-conversation")
async def reset_conversation(ticket_id: str):
    """
    Reset conversation by deleting all messages except the first one.

    Useful for demo purposes to restart a conversation from the initial message.
    """
    async with get_db_session() as session:
        # Verify ticket exists
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        # Get all messages ordered by created_at
        result = await session.execute(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at)
        )
        messages = result.scalars().all()

        if len(messages) <= 1:
            # Nothing to reset
            return {
                "status": "already_reset",
                "messages_deleted": 0
            }

        # Delete all messages except the first one
        messages_to_delete = messages[1:]
        deleted_count = 0
        for message in messages_to_delete:
            await session.delete(message)
            deleted_count += 1

        await session.commit()

        return {
            "status": "reset",
            "messages_deleted": deleted_count,
            "ticket_id": ticket_id
        }


@router.get(
    "/{ticket_id}/score-breakdown",
    responses={
        200: {
            "description": "Smart score breakdown",
            "content": {"application/json": {"example": SCORE_BREAKDOWN_RESPONSE_EXAMPLE}}
        },
        404: {
            "description": "Ticket or customer not found",
            "content": {"application/json": {"example": ERROR_NOT_FOUND_EXAMPLE}}
        }
    }
)
async def get_score_breakdown(ticket_id: str):
    """
    Get detailed smart score breakdown for a ticket.

    ## What You Get

    This endpoint shows you **exactly why** a ticket has its smart score, breaking down
    all 7 scoring components and showing the customer metrics that drive the score.

    ### Score Components:
    1. **Churn Risk** (weight: 3.0x) - How likely customer is to leave (0-1 scale)
    2. **Customer Value** (weight: 2.0x) - Customer LTV normalized ($/1000)
    3. **Urgency** (weight: 1.5x) - Ticket priority multiplier (urgent=4, high=3, normal=1, low=0.5)
    4. **Age** - Inverse of hours waiting (older = higher score)
    5. **Difficulty** - Keyword-based difficulty estimate (+1.0 easy, -1.5 hard)
    6. **Sentiment** - Frustrated customers get +2.0 boost
    7. **Topic Alert** - Keyword matches get +5.0 boost

    ### Use Cases:
    - 🔍 **Debug**: "Why is this ticket at the top of my inbox?"
    - 📊 **Understand**: "What makes this customer high priority?"
    - ⚙️ **Tune**: "Should I adjust algorithm weights?"
    - 📈 **Explain**: "Show stakeholders how prioritization works"

    ### Example:
    ```
    GET /api/tickets/T-001/score-breakdown

    Returns:
    {
      "total_score": 22.75,
      "components": {
        "churn_risk": 2.55,      // 85% churn risk × 3.0 weight
        "customer_value": 7.00,  // $3500 LTV ÷ 1000 × 2.0 weight
        "urgency": 6.00,         // urgent priority × 1.5 weight
        "age": 0.20,             // 5 hours old
        "sentiment": 2.00,       // Very frustrated
        "topic_alert": 5.00      // Matches "cancel" alert
      }
    }
    ```

    **Answer:** VIP customer ($3500 LTV) with 85% churn risk, very frustrated, wants to cancel.
    This ticket deserves immediate attention!
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Score breakdown requested for ticket_id: {ticket_id}")

        async with get_db_session() as session:
            # Get ticket
            logger.info(f"Fetching ticket with relations for {ticket_id}")
            ticket = await get_ticket_with_relations(ticket_id, session)
            if not ticket:
                logger.warning(f"Ticket not found: {ticket_id}")
                raise HTTPException(status_code=404, detail="Ticket not found")

            logger.info(f"Ticket found: {ticket.ticket_number}, customer_id: {ticket.customer_id}")

            # Get customer profile
            logger.info(f"Fetching customer profile for customer_id: {ticket.customer_id}")
            customer_profile = await get_customer_profile(ticket.customer_id, session)
            if not customer_profile:
                logger.warning(f"Customer profile not found for customer_id: {ticket.customer_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Customer profile not found - cannot calculate score"
                )

            logger.info(f"Customer profile loaded: LTV={customer_profile.get('business_metrics', {}).get('lifetime_value')}, churn={customer_profile.get('churn_risk', {}).get('churn_risk_score')}")

            # Get messages for the ticket
            logger.info(f"Fetching messages for ticket.id: {ticket.id}")
            messages_query = (
                select(TicketMessage)
                .where(TicketMessage.ticket_id == ticket.id)
                .order_by(desc(TicketMessage.created_at))
            )
            messages_result = await session.execute(messages_query)
            messages = messages_result.scalars().all()
            logger.info(f"Found {len(messages)} messages")

            # Build ticket dict for scoring
            logger.info("Building ticket dict for scoring")
            ticket_for_scoring = {
                "priority": ticket.priority,
                "created_at": ticket.created_at.isoformat(),
                "messages": [{"content": msg.content} for msg in messages],
                "customer_sentiment": None  # Ticket model doesn't have customer_sentiment field yet
            }
            logger.info(f"Ticket dict: priority={ticket.priority}, created_at={ticket.created_at.isoformat()}")

            # Get scoring breakdown
            logger.info("Calling scoring_service.get_scoring_breakdown")
            breakdown = scoring_service.get_scoring_breakdown(
                ticket=ticket_for_scoring,
                customer=customer_profile,
                topic_alerts=None
            )
            logger.info(f"Breakdown calculated: total_score={breakdown.get('total_score')}")

            # Add ticket info for context
            logger.info("Adding ticket info to breakdown")
            breakdown["ticket_info"] = {
                "ticket_id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "customer_id": ticket.customer_id,
                "status": ticket.status,
                "channel": ticket.channel,
                "created_at": ticket.created_at.isoformat()
            }

            logger.info(f"Successfully completed score breakdown for {ticket_id}")
            return breakdown

    except HTTPException:
        # Re-raise HTTP exceptions (404s)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_score_breakdown for ticket_id={ticket_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating score breakdown: {str(e)}"
        )


@router.get("/{ticket_id}/notes")
async def get_notes(ticket_id: str):
    """
    Get all internal notes for a ticket.

    Notes are returned in chronological order.
    """
    async with get_db_session() as session:
        # Verify ticket exists
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        # Get all notes
        query = (
            select(TicketNote)
            .where(TicketNote.ticket_id == ticket_id)
            .order_by(asc(TicketNote.created_at))
        )
        result = await session.execute(query)
        notes = result.scalars().all()

        return {
            "notes": [note.to_dict() for note in notes]
        }
