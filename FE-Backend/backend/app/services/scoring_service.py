"""
Smart Inbox Ordering: Scoring Service

Calculates intelligent priority scores for tickets based on:
- Customer churn risk (×3.0 weight)
- Customer lifetime value (×2.0 weight)
- Ticket urgency (×1.5 weight)
- Ticket age (older = higher)
- Difficulty estimate (easy wins bubble up)
- Customer sentiment (frustrated = priority boost)
- Topic alerts (agent-specified boost)

Philosophy: Intelligence Replaces Interface
No sorting UI needed - tickets arrive in the right order.
"""
from datetime import datetime
from typing import Optional
from app.core.config import settings


class ScoringService:
    """
    Calculate intelligent priority scores for tickets.

    Higher score = Higher priority in inbox.
    """

    def __init__(self):
        self.churn_weight = settings.scoring_churn_weight
        self.value_weight = settings.scoring_value_weight
        self.urgency_weight = settings.scoring_urgency_weight
        self.topic_alert_boost = settings.topic_alert_boost

    def calculate_ticket_score(
        self,
        ticket: dict,
        customer: dict,
        topic_alerts: Optional[list[str]] = None
    ) -> float:
        """
        Calculate composite score from multiple factors.

        Args:
            ticket: Ticket data including priority, messages, created_at
            customer: Customer data including churn_risk, ltv, etc.
            topic_alerts: Optional list of alert keywords to boost matching tickets

        Returns:
            float: Composite priority score (higher = higher priority)

        Score components:
        1. Churn risk (0-1) × 3.0 = 0-3 points
        2. Customer LTV ($) / 1000 × 2.0 = variable points
        3. Priority urgency × 1.5 = 0-6 points
        4. Wait time penalty = higher for older tickets
        5. Difficulty adjustment = easy wins rise
        6. Sentiment boost = angry customers prioritized
        7. Topic alert boost = +5.0 if matches agent alerts
        """
        # Component 1: Churn risk (weight: 3x)
        churn_component = self._get_churn_component(customer)

        # Component 2: Customer value (weight: 2x)
        value_component = self._get_value_component(customer)

        # Component 3: Urgency (weight: 1.5x)
        urgency_component = self._get_urgency_component(ticket)

        # Component 4: Age penalty (older = higher score)
        age_component = self._get_age_component(ticket)

        # Component 5: Difficulty (easy = higher score)
        difficulty_component = self._get_difficulty_component(ticket)

        # Component 6: Sentiment boost
        sentiment_component = self._get_sentiment_component(ticket)

        # Component 7: Topic alert boost (NEW)
        topic_alert_component = self._get_topic_alert_component(
            ticket, topic_alerts
        )

        # Total score
        total_score = (
            churn_component +
            value_component +
            urgency_component +
            age_component +
            difficulty_component +
            sentiment_component +
            topic_alert_component
        )

        return round(total_score, 2)

    def _get_churn_component(self, customer: dict) -> float:
        """Churn risk: 0-1 scale, weighted by config"""
        churn_risk = customer.get("churn_risk", {})
        if not churn_risk:
            return 0.0

        score = churn_risk.get("churn_risk_score", 0.0)
        return score * self.churn_weight

    def _get_value_component(self, customer: dict) -> float:
        """LTV value: dollars / 1000, weighted by config"""
        business_metrics = customer.get("business_metrics", {})
        if not business_metrics:
            return 0.0

        ltv = business_metrics.get("lifetime_value", 0.0)
        return (ltv / 1000.0) * self.value_weight

    def _get_urgency_component(self, ticket: dict) -> float:
        """Priority level: urgent=4, high=3, normal=1, low=0.5, weighted by config"""
        urgency_weights = {
            'urgent': 4.0,
            'high': 3.0,
            'normal': 1.0,
            'low': 0.5
        }
        priority = ticket.get("priority", "normal")
        base_urgency = urgency_weights.get(priority, 1.0)
        return base_urgency * self.urgency_weight

    def _get_age_component(self, ticket: dict) -> float:
        """
        Age penalty: 1 / hours_waiting (older = higher)

        Ensures old tickets don't get stuck.
        """
        created_at = ticket.get("created_at")
        if not created_at:
            return 0.0

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

        hours_waiting = (datetime.utcnow() - created_at).total_seconds() / 3600
        hours_waiting = max(hours_waiting, 0.1)  # Avoid division by zero

        return 1.0 / hours_waiting

    def _get_difficulty_component(self, ticket: dict) -> float:
        """
        Difficulty estimate: easy wins bubble up

        Simple questions = +1.0 (easy win, prioritize)
        Complex issues = -1.5 (harder, deprioritize slightly)

        Phase 1: Keyword-based
        Phase 2: ML-based difficulty prediction
        """
        messages = ticket.get("messages", [])
        if not messages:
            return 0.0

        # Get last customer message
        last_message = messages[-1].get("content", "").lower()

        # Simple keywords (tracking, status, when, where)
        simple_keywords = ['tracking', 'status', 'when', 'where is', 'can you']
        if any(kw in last_message for kw in simple_keywords):
            return 1.0  # Easy win

        # Complex keywords (refund, broken, wrong, damaged)
        complex_keywords = ['refund', 'broken', 'wrong', 'damaged', 'defective']
        if any(kw in last_message for kw in complex_keywords):
            return -1.5  # Harder issue

        return 0.0  # Neutral

    def _get_sentiment_component(self, ticket: dict) -> float:
        """
        Sentiment: negative = +2.0 boost (frustrated customers prioritized)

        Prevents churn by handling upset customers quickly.
        """
        sentiment = ticket.get("customer_sentiment")
        if sentiment is None:
            return 0.0

        # Negative sentiment (< 0.3) gets priority boost
        if sentiment < 0.3:
            return 2.0

        return 0.0

    def _get_topic_alert_component(
        self,
        ticket: dict,
        topic_alerts: Optional[list[str]] = None
    ) -> float:
        """
        Topic alert boost: +5.0 if ticket matches agent-specified topics

        Allows agents to influence sorting for emerging issues:
        - Chargebacks during fraud wave
        - Wrong address during holiday shipping
        - Vendor delays during stockouts

        Philosophy: Temporary intent-setting, not permanent manual sorting
        """
        if not topic_alerts:
            return 0.0

        # Check ticket content for alert matches
        messages = ticket.get("messages", [])
        if not messages:
            return 0.0

        # Combine all message content
        full_content = " ".join(
            msg.get("content", "").lower() for msg in messages
        )

        # Check if any alert topic appears in content
        for alert in topic_alerts:
            if alert.lower() in full_content:
                return self.topic_alert_boost

        return 0.0

    def get_scoring_breakdown(
        self,
        ticket: dict,
        customer: dict,
        topic_alerts: Optional[list[str]] = None
    ) -> dict:
        """
        Return detailed breakdown of score for debugging/explanation.

        Useful for:
        - Understanding why tickets are ordered
        - Tuning algorithm weights
        - Explaining to users
        """
        return {
            'total_score': self.calculate_ticket_score(
                ticket, customer, topic_alerts
            ),
            'components': {
                'churn_risk': self._get_churn_component(customer),
                'customer_value': self._get_value_component(customer),
                'urgency': self._get_urgency_component(ticket),
                'age': self._get_age_component(ticket),
                'difficulty': self._get_difficulty_component(ticket),
                'sentiment': self._get_sentiment_component(ticket),
                'topic_alert': self._get_topic_alert_component(
                    ticket, topic_alerts
                )
            },
            'customer': {
                'ltv': customer.get("business_metrics", {}).get(
                    "lifetime_value", 0
                ),
                'churn_risk': customer.get("churn_risk", {}).get(
                    "churn_risk_score", 0
                )
            },
            'ticket': {
                'priority': ticket.get("priority", "normal"),
                'age_hours': self._calculate_age_hours(ticket)
            },
            'weights': {
                'churn_weight': self.churn_weight,
                'value_weight': self.value_weight,
                'urgency_weight': self.urgency_weight,
                'topic_alert_boost': self.topic_alert_boost
            }
        }

    def _calculate_age_hours(self, ticket: dict) -> float:
        """Calculate ticket age in hours."""
        created_at = ticket.get("created_at")
        if not created_at:
            return 0.0

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

        return (datetime.utcnow() - created_at).total_seconds() / 3600
