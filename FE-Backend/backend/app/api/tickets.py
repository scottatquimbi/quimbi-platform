"""
Tickets API Endpoint

Implements Smart Inbox Ordering with Topic Alerts support.

Philosophy: No sorting UI - tickets arrive in intelligent order based on:
- Customer churn risk × 3.0
- Customer lifetime value × 2.0
- Ticket urgency × 1.5
- Ticket age (older = higher)
- Difficulty (easy wins bubble up)
- Sentiment (frustrated customers prioritized)
- Topic alerts (agent-specified boost +5.0)
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.services.scoring_service import ScoringService


router = APIRouter()
scoring_service = ScoringService()


@router.get("/tickets")
async def list_tickets(
    status: str = Query("open", description="Filter by ticket status"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    limit: int = Query(50, ge=1, le=100, description="Max tickets to return"),
    page: int = Query(1, ge=1, description="Page number"),
    topic_alerts: Optional[str] = Query(
        None,
        description="Comma-separated topics to boost (e.g., 'chargeback,wrong address')"
    )
):
    """
    Get tickets list in smart order.

    NO SORT PARAMETER - Tickets always arrive in intelligent order.

    Topic Alerts:
    - Agents can specify keywords to watch for
    - Matching tickets get +5.0 score boost
    - Temporary intent-setting during emerging issues
    - Example: "chargeback,fraud,wrong address"

    Returns:
        {
            "tickets": [...],  # Ordered by smart_score DESC
            "pagination": {...},
            "topic_alerts_active": ["chargeback", "fraud"],  # If provided
            "matches": 3  # Count of tickets matching alerts
        }
    """
    # TODO: Replace with actual database queries
    # This is a prototype showing the algorithm

    # Parse topic alerts
    alert_list = None
    if topic_alerts:
        alert_list = [
            alert.strip() for alert in topic_alerts.split(",")
            if alert.strip()
        ]

    # TODO: Fetch tickets from database
    # For now, return mock data structure showing the concept
    tickets = _get_mock_tickets()

    # TODO: Fetch customer data for each ticket
    # For now, using mock customer data
    customers = _get_mock_customers()

    # Calculate smart scores for each ticket
    for ticket in tickets:
        customer = customers.get(ticket["customer_id"], {})

        # Calculate score using scoring service
        ticket["smart_score"] = scoring_service.calculate_ticket_score(
            ticket=ticket,
            customer=customer,
            topic_alerts=alert_list
        )

        # Mark if matches topic alert
        if alert_list:
            ticket["matches_topic_alert"] = (
                scoring_service._get_topic_alert_component(ticket, alert_list) > 0
            )
        else:
            ticket["matches_topic_alert"] = False

    # Sort by smart score (highest first)
    tickets_sorted = sorted(
        tickets,
        key=lambda t: t["smart_score"],
        reverse=True
    )

    # Apply filters
    if channel:
        tickets_sorted = [t for t in tickets_sorted if t.get("channel") == channel]

    if status:
        tickets_sorted = [t for t in tickets_sorted if t.get("status") == status]

    # Pagination
    start = (page - 1) * limit
    end = start + limit
    tickets_page = tickets_sorted[start:end]

    # Count topic alert matches
    matches_count = sum(1 for t in tickets_sorted if t.get("matches_topic_alert"))

    return {
        "tickets": tickets_page,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": len(tickets_sorted),
            "has_next": end < len(tickets_sorted),
            "has_prev": page > 1
        },
        "topic_alerts_active": alert_list if alert_list else [],
        "matches": matches_count if alert_list else 0
    }


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    """
    Get single ticket with full details.

    Includes:
    - Complete message history
    - Customer profile with behavioral segmentation
    - AI-generated draft response (from cache or generated)
    - Proactive context (orders, tracking, past tickets)
    - Next best actions recommendations
    """
    # TODO: Implement full ticket detail endpoint
    raise HTTPException(
        status_code=501,
        detail="Full ticket detail endpoint - Phase 2"
    )


@router.post("/tickets/{ticket_id}/messages")
async def send_message(ticket_id: str):
    """
    Send response to ticket.

    Automatically:
    - Updates ticket status
    - Recalculates smart score
    - Clears cached AI draft
    - Triggers follow-up scheduling
    """
    # TODO: Implement message sending
    raise HTTPException(
        status_code=501,
        detail="Message sending endpoint - Phase 2"
    )


@router.get("/tickets/{ticket_id}/score-breakdown")
async def get_score_breakdown(ticket_id: str):
    """
    Debug endpoint: See why ticket has its score.

    Returns detailed breakdown:
    - Total score
    - Component scores (churn, value, urgency, age, etc.)
    - Customer metrics
    - Ticket properties
    - Algorithm weights

    Useful for:
    - Understanding inbox order
    - Tuning algorithm
    - Explaining to users
    """
    # TODO: Fetch real ticket and customer data
    ticket = _get_mock_tickets()[0]  # Mock
    customer = _get_mock_customers()[ticket["customer_id"]]  # Mock

    breakdown = scoring_service.get_scoring_breakdown(
        ticket=ticket,
        customer=customer,
        topic_alerts=None
    )

    return breakdown


# Mock data helpers (remove in production)
def _get_mock_tickets():
    """
    Mock ticket data for prototype.
    TODO: Replace with database queries.
    """
    from datetime import datetime, timedelta

    return [
        {
            "id": "1",
            "customer_id": "c1",
            "subject": "Order not delivered",
            "status": "open",
            "priority": "high",
            "channel": "email",
            "created_at": datetime.utcnow() - timedelta(hours=2),
            "messages": [
                {
                    "content": "My order hasn't arrived and tracking shows no updates",
                    "from_agent": False
                }
            ],
            "customer_sentiment": 0.2  # Frustrated
        },
        {
            "id": "2",
            "customer_id": "c2",
            "subject": "Need tracking number",
            "status": "open",
            "priority": "normal",
            "channel": "chat",
            "created_at": datetime.utcnow() - timedelta(minutes=30),
            "messages": [
                {
                    "content": "Can you send me the tracking number for order #12345?",
                    "from_agent": False
                }
            ],
            "customer_sentiment": 0.7  # Neutral
        },
        {
            "id": "3",
            "customer_id": "c3",
            "subject": "Product damaged",
            "status": "open",
            "priority": "urgent",
            "channel": "email",
            "created_at": datetime.utcnow() - timedelta(hours=5),
            "messages": [
                {
                    "content": "Product arrived damaged. Need refund immediately.",
                    "from_agent": False
                }
            ],
            "customer_sentiment": 0.1  # Very frustrated
        }
    ]


def _get_mock_customers():
    """
    Mock customer data for prototype.
    TODO: Replace with database queries.
    """
    return {
        "c1": {
            "customer_id": "c1",
            "business_metrics": {
                "lifetime_value": 2500.0,
                "total_orders": 12
            },
            "churn_risk": {
                "churn_risk_score": 0.75  # High risk
            }
        },
        "c2": {
            "customer_id": "c2",
            "business_metrics": {
                "lifetime_value": 450.0,
                "total_orders": 3
            },
            "churn_risk": {
                "churn_risk_score": 0.25  # Low risk
            }
        },
        "c3": {
            "customer_id": "c3",
            "business_metrics": {
                "lifetime_value": 5200.0,
                "total_orders": 28
            },
            "churn_risk": {
                "churn_risk_score": 0.85  # Very high risk
            }
        }
    }
