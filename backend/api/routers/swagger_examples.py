"""
Swagger UI Examples and Documentation Enhancements

This module provides comprehensive examples for all API endpoints to make
the Swagger UI more useful for frontend developers.
"""

from typing import Dict, Any

# ==================== System Configuration Examples ====================

SYSTEM_CONFIG_EXAMPLE = {
    "version": "1.0.0",
    "axis_count": 13,
    "axes": [
        {
            "name": "purchase_frequency",
            "display_name": "Purchase Frequency",
            "description": "How often the customer makes purchases",
            "category": "purchase",
            "segments": [
                {
                    "name": "weekly_shopper",
                    "display_name": "Weekly Shopper",
                    "description": "Makes 13+ purchases per year",
                    "order": 1
                },
                {
                    "name": "monthly_shopper",
                    "display_name": "Monthly Shopper",
                    "description": "Makes 6-12 purchases per year",
                    "order": 2
                }
            ]
        }
    ]
}

# ==================== Ticket Examples ====================

TICKET_CREATE_EXAMPLE = {
    "customer_id": "7827249201407",
    "channel": "email",
    "subject": "Order not received",
    "priority": "urgent",
    "initial_message": "I ordered thread last week (order #1234) and it still hasn't arrived. I need it for a project this weekend!",
    "author_name": "Sarah Johnson",
    "author_email": "sarah@example.com"
}

TICKET_LIST_RESPONSE_EXAMPLE = {
    "tickets": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "ticket_number": "T-001",
            "customer_id": "7827249201407",
            "channel": "email",
            "status": "open",
            "priority": "urgent",
            "subject": "Order not received",
            "assigned_to": None,
            "tags": ["vip", "shipping_issue"],
            "created_at": "2025-11-13T17:00:00Z",
            "updated_at": "2025-11-13T17:30:00Z",
            "closed_at": None,
            "message_count": 3,
            "last_message_preview": "I ordered thread last week and it still hasn't arrived...",
            "last_message_at": "2025-11-13T17:30:00Z",
            "last_message_from_agent": False
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "ticket_number": "T-002",
            "customer_id": "7827249201408",
            "channel": "sms",
            "status": "pending",
            "priority": "normal",
            "subject": "Question about product",
            "assigned_to": "agent_123",
            "tags": ["product_inquiry"],
            "created_at": "2025-11-13T16:00:00Z",
            "updated_at": "2025-11-13T16:15:00Z",
            "closed_at": None,
            "message_count": 2,
            "last_message_preview": "Thanks for the info! One more question...",
            "last_message_at": "2025-11-13T16:15:00Z",
            "last_message_from_agent": True
        }
    ],
    "pagination": {
        "page": 1,
        "limit": 50,
        "total": 234,
        "total_pages": 5,
        "has_next": True,
        "has_prev": False
    },
    "filters_applied": {
        "status": "open",
        "priority": None,
        "channel": None,
        "assigned_to": None,
        "customer_id": None
    }
}

