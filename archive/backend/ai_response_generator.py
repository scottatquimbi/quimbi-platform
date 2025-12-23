"""
AI Response Generator for Customer Service

Uses Google Gemini 1.5 Flash for cost-effective, high-quality responses.
Includes LTV-based compensation engine for automated discount recommendations.

Cost: ~$0.40 per 1,000 customer interactions
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)


class CompensationEngine:
    """Calculate appropriate compensation based on customer value and issue severity."""

    # LTV-based discount tiers
    LTV_TIERS = {
        'whale': {'threshold': 10000, 'max_discount': 0.30, 'priority': 'VIP'},
        'vip': {'threshold': 1000, 'max_discount': 0.20, 'priority': 'High'},
        'high_value': {'threshold': 500, 'max_discount': 0.15, 'priority': 'Medium'},
        'regular': {'threshold': 100, 'max_discount': 0.10, 'priority': 'Standard'},
        'new': {'threshold': 0, 'max_discount': 0.05, 'priority': 'Standard'}
    }

    # Issue severity multipliers
    SEVERITY_MULTIPLIERS = {
        'critical': 1.5,    # Product defect, wrong item shipped
        'high': 1.2,        # Delayed shipment, missing items
        'medium': 1.0,      # Minor quality issues
        'low': 0.8          # Questions, general inquiries
    }

    @classmethod
    def get_customer_tier(cls, ltv: float) -> Dict[str, Any]:
        """Determine customer tier based on LTV."""
        for tier_name, tier_config in cls.LTV_TIERS.items():
            if ltv >= tier_config['threshold']:
                return {'tier': tier_name, **tier_config}
        return {'tier': 'new', **cls.LTV_TIERS['new']}

    @classmethod
    def calculate_compensation(
        cls,
        ltv: float,
        issue_severity: str = 'medium',
        churn_risk: str = 'low'
    ) -> Dict[str, Any]:
        """
        Calculate appropriate compensation.

        Args:
            ltv: Customer lifetime value
            issue_severity: critical, high, medium, low
            churn_risk: critical, high, medium, low

        Returns:
            Compensation recommendation with discount percentage and reasoning
        """
        tier = cls.get_customer_tier(ltv)
        base_discount = tier['max_discount']

        # Apply severity multiplier
        severity_mult = cls.SEVERITY_MULTIPLIERS.get(issue_severity, 1.0)

        # Apply churn risk boost
        churn_boost = 0
        if churn_risk == 'critical':
            churn_boost = 0.10  # Add 10% for critical churn risk
        elif churn_risk == 'high':
            churn_boost = 0.05  # Add 5% for high churn risk

        # Calculate final discount (capped at 50%)
        final_discount = min(base_discount * severity_mult + churn_boost, 0.50)

        reasoning = []
        reasoning.append(f"{tier['tier'].upper()} customer (${ltv:,.2f} LTV)")
        reasoning.append(f"{issue_severity.capitalize()} severity issue")
        if churn_risk in ['high', 'critical']:
            reasoning.append(f"{churn_risk.capitalize()} churn risk - retention critical")

        return {
            'discount_percentage': round(final_discount * 100, 1),
            'tier': tier['tier'],
            'priority': tier['priority'],
            'reasoning': reasoning,
            'automatic_approval': final_discount <= 0.15,  # Auto-approve up to 15%
            'requires_manager': final_discount > 0.30  # Manager approval needed >30%
        }


class GeminiResponseGenerator:
    """Generate customer service responses using Google Gemini 1.5 Flash."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client.

        Args:
            api_key: Google AI API key (defaults to GEMINI_API_KEY env var)
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")

        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            logger.warning("No GEMINI_API_KEY found - AI responses will be mock responses")
            self.model = None
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')

        self.compensation = CompensationEngine()

    def _build_prompt(
        self,
        customer_profile: Dict[str, Any],
        ticket: Dict[str, Any],
        compensation: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the prompt for Gemini."""

        # Extract customer info
        ltv = customer_profile.get('business_metrics', {}).get('lifetime_value', 0)
        orders = customer_profile.get('business_metrics', {}).get('total_orders', 0)
        archetype = customer_profile.get('archetype', {})
        arch_id = archetype.get('archetype_id', 'Unknown')
        churn = customer_profile.get('churn_risk', {})
        churn_level = churn.get('risk_level', 'low')
        churn_factors = churn.get('risk_factors', [])

        # Get dominant segments for context
        segments = customer_profile.get('dominant_segments', {})
        purchase_freq = segments.get('purchase_frequency', 'unknown')
        shopping_style = segments.get('repurchase_behavior', 'unknown')
        price_sens = segments.get('price_sensitivity', 'unknown')

        # Build customer summary
        customer_summary = f"""
Customer Profile:
- Lifetime Value: ${ltv:,.2f}
- Total Orders: {orders}
- Customer Type: {purchase_freq.replace('_', ' ').title()}
- Shopping Style: {shopping_style.replace('_', ' ').title()}
- Price Sensitivity: {price_sens.replace('_', ' ').title()}
- Churn Risk: {churn_level.upper()}
"""

        if churn_level in ['high', 'critical']:
            customer_summary += f"- ⚠️ Churn Risk Factors: {', '.join(churn_factors)}\n"

        # Get ticket details
        subject = ticket.get('subject', 'Customer Inquiry')
        messages = ticket.get('messages', [])
        latest_message = messages[-1].get('body', '') if messages else ''

        # Build compensation guidance
        comp_guidance = ""
        if compensation:
            discount = compensation['discount_percentage']
            tier = compensation['tier']
            reasoning = '\n  - '.join(compensation['reasoning'])

            comp_guidance = f"""
Recommended Compensation:
- Discount: {discount}% off next order
- Customer Tier: {tier.upper()}
- Reasoning:
  - {reasoning}
- Approval: {'Automatically approved' if compensation['automatic_approval'] else 'Requires manager approval'}

"""

        prompt = f"""You are a customer service agent for Linda's Quilting Store, a family-owned business specializing in premium quilting supplies.

{customer_summary}

Customer Issue:
Subject: {subject}

Latest Message:
{latest_message}

{comp_guidance}

Instructions:
1. Write a warm, empathetic response addressing their concern
2. Show you understand their history with the store (reference their loyalty if appropriate)
3. If compensation is recommended, naturally mention the discount offer
4. Be concise but personal (3-4 paragraphs max)
5. Sign off as "The Linda's Team"
6. Match the tone to customer value: VIP/Whale customers get extra personalization

Generate the response now:"""

        return prompt

    async def generate_response(
        self,
        customer_profile: Dict[str, Any],
        ticket: Dict[str, Any],
        issue_severity: str = 'medium'
    ) -> Dict[str, Any]:
        """
        Generate AI response for customer service ticket.

        Args:
            customer_profile: Customer behavioral profile from MCP
            ticket: Gorgias ticket data
            issue_severity: critical, high, medium, low

        Returns:
            Dict with response text, compensation, and metadata
        """
        # Calculate compensation
        ltv = customer_profile.get('business_metrics', {}).get('lifetime_value', 0)
        churn_risk = customer_profile.get('churn_risk', {}).get('risk_level', 'low')

        compensation = self.compensation.calculate_compensation(
            ltv=ltv,
            issue_severity=issue_severity,
            churn_risk=churn_risk
        )

        # Build prompt
        prompt = self._build_prompt(customer_profile, ticket, compensation)

        # Generate response
        if self.model:
            try:
                response = await self.model.generate_content_async(prompt)
                response_text = response.text
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                response_text = self._mock_response(customer_profile, ticket, compensation)
        else:
            logger.info("Using mock response (no API key configured)")
            response_text = self._mock_response(customer_profile, ticket, compensation)

        return {
            'response_text': response_text,
            'compensation': compensation,
            'customer_tier': compensation['tier'],
            'timestamp': datetime.utcnow().isoformat(),
            'model': 'gemini-1.5-flash',
            'cost_estimate_usd': 0.0004  # ~$0.40 per 1K responses
        }

    def _mock_response(
        self,
        customer_profile: Dict[str, Any],
        ticket: Dict[str, Any],
        compensation: Dict[str, Any]
    ) -> str:
        """Generate mock response when API key not available."""
        ltv = customer_profile.get('business_metrics', {}).get('lifetime_value', 0)
        orders = customer_profile.get('business_metrics', {}).get('total_orders', 0)
        discount = compensation['discount_percentage']
        tier = compensation['tier']

        if tier in ['whale', 'vip']:
            greeting = f"Thank you so much for being one of our most valued customers! With {orders} orders and your continued trust in us"
        elif orders > 5:
            greeting = f"We really appreciate your loyalty - {orders} orders means a lot to our small business"
        else:
            greeting = "Thank you for reaching out to us"

        response = f"""Dear valued customer,

{greeting}, we want to make this right immediately.

I completely understand your concern about {ticket.get('subject', 'this issue')}. This isn't the experience we want for you, and we're going to fix it right away.

As a token of our appreciation and to make up for the inconvenience, I'd like to offer you {discount}% off your next order. This discount will be automatically applied to your account.

Please let me know if there's anything else we can do. Your satisfaction is our top priority.

Warmly,
The Linda's Team

---
[MOCK RESPONSE - Configure GEMINI_API_KEY for real AI responses]
"""
        return response


# Singleton instance
_generator = None


def get_ai_generator() -> GeminiResponseGenerator:
    """Get or create AI response generator instance."""
    global _generator
    if _generator is None:
        _generator = GeminiResponseGenerator()
    return _generator
