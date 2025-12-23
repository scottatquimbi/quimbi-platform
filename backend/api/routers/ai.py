"""
AI Endpoints Router

Provides AI-powered features for the ticketing system:
- Next best action recommendations
- Draft response generation
- Response regeneration with parameters
- Action completion tracking
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from sqlalchemy import select
import os

from backend.core.database import get_db_session
from backend.models import Ticket, TicketMessage, TicketAIRecommendation
from backend.api.dependencies import require_api_key
import httpx
from backend.api.routers.swagger_examples import (
    AI_REGENERATE_REQUEST_EXAMPLE,
    AI_RECOMMENDATION_RESPONSE_EXAMPLE,
    AI_DRAFT_RESPONSE_EXAMPLE,
    AI_REGENERATE_RESPONSE_EXAMPLE,
    ERROR_NOT_FOUND_EXAMPLE
)

# Import Claude client
import anthropic

# Import AI service for draft generation
from backend.services.ai_service import ai_service

router = APIRouter(prefix="/api/ai", tags=["ai"], dependencies=[Depends(require_api_key)])

# Initialize Claude client
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ==================== Request/Response Models ====================

class RegenerateRequest(BaseModel):
    """Request model for regenerating draft response."""
    tone: Optional[str] = Field(None, description="Tone: friendly, professional, empathetic, apologetic")
    length: Optional[str] = Field(None, description="Length: short, medium, long")
    include_offer: Optional[bool] = Field(None, description="Include compensation offer")
    template: Optional[str] = Field(None, description="Use specific template")

    model_config = {"json_schema_extra": {"example": AI_REGENERATE_REQUEST_EXAMPLE}}


class ActionCompletionRequest(BaseModel):
    """Request model for marking action as completed."""
    completed: bool = Field(..., description="Mark action as completed")

    model_config = {"json_schema_extra": {"example": {"completed": True}}}


# ==================== Helper Functions ====================

async def get_customer_recent_products(customer_id: str, limit: int = 10) -> list:
    """
    Fetch customer's recent product purchases from Shopify.
    Returns list of product names, vendors, and details for AI context.
    """
    try:
        shop_name = os.getenv("SHOPIFY_SHOP_NAME")
        access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        api_version = os.getenv("SHOPIFY_API_VERSION", "2024-10")

        if not shop_name or not access_token:
            return []

        graphql_url = f"https://{shop_name}.myshopify.com/admin/api/{api_version}/graphql.json"
        shopify_gid = f"gid://shopify/Customer/{customer_id}"

        query = """
        query ($id: ID!, $limit: Int!) {
          customer(id: $id) {
            orders(first: $limit, sortKey: CREATED_AT, reverse: true) {
              nodes {
                createdAt
                lineItems(first: 20) {
                  nodes {
                    title
                    vendor
                    sku
                    quantity
                    variant {
                      title
                    }
                  }
                }
              }
            }
          }
        }
        """

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                graphql_url,
                json={"query": query, "variables": {"id": shopify_gid, "limit": limit}},
                headers={
                    "X-Shopify-Access-Token": access_token,
                    "Content-Type": "application/json"
                }
            )

            if response.status_code != 200:
                return []

            data = response.json()
            customer_data = data.get("data", {}).get("customer")
            if not customer_data:
                return []

            # Extract unique products
            products = []
            seen = set()
            for order in customer_data.get("orders", {}).get("nodes", []):
                for item in order.get("lineItems", {}).get("nodes", []):
                    title = item.get("title", "")
                    if title and title not in seen:
                        seen.add(title)
                        products.append({
                            "name": title,
                            "vendor": item.get("vendor", ""),
                            "variant": item.get("variant", {}).get("title", ""),
                            "sku": item.get("sku", "")
                        })

            return products[:20]  # Limit to 20 products for context

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not fetch Shopify products for AI: {e}")
        return []


async def get_customer_profile_for_ai(customer_id: str, session):
    """Get customer profile data for AI context including archetype behavioral traits."""
    try:
        from sqlalchemy import text

        # Query customer_profiles with archetype details
        result = await session.execute(
            text("""
                SELECT
                    cp.customer_id,
                    cp.archetype_id,
                    cp.archetype_level,
                    cp.segment_memberships,
                    cp.dominant_segments,
                    cp.lifetime_value,
                    cp.total_orders,
                    cp.avg_order_value,
                    cp.churn_risk_score,
                    cp.days_since_last_purchase,
                    cp.customer_tenure_days,
                    ad.dominant_segments as archetype_segments,
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

        # Parse archetype segments for communication guidance
        archetype_segments = row[11] if row[11] else {}
        behavioral_traits = row[12] if row[12] else {}

        # Build communication style guidance based on archetype
        # NOTE: These are BACKGROUND CONTEXT only - do NOT override what customer explicitly states
        communication_style = []
        if archetype_segments:
            # Price sensitivity affects how to discuss costs
            price_sens = archetype_segments.get('price_sensitivity', '')
            if 'deal_hunter' in price_sens:
                communication_style.append("Customer typically responds well to value/savings (but only mention actual promotions, never make them up)")
            elif 'full_price' in price_sens:
                communication_style.append("Focus on quality and value, not discounts")
            elif 'strategic' in price_sens:
                communication_style.append("Highlight value propositions")

            # Purchase frequency affects urgency
            freq = archetype_segments.get('purchase_frequency', '')
            if 'power_buyer' in freq:
                communication_style.append("Frequent shopper - they know the store well")
            elif 'occasional' in freq:
                communication_style.append("Be welcoming and encouraging")

            # Shopping maturity - NOTE: This is their PURCHASE HISTORY, not their expertise in quilting
            maturity = archetype_segments.get('shopping_maturity', '')
            total_orders = row[6] if row[6] else 0  # Get actual order count

            if 'long_term' in maturity or 'established' in maturity:
                communication_style.append("Familiar with the store (but gauge their quilting expertise from their actual message)")
            elif 'new' in maturity:
                # Distinguish between truly new customers vs low-engagement existing customers
                if total_orders > 0:
                    communication_style.append("Low engagement customer - needs re-engagement, not first impression")
                else:
                    communication_style.append("New to the store - be extra welcoming")

            # Return behavior affects approach to issues
            returns = archetype_segments.get('return_behavior', '')
            if 'careful_buyer' in returns:
                communication_style.append("This customer rarely returns - take their concerns seriously")

        # Return in format expected by AI functions
        return {
            "customer_id": row[0],
            "archetype": {
                "id": row[1],
                "level": row[2],
                "segments": archetype_segments,
                "traits": behavioral_traits
            },
            "business_metrics": {
                "lifetime_value": row[5],
                "total_orders": row[6],
                "avg_order_value": row[7],
                "days_since_last_purchase": row[9],
                "customer_tenure_days": row[10]
            },
            "churn_risk": {
                "score": row[8],
                "risk_level": "critical" if row[8] and row[8] >= 0.7 else "high" if row[8] and row[8] >= 0.5 else "medium" if row[8] and row[8] >= 0.3 else "low"
            },
            "segment_memberships": row[3],  # JSONB
            "dominant_segments": row[4],  # JSONB
            "communication_style": communication_style
        }

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading customer profile for AI: {e}", exc_info=True)
        return None