# Smart Ordering Examples
TICKET_LIST_SMART_ORDER_RESPONSE_EXAMPLE = {
    "tickets": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "ticket_number": "T-001",
            "customer_id": "7827249201407",
            "channel": "email",
            "status": "open",
            "priority": "urgent",
            "subject": "Need to cancel order immediately",
            "assigned_to": None,
            "tags": ["vip", "urgent"],
            "created_at": "2025-11-13T17:00:00Z",
            "updated_at": "2025-11-13T17:30:00Z",
            "closed_at": None,
            "message_count": 2,
            "last_message_preview": "I need to cancel my order #5432 immediately! This is urgent.",
            "last_message_at": "2025-11-13T17:30:00Z",
            "last_message_from_agent": False,
            "smart_score": 22.75,
            "matches_topic_alert": True
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "ticket_number": "T-003",
            "customer_id": "7827249201409",
            "channel": "email",
            "status": "open",
            "priority": "high",
            "subject": "Package damaged",
            "assigned_to": None,
            "tags": ["shipping_issue"],
            "created_at": "2025-11-12T10:00:00Z",
            "updated_at": "2025-11-12T10:15:00Z",
            "closed_at": None,
            "message_count": 1,
            "last_message_preview": "Product arrived damaged. Need replacement.",
            "last_message_at": "2025-11-12T10:15:00Z",
            "last_message_from_agent": False,
            "smart_score": 17.69,
            "matches_topic_alert": False
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440002",
            "ticket_number": "T-002",
            "customer_id": "7827249201408",
            "channel": "chat",
            "status": "open",
            "priority": "normal",
            "subject": "Tracking number question",
            "assigned_to": None,
            "tags": ["tracking"],
            "created_at": "2025-11-13T16:00:00Z",
            "updated_at": "2025-11-13T16:15:00Z",
            "closed_at": None,
            "message_count": 1,
            "last_message_preview": "Can you send me the tracking number?",
            "last_message_at": "2025-11-13T16:15:00Z",
            "last_message_from_agent": False,
            "smart_score": 4.85,
            "matches_topic_alert": False
        }
    ],
    "pagination": {
        "page": 1,
        "limit": 50,
        "total": 156,
        "total_pages": 4,
        "has_next": True,
        "has_prev": False
    },
    "filters_applied": {
        "status": "open",
        "priority": None,
        "channel": None,
        "assigned_to": None,
        "customer_id": None
    },
    "smart_order_enabled": True,
    "topic_alerts_active": ["cancel", "urgent"],
    "matches": 1
}

SCORE_BREAKDOWN_RESPONSE_EXAMPLE = {
    "total_score": 22.75,
    "components": {
        "churn_risk": 2.55,
        "customer_value": 7.00,
        "urgency": 6.00,
        "age": 0.20,
        "difficulty": 0.00,
        "sentiment": 2.00,
        "topic_alert": 5.00
    },
    "customer": {
        "ltv": 3500.00,
        "churn_risk": 0.85
    },
    "ticket": {
        "priority": "urgent",
        "age_hours": 5.0
    },
    "weights": {
        "churn_weight": 3.0,
        "value_weight": 2.0,
        "urgency_weight": 1.5,
        "topic_alert_boost": 5.0
    },
    "ticket_info": {
        "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
        "ticket_number": "T-001",
        "customer_id": "7827249201407",
        "status": "open",
        "channel": "email",
        "created_at": "2025-11-13T17:00:00Z"
    }
}

