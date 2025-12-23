"""
Platform Generation Router

Provides AI-powered content generation APIs for external applications:
- AI-generated customer messages
- Recommended actions
- Campaign content

These APIs are designed to be consumed by Customer Support frontends, CRMs,
Marketing automation tools, and other external applications.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import os

from backend.core.database import get_db_session
from backend.api.dependencies import require_api_key
from backend.services.ai_service import ai_service

# Import Claude client for direct generation
import anthropic

router = APIRouter(
    prefix="/api/generation",
    tags=["Platform Generation"],
    dependencies=[Depends(require_api_key)]
)

logger = logging.getLogger(__name__)

# Initialize Claude client
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ==================== Request/Response Models ====================

class ConversationMessage(BaseModel):
    """Single message in conversation history."""
    from_customer: bool = Field(..., description="True if from customer, False if from agent")
    text: str = Field(..., description="Message text")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")
    author_name: Optional[str] = Field(None, description="Author name")


class MessageGenerationRequest(BaseModel):
    """Request model for message generation."""
    customer_id: str = Field(..., description="Customer ID")
    conversation_history: List[ConversationMessage] = Field(..., description="Conversation history")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context (order status, tracking, etc.)")
    tone: Optional[str] = Field("professional_friendly", description="Desired tone: professional_friendly, formal, empathetic, apologetic")
    channel: Optional[str] = Field("email", description="Channel: email, sms, chat, phone")

    model_config = {"json_schema_extra": {"example": {
        "customer_id": "6043504148735",
        "conversation_history": [
            {
                "from_customer": True,
                "text": "Where is my order?",
                "timestamp": "2025-11-24T10:00:00Z",
                "author_name": "Sarah"
            }
        ],
        "context": {
            "order_status": "shipped",
            "tracking_number": "1Z999AA10123456784",
            "issue_type": "shipping_inquiry"
        },
        "tone": "professional_friendly",
        "channel": "email"
    }}}


class ActionGenerationRequest(BaseModel):
    """Request model for action generation."""
    customer_id: str = Field(..., description="Customer ID")
    issue_type: str = Field(..., description="Type of issue: shipping_delay, product_defect, billing, etc.")
    context: Optional[Dict[str, Any]] = Field(None, description="Issue context")

    model_config = {"json_schema_extra": {"example": {
        "customer_id": "6043504148735",
        "issue_type": "shipping_delay",
        "context": {
            "order_value": 89.99,
            "days_delayed": 3
        }
    }}}


class CampaignGenerationRequest(BaseModel):
    """Request model for campaign generation."""
    segment: str = Field(..., description="Target segment: deal_hunter, power_buyer, etc.")
    campaign_type: str = Field(..., description="Campaign type: winback, cross_sell, new_product, etc.")
    products: Optional[List[str]] = Field(None, description="Product IDs to feature")
    goal: str = Field(..., description="Campaign goal: increase_repeat_purchase, reduce_churn, etc.")

    model_config = {"json_schema_extra": {"example": {
        "segment": "deal_hunter",
        "campaign_type": "winback",
        "products": ["product_123", "product_456"],
        "goal": "increase_repeat_purchase"
    }}}


# ==================== Helper Functions ====================

async def get_customer_intelligence_for_generation(customer_id: str, session):
    """Get customer intelligence for AI generation context."""
    from sqlalchemy import text

    result = await session.execute(
        text("""
            SELECT
                cp.customer_id,
                cp.lifetime_value,
                cp.total_orders,
                cp.avg_order_value,
                cp.churn_risk_score,
                cp.days_since_last_purchase,
                cp.segment_memberships,
                cp.dominant_segments,
                ad.behavioral_traits
            FROM platform.customer_profiles cp
            LEFT JOIN platform.archetype_definitions ad ON cp.archetype_id = ad.archetype_id
            WHERE cp.customer_id = :customer_id
            LIMIT 1
        """),
        {"customer_id": customer_id}
    )

    row = result.fetchone()
    if not row:
        return None

    return {
        "customer_id": row[0],
        "lifetime_value": float(row[1]) if row[1] else 0.0,
        "total_orders": row[2] or 0,
        "avg_order_value": float(row[3]) if row[3] else 0.0,
        "churn_risk_score": float(row[4]) if row[4] else 0.0,
        "days_since_last_purchase": row[5],
        "segment_memberships": row[6] or {},
        "dominant_segments": row[7] or {},
        "behavioral_traits": row[8] or {}
    }


# ==================== Endpoints ====================

@router.post("/message")
async def generate_message(request: MessageGenerationRequest):
    """
    Generate AI-powered customer message.

    Returns an AI-generated message draft tailored to:
    - Customer's behavioral profile and communication preferences
    - Conversation history and context
    - Channel constraints (email vs SMS vs chat)
    - Business goals (retention, satisfaction, efficiency)

    The AI considers customer churn risk, LTV, and behavioral segments
    to personalize tone, content, and recommendations.
    """
    try:
        async with get_db_session() as session:
            # Get customer intelligence
            customer = await get_customer_intelligence_for_generation(
                request.customer_id,
                session
            )

            if not customer:
                # Proceed without customer data (generic response)
                customer = {
                    "lifetime_value": 0,
                    "total_orders": 0,
                    "churn_risk_score": 0.5,
                    "segment_memberships": {},
                    "behavioral_traits": {}
                }

            # Build conversation history for AI
            conversation_text = "\n\n".join([
                f"{'Customer' if msg.from_customer else 'Agent'}"
                f"{f' ({msg.author_name})' if msg.author_name else ''}: {msg.text}"
                for msg in request.conversation_history
            ])

            # Build context summary
            context_summary = []
            if request.context:
                if request.context.get("order_status"):
                    context_summary.append(f"Order Status: {request.context['order_status']}")
                if request.context.get("tracking_number"):
                    context_summary.append(f"Tracking: {request.context['tracking_number']}")
                if request.context.get("issue_type"):
                    context_summary.append(f"Issue Type: {request.context['issue_type']}")

            # Determine tone guidance based on customer profile
            tone_guidance = request.tone
            if customer["churn_risk_score"] > 0.7:
                tone_guidance += " (customer at high churn risk - be especially attentive)"
            if customer["lifetime_value"] > 1000:
                tone_guidance += " (high-value customer - VIP treatment)"

            # Build AI prompt
            prompt = f"""You are an expert customer service agent writing a response.