async def get_ticket_context(ticket_id: str, session):
    """
    Get full ticket context for AI generation.

    Supports lookup by UUID or ticket_number (e.g., "T-005").
    """
    import uuid as uuid_module

    # Try to determine if it's a UUID or ticket_number
    try:
        # Try parsing as UUID
        uuid_obj = uuid_module.UUID(ticket_id)
        # It's a valid UUID, query by ID
        query = select(Ticket).where(Ticket.id == uuid_obj)
    except (ValueError, AttributeError):
        # Not a UUID, assume it's a ticket_number
        query = select(Ticket).where(Ticket.ticket_number == ticket_id)

    result = await session.execute(query)
    ticket = result.scalar_one_or_none()

    if not ticket:
        return None

    # Get messages (use ticket.id which is the UUID)
    msg_query = select(TicketMessage).where(TicketMessage.ticket_id == ticket.id).order_by(TicketMessage.created_at)
    msg_result = await session.execute(msg_query)
    messages = msg_result.scalars().all()

    # Get customer profile
    customer_profile = await get_customer_profile_for_ai(ticket.customer_id, session)

    # Get customer's recent products from Shopify
    recent_products = await get_customer_recent_products(ticket.customer_id)

    return {
        "ticket": ticket,
        "messages": messages,
        "customer_profile": customer_profile,
        "recent_products": recent_products
    }