TICKET_DETAIL_RESPONSE_EXAMPLE = {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "ticket_number": "T-001",
    "customer_id": "7827249201407",
    "channel": "email",
    "status": "open",
    "priority": "urgent",
    "subject": "Order not received",
    "assigned_to": None,
    "tags": ["vip", "shipping_issue"],
    "created_at": "2025-11-13T17:00:00Z",
    "updated_at": "2025-11-13T17:30:00Z",
    "closed_at": None,
    "messages": [
        {
            "id": "msg_001",
            "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
            "from_agent": False,
            "content": "I ordered thread last week (order #1234) and it still hasn't arrived. I need it for a project this weekend!",
            "created_at": "2025-11-13T17:00:00Z",
            "author_name": "Sarah Johnson",
            "author_email": "sarah@example.com",
            "author_id": "7827249201407"
        },
        {
            "id": "msg_002",
            "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
            "from_agent": True,
            "content": "Hi Sarah, I'm so sorry to hear about this. Let me check on your order right away.",
            "created_at": "2025-11-13T17:15:00Z",
            "author_name": "John Smith",
            "author_email": "john@company.com",
            "author_id": "agent_123"
        },
        {
            "id": "msg_003",
            "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
            "from_agent": False,
            "content": "Thank you! I really need it by Saturday.",
            "created_at": "2025-11-13T17:30:00Z",
            "author_name": "Sarah Johnson",
            "author_email": "sarah@example.com",
            "author_id": "7827249201407"
        }
    ],
    "customer_profile": {
        "customer_id": "7827249201407",
        "archetype": {
            "archetype_id": "weekly_highvalue_multicategory",
            "dominant_segments": {
                "purchase_frequency": "weekly_shopper",
                "purchase_value": "high_value",
                "category_exploration": "multi_category",
                "price_sensitivity": "value_seeker",
                "purchase_cadence": "routine_buyer",
                "customer_maturity": "established",
                "repurchase_behavior": "highly_loyal",
                "return_behavior": "never_returns",
                "communication_preference": "email_preferred",
                "problem_complexity_profile": "simple_questions",
                "loyalty_trajectory": "growing_engagement",
                "product_knowledge": "expert",
                "value_sophistication": "value_aware"
            },
            "member_count": 847,
            "population_percentage": 0.0847
        },
        "business_metrics": {
            "lifetime_value": 3420.50,
            "total_orders": 28,
            "avg_order_value": 122.16,
            "days_since_last_purchase": 18,
            "customer_tenure_days": 567
        },
        "churn_risk": {
            "risk_level": "critical",
            "churn_risk_score": 0.73,
            "factors": {
                "recency_days": 18,
                "order_frequency": "declining",
                "value_tier": "vip",
                "engagement_trend": "decreasing"
            },
            "recommendation": "Immediate retention offer recommended. VIP customer showing decreased engagement."
        }
    },
    "ai_recommendation": {
        "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
        "priority": "urgent",
        "actions": [
            {
                "action": "Offer expedited replacement shipment at no charge",
                "priority": 1,
                "completed": False,
                "reasoning": "VIP customer with high churn risk needs immediate resolution"
            },
            {
                "action": "Issue $25 store credit for inconvenience",
                "priority": 2,
                "completed": False,
                "reasoning": "Goodwill gesture to maintain relationship"
            }
        ],
        "talking_points": [
            "Acknowledge frustration and apologize for delivery issue",
            "Emphasize her VIP status and long-term relationship",
            "Proactively offer solution before she has to ask"
        ],
        "warnings": [
            "VIP customer with high churn risk (73%)",
            "Recent purchase frequency decline detected",
            "This is second shipping issue in 6 months"
        ],
        "estimated_impact": {
            "retention_probability": 0.45,
            "revenue_at_risk": 3420.50
        },
        "generated_at": "2025-11-13T18:00:00Z"
    }
}

MESSAGE_CREATE_EXAMPLE = {
    "content": "Hi Sarah, I've processed your replacement order and it's being shipped via express delivery. You should receive it by Friday. I've also added $25 store credit to your account for the inconvenience. We really appreciate your business and want to make this right!",
    "from_agent": True,
    "author_name": "John Smith",
    "author_email": "john@company.com",
    "author_id": "agent_123",
    "send_to_customer": True,
    "close_ticket": False
}

TICKET_UPDATE_EXAMPLE = {
    "status": "pending",
    "priority": "high",
    "assigned_to": "agent_456",
    "add_tags": ["resolved", "follow_up"],
    "remove_tags": ["shipping_issue"]
}

NOTE_CREATE_EXAMPLE = {
    "content": "Customer mentioned this is second shipping issue in 6 months. Flagged with warehouse manager to investigate recurring issues with this carrier.",
    "author_name": "John Smith",
    "author_id": "agent_123"
}

# ==================== AI Examples ====================

AI_RECOMMENDATION_RESPONSE_EXAMPLE = {
    "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
    "priority": "urgent",
    "estimated_impact": {
        "retention_probability": 0.45,
        "revenue_at_risk": 3420.50
    },
    "actions": [
        {
            "action": "Offer expedited replacement shipment at no charge",
            "priority": 1,
            "completed": False,
            "reasoning": "VIP customer with high churn risk needs immediate resolution"
        },
        {
            "action": "Issue $25 store credit for inconvenience",
            "priority": 2,
            "completed": False,
            "reasoning": "Goodwill gesture to maintain relationship"
        },
        {
            "action": "Follow up within 24 hours to confirm resolution",
            "priority": 3,
            "completed": False,
            "reasoning": "Ensure customer satisfaction and prevent churn"
        }
    ],
    "talking_points": [
        "Acknowledge frustration and apologize for delivery issue",
        "Emphasize her VIP status and long-term relationship ($3,420 lifetime value)",
        "Proactively offer solution before she has to ask",
        "Mention checking with carrier about delivery confirmation",
        "Reference her upcoming project deadline (Saturday)"
    ],
    "warnings": [
        "VIP customer with high churn risk (73%)",
        "Recent purchase frequency decline detected",
        "This is second shipping issue in 6 months",
        "Customer has project deadline in 3 days"
    ],
    "generated_at": "2025-11-13T18:00:00Z"
}