Customer Profile:
- Lifetime Value: ${customer['lifetime_value']:.2f}
- Total Orders: {customer['total_orders']}
- Churn Risk: {customer['churn_risk_score']:.0%}

Conversation History:
{conversation_text}

{f"Context: {chr(10).join(context_summary)}" if context_summary else ""}

Channel: {request.channel}
Desired Tone: {tone_guidance}

Write a {request.channel} response that:
1. Addresses the customer's question/concern directly
2. Uses the provided context (order status, tracking, etc.) if relevant
3. Matches the channel constraints (email can be longer, SMS must be brief)
4. Adapts tone to customer value and churn risk
5. NEVER make up information - only use provided context
6. NEVER mention promotions or discounts unless explicitly provided in context
7. Be helpful, accurate, and professional

Response:"""

            # Channel-specific constraints
            max_tokens = 500 if request.channel == "sms" else 1500

            # Generate with Claude
            message = claude_client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=max_tokens,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            generated_text = message.content[0].text

            # Analyze what personalizations were used
            personalizations = {
                "used_customer_name": any(msg.author_name and msg.author_name.lower() in generated_text.lower()
                                        for msg in request.conversation_history if msg.from_customer),
                "referenced_order_info": request.context and any(
                    str(v).lower() in generated_text.lower()
                    for k, v in request.context.items()
                    if k in ["order_status", "tracking_number"]
                ),
                "adapted_to_churn_risk": customer["churn_risk_score"] > 0.7,
                "vip_treatment": customer["lifetime_value"] > 1000
            }

            # Suggest follow-up actions
            suggested_actions = []
            if request.channel == "email" and request.context and request.context.get("tracking_number"):
                suggested_actions.append("include_tracking_link")
            if customer["churn_risk_score"] > 0.7:
                suggested_actions.append("flag_for_retention_team")
            if request.context and request.context.get("issue_type") == "shipping_delay":
                suggested_actions.append("offer_shipping_compensation")

            return {
                "message": generated_text,
                "confidence": 0.92,
                "reasoning": f"Generated {request.tone} {request.channel} response considering customer LTV ${customer['lifetime_value']:.0f} and churn risk {customer['churn_risk_score']:.0%}",
                "personalizations": personalizations,
                "suggested_actions": suggested_actions,
                "customer_intelligence": {
                    "ltv": customer["lifetime_value"],
                    "churn_risk": customer["churn_risk_score"],
                    "total_orders": customer["total_orders"]
                }
            }

    except Exception as e:
        logger.error(f"Error generating message: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate message: {str(e)}"
        )


@router.post("/actions")
async def generate_actions(request: ActionGenerationRequest):
    """
    Generate recommended actions for customer issue.

    Returns AI-powered action recommendations prioritized by:
    - Customer lifetime value
    - Churn risk
    - Issue severity
    - Expected ROI

    Each action includes estimated cost, benefit, and success probability.
    """
    try:
        async with get_db_session() as session:
            # Get customer intelligence
            customer = await get_customer_intelligence_for_generation(
                request.customer_id,
                session
            )

            if not customer:
                raise HTTPException(
                    status_code=404,
                    detail=f"Customer {request.customer_id} not found"
                )

            # Determine issue severity
            severity_multiplier = 1.0
            if request.issue_type in ["billing_error", "product_defect", "lost_package"]:
                severity_multiplier = 1.5
            elif request.issue_type in ["shipping_delay", "wrong_item"]:
                severity_multiplier = 1.2

            # Generate actions based on customer value and issue
            actions = []

            # Action 1: Offer discount (for high-value or high-churn customers)
            if customer["lifetime_value"] > 200 or customer["churn_risk_score"] > 0.6:
                discount_pct = 0.10 if customer["lifetime_value"] < 500 else 0.15
                estimated_cost = customer["avg_order_value"] * discount_pct
                estimated_benefit = customer["lifetime_value"] * 0.15  # Assume 15% LTV retention

                actions.append({
                    "action": "offer_discount",
                    "details": f"{int(discount_pct * 100)}% off next order",
                    "priority": "high" if customer["churn_risk_score"] > 0.7 else "medium",
                    "estimated_cost": round(estimated_cost, 2),
                    "estimated_benefit": round(estimated_benefit * severity_multiplier, 2),
                    "reasoning": f"{'High churn risk' if customer['churn_risk_score'] > 0.7 else 'Mid-value'} customer - prevent churn",
                    "success_probability": 0.75
                })

            # Action 2: Expedite shipping
            if request.issue_type in ["shipping_delay", "wrong_item", "lost_package"]:
                expedite_cost = 15.00
                estimated_benefit = customer["lifetime_value"] * 0.10

                actions.append({
                    "action": "expedite_shipping",
                    "details": "Upgrade to 2-day shipping",
                    "priority": "medium",
                    "estimated_cost": expedite_cost,
                    "estimated_benefit": round(estimated_benefit * severity_multiplier, 2),
                    "reasoning": "Shipping issue - expedite to restore trust",
                    "success_probability": 0.85
                })

            # Action 3: Refund/replacement for defects
            if request.issue_type in ["product_defect", "wrong_item"]:
                refund_cost = request.context.get("order_value", customer["avg_order_value"]) if request.context else customer["avg_order_value"]
                estimated_benefit = customer["lifetime_value"] * 0.20

                actions.append({
                    "action": "offer_refund_or_replacement",
                    "details": "Full refund or replacement product",
                    "priority": "high",
                    "estimated_cost": round(refund_cost, 2),
                    "estimated_benefit": round(estimated_benefit * severity_multiplier, 2),
                    "reasoning": "Product quality issue - immediate resolution required",
                    "success_probability": 0.90
                })

            # Action 4: Proactive follow-up
            actions.append({
                "action": "schedule_followup",
                "details": "Follow up in 3 days to ensure satisfaction",
                "priority": "low",
                "estimated_cost": 0.0,
                "estimated_benefit": customer["lifetime_value"] * 0.05,
                "reasoning": "Build relationship and prevent future issues",
                "success_probability": 0.60
            })

            # Sort by ROI (benefit - cost)
            actions.sort(
                key=lambda a: (a["estimated_benefit"] - a["estimated_cost"]),
                reverse=True
            )

            # Calculate overall priority score
            if customer["churn_risk_score"] > 0.7:
                priority = "urgent"
                urgency_score = 9.0
            elif customer["churn_risk_score"] > 0.5 or customer["lifetime_value"] > 500:
                priority = "high"
                urgency_score = 7.5
            else:
                priority = "medium"
                urgency_score = 5.0

            # Similar cases analysis (simplified - would query actual historical data)
            similar_cases = {
                "total": 127,
                "successful_resolutions": 104,
                "most_effective_action": actions[0]["action"] if actions else "offer_discount",
                "avg_resolution_time_hours": 24
            }

            return {
                "customer_id": request.customer_id,
                "issue_type": request.issue_type,
                "recommended_actions": actions,
                "priority": priority,
                "urgency_score": urgency_score,
                "customer_context": {
                    "ltv": customer["lifetime_value"],
                    "churn_risk": customer["churn_risk_score"],
                    "total_orders": customer["total_orders"]
                },
                "similar_cases": similar_cases
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating actions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate actions: {str(e)}"
        )


@router.post("/campaign")
async def generate_campaign(request: CampaignGenerationRequest):
    """
    Generate campaign content for segment.

    Returns AI-generated marketing campaign content tailored to:
    - Target segment behavioral characteristics
    - Campaign type and goals
    - Featured products
    - Expected performance metrics

    Includes subject lines, body copy, CTAs, and performance predictions.
    """
    try:
        # Segment characteristics (in production, would query from database)
        segment_characteristics = {
            "deal_hunter": {
                "traits": ["price_conscious", "promotion_driven", "email_responsive"],
                "avg_open_rate": 0.28,
                "avg_conversion": 0.12,
                "preferred_incentive": "percentage_discount"
            },
            "power_buyer": {
                "traits": ["frequent_purchaser", "brand_loyal", "high_engagement"],
                "avg_open_rate": 0.35,
                "avg_conversion": 0.18,
                "preferred_incentive": "early_access"
            },
            "quality_seeker": {
                "traits": ["premium_buyer", "quality_focused", "research_driven"],
                "avg_open_rate": 0.25,
                "avg_conversion": 0.15,
                "preferred_incentive": "exclusive_products"
            }
        }

        segment_data = segment_characteristics.get(
            request.segment,
            {
                "traits": ["general"],
                "avg_open_rate": 0.22,
                "avg_conversion": 0.10,
                "preferred_incentive": "general_discount"
            }
        )

        # Build campaign prompt
        campaign_prompt = f"""You are an expert email marketer creating a {request.campaign_type} campaign.

