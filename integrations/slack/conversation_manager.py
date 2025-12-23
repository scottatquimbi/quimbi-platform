"""
Conversation Manager for Slack Bot

Handles multi-turn conversations, clarifying questions, and context tracking.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manage conversational state and clarifications for Slack interactions."""

    def __init__(self):
        """Initialize conversation manager with in-memory state."""
        # Store conversation context: {user_id: {last_query, pending_clarification, context, timestamp}}
        self.conversations = {}
        self.context_timeout = timedelta(minutes=10)

    def needs_clarification(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Determine if a query is ambiguous and needs clarification.

        Args:
            query: User's natural language query

        Returns:
            Clarification prompt dict if needed, None otherwise
        """
        query_lower = query.lower()

        # Detect ambiguous "successful customer" questions
        if any(phrase in query_lower for phrase in [
            'succeed', 'successful', 'best customer', 'ideal customer',
            'type of person', 'kind of customer', 'who does well'
        ]):
            return {
                "question": query,
                "clarification_needed": True,
                "options": [
                    {
                        "label": "Revenue",
                        "value": "revenue",
                        "description": "Customers who spend the most money"
                    },
                    {
                        "label": "Longevity",
                        "value": "longevity",
                        "description": "Customers who stick around longest"
                    },
                    {
                        "label": "Engagement",
                        "value": "engagement",
                        "description": "Customers who shop most frequently"
                    },
                    {
                        "label": "Loyalty",
                        "value": "loyalty",
                        "description": "Customers with lowest churn risk"
                    },
                    {
                        "label": "All of the above",
                        "value": "comprehensive",
                        "description": "Show me all success metrics"
                    }
                ],
                "prompt": "What type of 'success' are you interested in?"
            }

        # Detect ambiguous "best" or "top" questions without context
        if any(phrase in query_lower for phrase in [
            'best ', 'top ', 'highest'
        ]) and not any(metric in query_lower for metric in [
            'revenue', 'ltv', 'churn', 'value', 'spend', 'risk', 'loyal',
            'repeat', 'purchase', 'order', 'buy', 'frequen', 'engagement'
        ]):
            return {
                "question": query,
                "clarification_needed": True,
                "options": [
                    {
                        "label": "By Revenue (LTV)",
                        "value": "ltv",
                        "description": "Highest lifetime value customers"
                    },
                    {
                        "label": "By Order Frequency",
                        "value": "frequency",
                        "description": "Most frequent shoppers"
                    },
                    {
                        "label": "By Retention",
                        "value": "retention",
                        "description": "Most loyal (low churn) customers"
                    },
                    {
                        "label": "By Segment Size",
                        "value": "population",
                        "description": "Largest customer groups"
                    }
                ],
                "prompt": "What metric should I use to rank them?"
            }

        return None

    def store_context(self, user_id: str, query: str, context: Dict[str, Any]):
        """
        Store conversation context for follow-up questions.

        Args:
            user_id: Slack user ID
            query: Original query
            context: Additional context to store
        """
        self.conversations[user_id] = {
            "last_query": query,
            "context": context,
            "timestamp": datetime.now()
        }

    def get_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve conversation context if still valid.

        Args:
            user_id: Slack user ID

        Returns:
            Context dict if exists and not expired, None otherwise
        """
        if user_id not in self.conversations:
            return None

        conv = self.conversations[user_id]

        # Check if context is expired
        if datetime.now() - conv['timestamp'] > self.context_timeout:
            del self.conversations[user_id]
            return None

        return conv

    def clear_context(self, user_id: str):
        """Clear conversation context for user."""
        if user_id in self.conversations:
            del self.conversations[user_id]

    def format_clarification(self, clarification: Dict[str, Any]) -> str:
        """
        Format clarification question for Slack.

        Args:
            clarification: Clarification dict from needs_clarification()

        Returns:
            Formatted Slack message text
        """
        prompt = clarification['prompt']
        options = clarification['options']

        message = f"*{prompt}*\n\n"

        for i, option in enumerate(options, 1):
            message += f"{i}. *{option['label']}* - {option['description']}\n"

        message += "\nReply with the number or name of your choice."

        return message

    def parse_clarification_response(self, response: str, clarification: Dict[str, Any]) -> Optional[str]:
        """
        Parse user's response to clarification question.

        Args:
            response: User's text response
            clarification: Original clarification dict

        Returns:
            Selected option value, or None if can't parse
        """
        response_lower = response.strip().lower()
        options = clarification['options']

        # Try to match by number
        if response_lower.isdigit():
            idx = int(response_lower) - 1
            if 0 <= idx < len(options):
                return options[idx]['value']

        # Try to match by label or value
        for option in options:
            if (response_lower == option['label'].lower() or
                response_lower == option['value'].lower() or
                option['value'] in response_lower):
                return option['value']

        return None

    def describe_archetype_behaviors(self, archetype: Dict[str, Any]) -> str:
        """
        Convert archetype data into natural language behavior description.

        Args:
            archetype: Archetype data with dominant_segments

        Returns:
            Natural language description of customer behaviors
        """
        segments = archetype.get('dominant_segments', {})

        descriptions = []

        # Purchase value
        value_map = {
            'premium': 'high spenders',
            'high_tier': 'above-average spenders',
            'mid_tier': 'moderate spenders',
            'low_tier': 'budget-conscious shoppers',
            'bargain': 'deal seekers'
        }
        if segments.get('purchase_value') in value_map:
            descriptions.append(value_map[segments['purchase_value']])

        # Shopping frequency
        freq_map = {
            'power_buyer': 'shop very frequently',
            'regular': 'shop regularly',
            'occasional': 'shop occasionally',
            'rare': 'shop infrequently'
        }
        if segments.get('purchase_frequency') in freq_map:
            descriptions.append(freq_map[segments['purchase_frequency']])

        # Shopping cadence
        cadence_map = {
            'seasonal': 'primarily during seasonal events',
            'holiday': 'mainly around holidays',
            'year_round': 'consistently throughout the year',
            'weekday': 'prefer shopping on weekdays',
            'weekend': 'prefer weekend shopping'
        }
        if segments.get('shopping_cadence') in cadence_map:
            descriptions.append(cadence_map[segments['shopping_cadence']])

        # Return behavior
        return_map = {
            'frequent_returner': 'return items often',
            'occasional_returner': 'return items occasionally',
            'careful_buyer': 'rarely return purchases'
        }
        if segments.get('return_behavior') in return_map:
            descriptions.append(return_map[segments['return_behavior']])

        # Category affinity
        category_map = {
            'category_loyal': 'stick to favorite categories',
            'multi_category': 'explore multiple categories',
            'specialized': 'focus on specific product types'
        }
        if segments.get('category_affinity') in category_map:
            descriptions.append(category_map[segments['category_affinity']])

        # Price sensitivity
        price_map = {
            'deal_hunter': 'wait for sales and discounts',
            'price_conscious': 'compare prices carefully',
            'value_seeker': 'balance quality and price',
            'premium_buyer': 'willing to pay full price for quality'
        }
        if segments.get('price_sensitivity') in price_map:
            descriptions.append(price_map[segments['price_sensitivity']])

        # Loyalty/maturity
        maturity_map = {
            'long_term': 'been customers for years',
            'established': 'well-established relationship',
            'developing': 'building their shopping habits',
            'new': 'recently joined'
        }
        if segments.get('shopping_maturity') in maturity_map:
            descriptions.append(maturity_map[segments['shopping_maturity']])

        if not descriptions:
            return "customers with diverse shopping behaviors"

        # Join descriptions naturally
        if len(descriptions) == 1:
            return descriptions[0]
        elif len(descriptions) == 2:
            return f"{descriptions[0]} and {descriptions[1]}"
        else:
            return f"{', '.join(descriptions[:-1])}, and {descriptions[-1]}"