AI_DRAFT_RESPONSE_EXAMPLE = {
    "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
    "draft": "Hi Sarah,\n\nI'm so sorry to hear about the delivery issue with your thread order #1234. I completely understand your frustration, especially with your project deadline this weekend.\n\nI've checked with our carrier and I see the tracking shows delivered, but since you didn't receive it, this is clearly an error on their end. Here's what I'd like to do for you:\n\n1. Send you a replacement shipment via expedited delivery (arriving by Friday) at no charge\n2. Add $25 store credit to your account for the inconvenience\n3. File a claim with the carrier to investigate the missing package\n\nAs one of our VIP customers, we really value your business and want to make this right. Can you confirm your shipping address is still correct, and I'll get that replacement order processed immediately?\n\nBest regards,\nSupport Team",
    "tone": "empathetic",
    "personalization_applied": [
        "VIP status mentioned",
        "Project deadline acknowledged",
        "Specific order number referenced",
        "Proactive solution offered",
        "Expedited shipping to meet deadline"
    ],
    "generated_at": "2025-11-13T18:00:00Z"
}

AI_REGENERATE_REQUEST_EXAMPLE = {
    "tone": "friendly",
    "length": "short",
    "include_offer": True,
    "template": None
}

AI_REGENERATE_RESPONSE_EXAMPLE = {
    "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
    "draft": "Hey Sarah!\n\nOh no! I'm really sorry your thread order hasn't arrived yet. That's so frustrating, especially with your weekend project!\n\nI'm sending you a replacement via express shipping (arriving Friday) at no charge, plus adding $25 credit to your account. Sound good?\n\nLet me know if you need anything else!",
    "tone": "friendly",
    "length": "short",
    "generated_at": "2025-11-13T18:05:00Z"
}

# ==================== Error Examples ====================

ERROR_NOT_FOUND_EXAMPLE = {
    "error": {
        "code": "TICKET_NOT_FOUND",
        "message": "Ticket with ID 550e8400-e29b-41d4-a716-446655440999 not found",
        "details": {
            "ticket_id": "550e8400-e29b-41d4-a716-446655440999"
        }
    }
}

ERROR_VALIDATION_EXAMPLE = {
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid request data",
        "details": {
            "field": "priority",
            "error": "Value must be one of: urgent, high, normal, low"
        }
    }
}

ERROR_UNAUTHORIZED_EXAMPLE = {
    "error": {
        "code": "UNAUTHORIZED",
        "message": "Invalid or missing API key",
        "details": {}
    }
}

# ==================== Export all examples ====================

EXAMPLES = {
    "system_config": SYSTEM_CONFIG_EXAMPLE,
    "ticket_create": TICKET_CREATE_EXAMPLE,
    "ticket_list_response": TICKET_LIST_RESPONSE_EXAMPLE,
    "ticket_detail_response": TICKET_DETAIL_RESPONSE_EXAMPLE,
    "message_create": MESSAGE_CREATE_EXAMPLE,
    "ticket_update": TICKET_UPDATE_EXAMPLE,
    "note_create": NOTE_CREATE_EXAMPLE,
    "ai_recommendation_response": AI_RECOMMENDATION_RESPONSE_EXAMPLE,
    "ai_draft_response": AI_DRAFT_RESPONSE_EXAMPLE,
    "ai_regenerate_request": AI_REGENERATE_REQUEST_EXAMPLE,
    "ai_regenerate_response": AI_REGENERATE_RESPONSE_EXAMPLE,
    "error_not_found": ERROR_NOT_FOUND_EXAMPLE,
    "error_validation": ERROR_VALIDATION_EXAMPLE,
    "error_unauthorized": ERROR_UNAUTHORIZED_EXAMPLE,
}