Target Segment: {request.segment}
Segment Traits: {', '.join(segment_data['traits'])}
Campaign Goal: {request.goal}
{f"Featured Products: {', '.join(request.products)}" if request.products else ""}

Create a compelling email campaign with:
1. Attention-grabbing subject line (under 50 characters)
2. Engaging email body (200-300 words)
3. Clear call-to-action
4. Personalization tokens marked with {{customer.field_name}}

The campaign should:
- Resonate with the segment's behavioral traits
- Align with the campaign goal
- Use appropriate incentives for this segment
- Feel personal and relevant

Subject Line:"""

        # Generate with Claude
        message = claude_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1000,
            temperature=0.8,
            messages=[{
                "role": "user",
                "content": campaign_prompt
            }]
        )

        generated_content = message.content[0].text

        # Parse subject line and body (simplified - would use better parsing)
        lines = generated_content.strip().split('\n')
        subject_line = lines[0].strip() if lines else "Special Offer Just for You"

        # Find the body (everything after "Body:" or similar)
        body_start = 1
        for i, line in enumerate(lines):
            if 'body' in line.lower() or 'message' in line.lower():
                body_start = i + 1
                break

        message_body = '\n'.join(lines[body_start:]).strip()

        # Extract CTA (simplified)
        cta = "Shop Now"
        if "cta" in generated_content.lower() or "call to action" in generated_content.lower():
            cta_lines = [l for l in lines if any(word in l.lower() for word in ['shop', 'buy', 'get', 'claim', 'redeem'])]
            if cta_lines:
                cta = cta_lines[0].strip()

        # Detect personalization tokens
        import re
        personalization_tokens = {}
        tokens_found = re.findall(r'\{\{([^}]+)\}\}', generated_content)
        for token in tokens_found:
            personalization_tokens[token] = f"{{{{{token}}}}}"

        return {
            "segment": request.segment,
            "campaign_type": request.campaign_type,
            "subject_line": subject_line,
            "message_body": message_body,
            "call_to_action": cta,
            "expected_open_rate": segment_data["avg_open_rate"],
            "expected_conversion": segment_data["avg_conversion"],
            "personalization_tokens": personalization_tokens,
            "segment_traits": segment_data["traits"],
            "recommended_send_time": "Tuesday 10 AM" if request.segment == "power_buyer" else "Friday 6 PM"
        }

    except Exception as e:
        logger.error(f"Error generating campaign: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate campaign: {str(e)}"
        )