def generate_ai_recommendation(context: dict) -> dict:
    """
    Generate AI recommendation using Claude API.

    Takes ticket context and customer profile, returns:
    - Priority assessment
    - Next best actions
    - Talking points
    - Warnings
    - Estimated impact
    """
    ticket = context["ticket"]
    messages = context["messages"]
    customer_profile = context.get("customer_profile")

    # Build conversation history
    conversation = "\n\n".join([
        f"{'Agent' if m.from_agent else 'Customer'} ({m.author_name}): {m.content}"
        for m in messages
    ])

    # Build customer context
    customer_context = ""
    if customer_profile:
        customer_context = f"""
Customer Profile:
- LTV: ${customer_profile.get('business_metrics', {}).get('lifetime_value', 0):.2f}
- Total Orders: {customer_profile.get('business_metrics', {}).get('total_orders', 0)}
- Churn Risk: {customer_profile.get('churn_risk', {}).get('risk_level', 'unknown')} ({customer_profile.get('churn_risk', {}).get('churn_risk_score', 0):.0%})
- Customer Since: {customer_profile.get('business_metrics', {}).get('customer_tenure_days', 0)} days
"""

    # Extract customer metrics for context
    ltv = customer_profile.get('business_metrics', {}).get('lifetime_value', 0) if customer_profile else 0
    churn_score = customer_profile.get('churn_risk', {}).get('score', 0) if customer_profile else 0
    total_orders = customer_profile.get('business_metrics', {}).get('total_orders', 0) if customer_profile else 0

    # Build prompt
    prompt = f"""You are an expert customer support analyst helping agents provide excellent service.

Analyze this support ticket and provide strategic recommendations.

Ticket #{ticket.ticket_number}
Channel: {ticket.channel}
Subject: {ticket.subject or 'N/A'}
Status: {ticket.status}
Priority: {ticket.priority}

{customer_context}

Conversation:
{conversation}

Provide a JSON response with:
1. priority: Overall priority level (urgent/high/normal/low)
   - Use "urgent" for VIP customers (LTV > $1000 OR orders > 20) with critical issues
   - Use "high" for high-value customers (LTV > $500) or churn risk > 0.5
   - Use "normal" for standard inquiries
   - Use "low" for informational questions from low-risk customers

2. actions: Array of 2-4 specific next best actions, each with:
   - action: Clear, actionable step (be specific to THIS ticket's issue)
   - priority: Numeric priority (1=highest)
   - reasoning: Why this action matters for THIS specific customer and situation

3. talking_points: Array of 3-5 key points to emphasize in response
   - Make these specific to the customer's issue, NOT generic
   - Reference specific products, patterns, or issues mentioned in the ticket

4. warnings: Array of critical issues to be aware of
   - Include VIP status if LTV > $1000 or orders > 20
   - Include high churn risk if score > 0.5
   - Include specific business risks (e.g., "damaged shipment may trigger refund request")
   - Make warnings specific to THIS ticket, not generic

5. estimated_impact:
   - retention_probability: 0-1 (calculate based on churn risk and issue severity)
     * Start with base: 1.0 - churn_risk_score
     * Adjust down for critical issues (missing items, damaged goods): -0.05 to -0.15
     * Adjust up for good resolution potential (info questions, easy fixes): +0.05 to +0.10
   - revenue_at_risk: Dollar amount
     * For critical issues (missing items, damaged goods, wrong items): Use customer's LTV (${ltv:.2f})
     * For high-priority complaints with churn risk > 0.5: Use LTV * churn_risk_score
     * For normal inquiries or low-risk customers: Use 0
     * IMPORTANT: Base this on the ACTUAL customer LTV provided above, not a generic estimate

CRITICAL INSTRUCTIONS FOR REVENUE CALCULATION:
- Customer LTV is ${ltv:.2f} - use THIS value in your calculations
- Churn risk is {churn_score} ({churn_score * 100:.0f}%)
- If this is a critical issue (missing/damaged/wrong item), revenue_at_risk should be close to or equal to LTV
- If this is a complaint from high churn risk customer, revenue_at_risk = LTV * churn_risk_score
- If this is just an info question, revenue_at_risk should be 0 or very low

Focus on:
- Customer value and churn risk (THIS customer, not generic)
- Resolution path that maintains relationship
- Proactive solutions before customer asks
- Personalization based on THIS customer's history and THIS ticket's specific issue
"""

    try:
        response = claude_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse JSON response
        import json
        result = json.loads(response.content[0].text)

        return result

    except Exception as e:
        # Return fallback recommendation
        return {
            "priority": "normal",
            "actions": [
                {
                    "action": "Review ticket details and customer history",
                    "priority": 1,
                    "reasoning": "Understand full context before responding"
                },
                {
                    "action": "Respond to customer inquiry with empathy",
                    "priority": 2,
                    "reasoning": "Acknowledge their concern and show understanding"
                }
            ],
            "talking_points": [
                "Thank customer for reaching out",
                "Show empathy for their situation",
                "Provide clear next steps"
            ],
            "warnings": [],
            "estimated_impact": {
                "retention_probability": 0.75,
                "revenue_at_risk": 0
            }
        }


