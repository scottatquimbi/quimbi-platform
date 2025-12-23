"""
AI Draft Generation Service

Generates intelligent, personalized response drafts using:
- Customer behavioral profile (13-axis segmentation)
- Churn risk assessment
- Customer lifetime value
- Order history and tracking info
- Past ticket resolutions
- Channel-specific tone and length

Philosophy: Proactive Context + Channel Adaptation
- Agent doesn't search for info - AI gathers it automatically
- Response matches channel (SMS ≠ Email ≠ Chat)
- Tone adapts to customer value and churn risk
- Context invisibly injected into prompt
"""
from typing import Optional
import anthropic
import openai
from app.core.config import settings


class AIService:
    """Generate intelligent AI response drafts."""

    def __init__(self):
        self.llm_provider = settings.draft_llm_provider
        self.model = settings.draft_model

        if self.llm_provider == "anthropic":
            self.anthropic_client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key
            )
        elif self.llm_provider == "openai":
            openai.api_key = settings.openai_api_key

    async def generate_draft(
        self,
        ticket: dict,
        customer: dict,
        context: Optional[dict] = None
    ) -> dict:
        """
        Generate AI draft response.

        Args:
            ticket: Ticket data (messages, channel, priority)
            customer: Customer data (profile, churn risk, LTV)
            context: Optional proactive context (orders, tracking, past tickets)

        Returns:
            {
                "content": "Draft message text...",
                "tone": "professional",
                "channel": "email",
                "reasoning": "Why this response...",
                "personalization": {
                    "used_order_info": True,
                    "mentioned_past_issue": False,
                    "applied_vip_treatment": True
                }
            }
        """
        # Build comprehensive prompt with all context
        prompt = self._build_prompt(ticket, customer, context or {})

        # Channel-specific constraints
        constraints = self._get_channel_constraints(ticket.get("channel", "email"))

        # Generate draft
        draft_text = await self._call_llm(prompt, constraints)

        # Detect tone and personalization
        tone = self._detect_tone(draft_text, ticket.get("channel"))
        personalization = self._extract_personalizations(
            draft_text, context or {}
        )

        return {
            "content": draft_text,
            "tone": tone,
            "channel": ticket.get("channel"),
            "reasoning": f"Generated {tone} response for {ticket.get('channel')}",
            "personalization": personalization
        }

    def _build_prompt(
        self,
        ticket: dict,
        customer: dict,
        context: dict
    ) -> str:
        """
        Build comprehensive prompt with invisible intelligence.

        All context is injected without agent intervention.
        """
        channel = ticket.get("channel", "email")
        messages = ticket.get("messages", [])
        customer_message = messages[-1].get("content", "") if messages else ""

        # Get customer metrics
        business_metrics = customer.get("business_metrics", {})
        churn_risk = customer.get("churn_risk", {})
        ltv = business_metrics.get("lifetime_value", 0)
        churn_score = churn_risk.get("churn_risk_score", 0)

        # Determine if VIP
        is_vip = ltv > 1000
        is_high_churn = churn_score > 0.7

        prompt = f"""You are a customer support agent responding to a ticket.

CHANNEL: {channel.upper()}
{self._get_channel_instructions(channel)}

CUSTOMER PROFILE:
- Status: {'⭐ VIP CUSTOMER' if is_vip else 'Regular Customer'}
- Lifetime Value: ${ltv:.2f}
- Churn Risk: {churn_score * 100:.0f}% {'⚠️ HIGH RISK' if is_high_churn else '✅ Low Risk'}
- Total Orders: {business_metrics.get('total_orders', 0)}

CUSTOMER'S MESSAGE:
"{customer_message}"

ISSUE CONTEXT:
"""

        # Add order context if available
        orders = context.get("orders", [])
        if orders:
            order = orders[0]
            prompt += f"""
- Recent Order: #{order.get('order_number', 'N/A')} (${order.get('total', 0):.2f})
- Order Status: {order.get('status', 'unknown')}
- Placed: {order.get('days_ago', 'N/A')} days ago
"""

        # Add tracking info if available
        tracking = context.get("tracking", {})
        if tracking:
            prompt += f"""
- Tracking Status: {tracking.get('status', 'unknown')}
- Last Update: {tracking.get('last_update', 'N/A')}
"""

        # Add past issue context
        past_tickets = context.get("past_tickets", [])
        if past_tickets:
            similar = [
                t for t in past_tickets
                if t.get("category") == ticket.get("category")
            ]
            if similar:
                prompt += f"""
⚠️ IMPORTANT: Customer had similar issue {similar[0].get('days_ago', 'N/A')} days ago
Previous resolution: {similar[0].get('resolution', 'Unknown')}
"""

        # Add special instructions for high-value/high-churn customers
        if is_high_churn or is_vip:
            prompt += """

🎯 CRITICAL INSTRUCTIONS (High-value customer at churn risk):
1. Be extra helpful and proactive
2. Offer expedited solutions when possible
3. Consider mentioning appreciation for their business
4. Solve the issue completely - don't ask them to do extra steps
5. Offer compensation if appropriate (discount/credit)
"""

        # Final instructions
        prompt += f"""

RESPONSE REQUIREMENTS:
1. Acknowledge their specific issue with empathy
2. Show you understand the full context (mention order# if relevant)
3. Offer a clear, actionable solution
4. Match the {channel} channel tone and length constraints
5. Be appropriately personalized to their customer status

Write the response now:"""

        return prompt

    def _get_channel_instructions(self, channel: str) -> str:
        """Get channel-specific instructions."""
        instructions = {
            'sms': """
- STRICT: Maximum 160 characters
- Casual, friendly tone
- Use abbreviations if needed
- Get straight to the point
""",
            'email': """
- Professional but warm tone
- Can be detailed (up to 200 words)
- Use proper formatting
- Include greeting and signature placeholder
""",
            'chat': """
- Conversational, friendly tone
- Keep under 100 words
- Use short paragraphs
- Feel immediate and personal
""",
            'phone': """
- Conversational script format
- Natural speech patterns
- Include empathy statements
- Under 75 words
"""
        }
        return instructions.get(channel, instructions['email'])

    def _get_channel_constraints(self, channel: str) -> dict:
        """Get channel-specific generation constraints."""
        constraints = {
            'sms': {'max_tokens': 50, 'temperature': 0.7},
            'email': {'max_tokens': 300, 'temperature': 0.7},
            'chat': {'max_tokens': 150, 'temperature': 0.8},
            'phone': {'max_tokens': 120, 'temperature': 0.7}
        }
        return constraints.get(channel, constraints['email'])

    async def _call_llm(self, prompt: str, constraints: dict) -> str:
        """Call LLM with provider abstraction."""
        if self.llm_provider == "anthropic":
            return await self._call_anthropic(prompt, constraints)
        elif self.llm_provider == "openai":
            return await self._call_openai(prompt, constraints)
        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")

    async def _call_anthropic(self, prompt: str, constraints: dict) -> str:
        """Call Anthropic Claude."""
        try:
            message = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=constraints.get('max_tokens', 300),
                temperature=constraints.get('temperature', 0.7),
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text.strip()
        except Exception as e:
            # Fallback to simple response if AI fails
            return self._fallback_response()

    async def _call_openai(self, prompt: str, constraints: dict) -> str:
        """Call OpenAI GPT."""
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful customer support agent."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=constraints.get('max_tokens', 300),
                temperature=constraints.get('temperature', 0.7)
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return self._fallback_response()

    def _fallback_response(self) -> str:
        """Simple fallback if AI generation fails."""
        return "Thank you for contacting us. We're looking into your issue and will respond shortly."

    def _detect_tone(self, draft_text: str, channel: str) -> str:
        """Detect tone of generated draft."""
        # Simple heuristic detection
        if channel == 'sms':
            return 'casual'
        elif 'sincerely' in draft_text.lower() or 'regards' in draft_text.lower():
            return 'professional'
        else:
            return 'friendly'

    def _extract_personalizations(
        self,
        draft_text: str,
        context: dict
    ) -> dict:
        """Extract what personalizations were applied."""
        return {
            'used_order_info': bool(context.get('orders')),
            'mentioned_tracking': 'tracking' in draft_text.lower(),
            'referenced_past_issue': bool(context.get('past_tickets')),
            'applied_vip_treatment': 'appreciate' in draft_text.lower() or 'value' in draft_text.lower()
        }