def generate_draft_response(context: dict, tone: str = "empathetic", length: str = "medium") -> dict:
    """
    Generate AI draft response using Claude API.

    Takes ticket context and parameters, returns personalized draft response.
    Uses customer archetype to personalize communication style and provide actual solutions.
    """
    ticket = context["ticket"]
    messages = context["messages"]
    customer_profile = context.get("customer_profile")
    recent_products = context.get("recent_products", [])

    # Get last customer message
    customer_messages = [m for m in messages if not m.from_agent]
    last_customer_message = customer_messages[-1] if customer_messages else None

    if not last_customer_message:
        return {
            "draft": "No customer message to respond to.",
            "tone": tone,
            "personalization_applied": []
        }

    # Build customer context with archetype-based communication guidance
    customer_context = ""
    personalization = []
    communication_guidance = []

    if customer_profile:
        ltv = customer_profile.get('business_metrics', {}).get('lifetime_value', 0)
        total_orders = customer_profile.get('business_metrics', {}).get('total_orders', 0)
        churn_risk = customer_profile.get('churn_risk', {}).get('risk_level', 'unknown')

        # Get archetype-based communication style
        comm_style = customer_profile.get('communication_style', [])
        if comm_style:
            communication_guidance = comm_style
            personalization.append("Archetype-based communication style applied")

        # Get behavioral segments for context
        archetype = customer_profile.get('archetype', {})
        segments = archetype.get('segments', {})

        if segments:
            customer_context += "\nCustomer Behavioral Profile:"
            if segments.get('purchase_value'):
                customer_context += f"\n- Purchase tier: {segments.get('purchase_value')}"
            if segments.get('price_sensitivity'):
                customer_context += f"\n- Price sensitivity: {segments.get('price_sensitivity')}"
            if segments.get('shopping_maturity'):
                customer_context += f"\n- Experience level: {segments.get('shopping_maturity')}"
            if segments.get('purchase_frequency'):
                customer_context += f"\n- Purchase frequency: {segments.get('purchase_frequency')}"

        # Include business context without arbitrary VIP labels
        # Only use actual VIP membership when available from tags
        customer_context += f"\n- Lifetime value: ${ltv:.2f}"
        customer_context += f"\n- Order history: {total_orders} orders"

        if churn_risk in ["critical", "high"]:
            customer_context += f"\n- Churn risk: {churn_risk}"
            personalization.append("Churn risk considered")

    # Build conversation history
    recent_messages = messages[-3:] if len(messages) > 3 else messages
    conversation = "\n\n".join([
        f"{'Agent' if m.from_agent else 'Customer'}: {m.content}"
        for m in recent_messages
    ])

    # Tone instructions
    tone_instructions = {
        "friendly": "Use a warm, casual, friendly tone. Be conversational and personable.",
        "professional": "Use a formal, professional tone. Be clear and business-like.",
        "empathetic": "Show deep empathy and understanding. Acknowledge their feelings.",
        "apologetic": "Express sincere apology. Take ownership of the issue."
    }

    # Length instructions
    length_instructions = {
        "short": "Keep response brief (2-3 sentences)",
        "medium": "Provide moderate detail (1-2 paragraphs)",
        "long": "Give comprehensive response (3-4 paragraphs)"
    }

    # Build communication guidance string
    guidance_str = ""
    if communication_guidance:
        guidance_str = "\n\nCommunication Style Guidance (based on customer archetype):\n" + "\n".join(f"- {g}" for g in communication_guidance)

    # Build products context
    products_str = ""
    if recent_products:
        products_str = "\n\nCustomer's Recent Purchases (use exact product names):"
        for p in recent_products[:10]:
            vendor = f" by {p['vendor']}" if p.get('vendor') else ""
            variant = f" ({p['variant']})" if p.get('variant') else ""
            products_str += f"\n- {p['name']}{vendor}{variant}"
        personalization.append("Product history included")

    # Build tracking/order context from ticket custom_fields
    tracking_str = ""
    if ticket.custom_fields and isinstance(ticket.custom_fields, dict):
        order_num = ticket.custom_fields.get('order_number')
        tracking_num = ticket.custom_fields.get('tracking_number')
        carrier = ticket.custom_fields.get('carrier')
        status = ticket.custom_fields.get('carrier_status')
        last_update = ticket.custom_fields.get('last_update')
        estimated_delivery = ticket.custom_fields.get('estimated_delivery')
        delivered_date = ticket.custom_fields.get('delivered_date')
        items = ticket.custom_fields.get('items', [])

        if order_num:
            tracking_str = f"\n\nOrder Information (USE THIS DATA - it's real):"
            tracking_str += f"\n- Order Number: {order_num}"

            if items:
                tracking_str += "\n- Items in this order:"
                for item in items:
                    tracking_str += f"\n  * {item.get('name')} (qty: {item.get('quantity')})"

            if tracking_num:
                tracking_str += f"\n- Tracking Number: {tracking_num}"
                tracking_str += f"\n- Carrier: {carrier}"
                tracking_str += f"\n- Current Status: {status}"
                if last_update:
                    tracking_str += f"\n- Last Update: {last_update}"
                if delivered_date:
                    tracking_str += f"\n- Delivered: {delivered_date}"
                elif estimated_delivery:
                    tracking_str += f"\n- Estimated Delivery: {estimated_delivery}"
            else:
                # Pre-order or not yet shipped
                if status:
                    tracking_str += f"\n- Status: {status}"
                estimated_ship = ticket.custom_fields.get('estimated_ship_date')
                if estimated_ship:
                    tracking_str += f"\n- Estimated Ship Date: {estimated_ship}"

            # Replacement/return info
            if ticket.custom_fields.get('replacement_order'):
                tracking_str += f"\n- Replacement Order: {ticket.custom_fields['replacement_order']}"
                if ticket.custom_fields.get('replacement_tracking'):
                    tracking_str += f"\n- Replacement Tracking: {ticket.custom_fields['replacement_tracking']}"
                    tracking_str += f"\n- Replacement Status: {ticket.custom_fields.get('replacement_status', 'Unknown')}"

            personalization.append("Order/tracking information included")

    prompt = f"""You are an expert customer support agent for a quilting/fabric supply store. Write a response that ACTUALLY SOLVES the customer's problem.

Ticket Context:
- Channel: {ticket.channel}
- Subject: {ticket.subject or 'Customer inquiry'}
{customer_context}
{guidance_str}
{products_str}
{tracking_str}

Recent Conversation:
{conversation}

CRITICAL INSTRUCTIONS:
1. READ THE CUSTOMER'S ACTUAL MESSAGE CAREFULLY
   - If they say "first time making a quilt" → treat them as a beginner quilter
   - If they say "I'm new to this" → provide detailed explanations
   - If they ask "what do you recommend" → give a specific product recommendation
   - The customer's actual words ALWAYS override the background profile data

2. ACTUALLY ANSWER THE QUESTION - Don't just say "let me look into it" or "I'll check on that"

3. PROVIDE SPECIFIC SOLUTIONS based on the issue type:
   - Missing items: Offer immediate replacement shipment
   - Wrong items: Provide return label + correct item shipment
   - Product questions: Give direct, knowledgeable answers about fabrics/patterns
   - Damaged items: Offer replacement or refund
   - Shipping delays: Provide tracking info and realistic timeline
   - Pattern questions: Give specific instructions or clarifications
   - Pre-order inquiries: Give specific estimated dates
   - Returns: Explain the process clearly with next steps

4. USE EXACT PRODUCT NAMES from the customer's purchase history when relevant

5. FOR TECHNICAL QUESTIONS (cutting instructions, care guides, pattern help):
   - If the question requires manufacturer-specific information (like care instructions for a specific fabric brand, or pattern instructions), direct them to the manufacturer's website
   - Use the vendor name from their purchase to suggest: "[Vendor name] has detailed care/instruction guides on their website"
   - For sewing machine questions, suggest the manufacturer's manual or support site

6. Tone: {tone_instructions.get(tone, tone_instructions['empathetic'])}
7. Length: {length_instructions.get(length, length_instructions['medium'])}
8. The "Communication Style Guidance" above is BACKGROUND CONTEXT about shopping habits - use it to inform your tone, but never let it contradict what the customer actually says
9. Include concrete next steps the customer should take (if any)

IMPORTANT - DO NOT:
- Offer discounts, coupons, store credit, or promotions unless you have specific promotion data
- NEVER make up promotion codes, shipping offers, or discount percentages
- Call the customer "VIP" or "valued customer" - just be helpful and professional
- Make promises about compensation - focus on solving the actual problem
- Use excessive flattery or over-the-top appreciation language
- Misread the customer's expertise level - if they say "first time," believe them

Write a response that demonstrates product knowledge and solves the problem directly. When you don't have specific technical information, point to authoritative external sources (manufacturer websites, pattern designers). Be helpful and professional. Only include the message body, no greetings or signatures."""

    try:
        response = claude_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        draft = response.content[0].text

        return {
            "draft": draft,
            "tone": tone,
            "personalization_applied": personalization
        }

    except Exception as e:
        return {
            "draft": f"Thank you for contacting us. We're looking into your {ticket.subject or 'inquiry'} and will get back to you shortly.",
            "tone": tone,
            "personalization_applied": []
        }


# ==================== Endpoints ====================

@router.get(
    "/tickets/{ticket_id}/recommendation",
    responses={
        200: {
            "description": "AI-generated recommendation",
            "content": {"application/json": {"example": AI_RECOMMENDATION_RESPONSE_EXAMPLE}}
        },
        404: {
            "description": "Ticket not found",
            "content": {"application/json": {"example": ERROR_NOT_FOUND_EXAMPLE}}
        }
    }
)
async def get_recommendation(ticket_id: str):
    """
    Get AI-generated next best action recommendations for a ticket.

    This endpoint uses Claude 3.5 Haiku to analyze the ticket and customer profile,
    then provides strategic recommendations for handling the ticket effectively.

    **Caching**: Results are cached for 1 hour to improve performance.

    **Returns**:
    - `priority`: Overall ticket priority (urgent/high/normal/low)
    - `actions`: 2-4 specific next steps with priority ranking and reasoning
    - `talking_points`: 3-5 key points to emphasize in your response
    - `warnings`: Critical issues to be aware of (VIP status, churn risk, etc.)
    - `estimated_impact`: Retention probability and revenue at risk
    - `generated_at`: Timestamp of generation

    **Personalization**: Recommendations consider:
    - Customer lifetime value (LTV)
    - Churn risk score and factors
    - Purchase history and behavioral archetype
    - Previous support interactions
    """
    async with get_db_session() as session:
        # Get ticket context first (handles UUID or ticket_number lookup)
        context = await get_ticket_context(ticket_id, session)
        if not context:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        ticket = context["ticket"]

        # Check for existing non-expired recommendation (use ticket.id which is UUID)
        query = (
            select(TicketAIRecommendation)
            .where(TicketAIRecommendation.ticket_id == ticket.id)
            .where(TicketAIRecommendation.expires_at > datetime.utcnow())
            .order_by(TicketAIRecommendation.generated_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        existing_rec = result.scalar_one_or_none()

        if existing_rec:
            # Return cached recommendation
            return existing_rec.to_dict()

        # Generate new recommendation
        ai_result = generate_ai_recommendation(context)

        # Create recommendation record (use ticket.id which is UUID)
        recommendation = TicketAIRecommendation(
            ticket_id=ticket.id,
            priority=ai_result.get("priority"),
            actions=ai_result.get("actions", []),
            talking_points=ai_result.get("talking_points", []),
            warnings=ai_result.get("warnings", []),
            estimated_impact=ai_result.get("estimated_impact", {}),
            generated_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )

        session.add(recommendation)
        await session.commit()
        await session.refresh(recommendation)

        return recommendation.to_dict()


@router.get(
    "/tickets/{ticket_id}/draft-response",
    responses={
        200: {
            "description": "AI-generated draft response",
            "content": {"application/json": {"example": AI_DRAFT_RESPONSE_EXAMPLE}}
        },
        404: {
            "description": "Ticket not found",
            "content": {"application/json": {"example": ERROR_NOT_FOUND_EXAMPLE}}
        }
    }
)
async def get_draft_response(ticket_id: str):
    """
    Get AI-generated draft response for a ticket.

    This endpoint uses Claude 3.5 Haiku to generate a personalized draft response
    that agents can use as a starting point or send directly.

    **Caching**: Results are cached for 1 hour to improve performance.

    **Returns**:
    - `draft`: Draft response text (ready to send)
    - `tone`: Tone used (empathetic by default)
    - `personalization_applied`: List of personalizations made
    - `generated_at`: Timestamp of generation

    **Personalization includes**:
    - VIP status acknowledgment
    - Reference to customer's purchase history
    - Urgency awareness (deadlines, time-sensitive issues)
    - Churn risk mitigation language
    - Behavioral archetype-appropriate communication style

    **Use with regenerate endpoint** to customize tone/length if needed.
    """
    async with get_db_session() as session:
        # Get ticket context first (handles UUID or ticket_number lookup)
        context = await get_ticket_context(ticket_id, session)
        if not context:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        ticket = context["ticket"]
        messages = context["messages"]
        current_message_count = len(messages)

        # Check for existing non-expired recommendation with draft (use ticket.id which is UUID)
        query = (
            select(TicketAIRecommendation)
            .where(TicketAIRecommendation.ticket_id == ticket.id)
            .where(TicketAIRecommendation.expires_at > datetime.utcnow())
            .where(TicketAIRecommendation.draft_response.isnot(None))
            .order_by(TicketAIRecommendation.generated_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        existing_rec = result.scalar_one_or_none()

        # Only use cached draft if message count hasn't changed
        # This ensures new messages trigger fresh AI generation
        if existing_rec:
            cached_message_count = existing_rec.message_count or 0
            if cached_message_count == current_message_count:
                # Return cached draft - conversation hasn't changed
                return {
                    "ticket_id": str(existing_rec.ticket_id),
                    "draft": existing_rec.draft_response,
                    "tone": existing_rec.draft_tone or "empathetic",
                    "personalization_applied": existing_rec.draft_personalization or [],
                    "generated_at": existing_rec.generated_at.isoformat()
                }
            # Message count changed - invalidate cache and regenerate

        # Generate new draft
        draft_result = generate_draft_response(context)

        # Update or create recommendation record (use ticket.id which is UUID)
        query = (
            select(TicketAIRecommendation)
            .where(TicketAIRecommendation.ticket_id == ticket.id)
            .order_by(TicketAIRecommendation.generated_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        recommendation = result.scalar_one_or_none()

        if recommendation and not recommendation.is_expired:
            # Update existing with new draft and message count
            recommendation.draft_response = draft_result["draft"]
            recommendation.draft_tone = draft_result["tone"]
            recommendation.draft_personalization = draft_result["personalization_applied"]
            recommendation.message_count = current_message_count
        else:
            # Create new
            recommendation = TicketAIRecommendation(
                ticket_id=ticket.id,
                actions=[],
                draft_response=draft_result["draft"],
                draft_tone=draft_result["tone"],
                draft_personalization=draft_result["personalization_applied"],
                message_count=current_message_count,
                generated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )
            session.add(recommendation)

        await session.commit()
        await session.refresh(recommendation)

        return {
            "ticket_id": str(recommendation.ticket_id),
            "draft": recommendation.draft_response,
            "tone": recommendation.draft_tone,
            "personalization_applied": recommendation.draft_personalization or [],
            "generated_at": recommendation.generated_at.isoformat()
        }


@router.post(
    "/tickets/{ticket_id}/draft-response/regenerate",
    responses={
        200: {
            "description": "Regenerated draft response",
            "content": {"application/json": {"example": AI_REGENERATE_RESPONSE_EXAMPLE}}
        },
        404: {
            "description": "Ticket not found",
            "content": {"application/json": {"example": ERROR_NOT_FOUND_EXAMPLE}}
        }
    }
)
async def regenerate_draft_response(ticket_id: str, params: RegenerateRequest):
    """
    Regenerate AI draft response with custom parameters.

    Use this endpoint when the initial draft doesn't match your needs.
    Always generates a fresh response (doesn't use cache).

    **Customization options**:
    - `tone`: friendly, professional, empathetic (default), apologetic
    - `length`: short, medium (default), long
    - `include_offer`: Boolean to include compensation offer
    - `template`: Name of specific template to use

    **Tone examples**:
    - `friendly`: "Hey Sarah! Oh no, so sorry about that..."
    - `professional`: "Dear Ms. Johnson, We apologize for the inconvenience..."
    - `empathetic`: "I completely understand how frustrating this must be..."
    - `apologetic`: "We sincerely apologize for this issue..."

    **Length examples**:
    - `short`: 2-3 sentences, quick acknowledgment
    - `medium`: 1-2 paragraphs, balanced detail
    - `long`: 3-4 paragraphs, comprehensive explanation

    Try different combinations until you get the perfect response!
    """
    async with get_db_session() as session:
        context = await get_ticket_context(ticket_id, session)
        if not context:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        ticket = context["ticket"]

        # Generate with specified parameters
        tone = params.tone or "empathetic"
        length = params.length or "medium"

        draft_result = generate_draft_response(context, tone=tone, length=length)

        # Create new recommendation (don't update existing) - use ticket.id which is UUID
        recommendation = TicketAIRecommendation(
            ticket_id=ticket.id,
            actions=[],
            draft_response=draft_result["draft"],
            draft_tone=draft_result["tone"],
            draft_personalization=draft_result["personalization_applied"],
            generated_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        session.add(recommendation)

        await session.commit()
        await session.refresh(recommendation)

        return {
            "ticket_id": str(recommendation.ticket_id),
            "draft": recommendation.draft_response,
            "tone": recommendation.draft_tone,
            "length": length,
            "generated_at": recommendation.generated_at.isoformat()
        }


@router.patch("/tickets/{ticket_id}/recommendation/actions/{action_index}")
async def mark_action_completed(
    ticket_id: str,
    action_index: int,
    completion: ActionCompletionRequest
):
    """
    Mark a specific recommended action as completed.

    Updates the action's completed status in the cached recommendation.
    """
    async with get_db_session() as session:
        # Get latest recommendation
        query = (
            select(TicketAIRecommendation)
            .where(TicketAIRecommendation.ticket_id == ticket_id)
            .order_by(TicketAIRecommendation.generated_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        recommendation = result.scalar_one_or_none()

        if not recommendation:
            raise HTTPException(status_code=404, detail=f"No recommendation found for ticket {ticket_id}")

        # Update action
        actions = recommendation.actions or []
        if action_index >= len(actions):
            raise HTTPException(status_code=404, detail=f"Action index {action_index} not found")

        actions[action_index]["completed"] = completion.completed
        if completion.completed:
            actions[action_index]["completed_at"] = datetime.utcnow().isoformat()

        recommendation.actions = actions

        await session.commit()

        return {
            "action": actions[action_index]
        }
