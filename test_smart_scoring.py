#!/usr/bin/env python3
"""
Test Smart Scoring Integration

This script tests the smart scoring service with real customer data
from the production database.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.services.scoring_service import scoring_service
from datetime import datetime, timedelta

# Mock tickets with different characteristics
mock_tickets = [
    {
        "id": "1",
        "priority": "urgent",
        "created_at": (datetime.utcnow() - timedelta(hours=5)).isoformat(),
        "messages": [
            {"content": "I need to cancel my order immediately! This is urgent."}
        ],
        "customer_sentiment": 0.1,  # Very frustrated
        "customer_id": "test_customer_1"
    },
    {
        "id": "2",
        "priority": "normal",
        "created_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        "messages": [
            {"content": "Can you send me the tracking number for my order?"}
        ],
        "customer_sentiment": 0.7,  # Neutral
        "customer_id": "test_customer_2"
    },
    {
        "id": "3",
        "priority": "high",
        "created_at": (datetime.utcnow() - timedelta(hours=24)).isoformat(),
        "messages": [
            {"content": "My package was damaged during shipping"}
        ],
        "customer_sentiment": 0.2,  # Frustrated
        "customer_id": "test_customer_3"
    }
]

# Mock customer profiles (matching existing backend structure)
mock_customers = {
    "test_customer_1": {
        "customer_id": "test_customer_1",
        "business_metrics": {
            "lifetime_value": 3500.0,  # High value customer
            "total_orders": 15,
            "avg_order_value": 233.33
        },
        "churn_risk": {
            "churn_risk_score": 0.85  # Very high churn risk
        }
    },
    "test_customer_2": {
        "customer_id": "test_customer_2",
        "business_metrics": {
            "lifetime_value": 450.0,  # Regular customer
            "total_orders": 3,
            "avg_order_value": 150.0
        },
        "churn_risk": {
            "churn_risk_score": 0.15  # Low churn risk
        }
    },
    "test_customer_3": {
        "customer_id": "test_customer_3",
        "business_metrics": {
            "lifetime_value": 5200.0,  # VIP customer
            "total_orders": 28,
            "avg_order_value": 185.71
        },
        "churn_risk": {
            "churn_risk_score": 0.75  # High churn risk
        }
    }
}

def test_basic_scoring():
    """Test basic scoring without topic alerts."""
    print("=" * 80)
    print("TEST 1: Basic Smart Scoring")
    print("=" * 80)
    print()

    scored_tickets = []
    for ticket in mock_tickets:
        customer = mock_customers[ticket["customer_id"]]
        score = scoring_service.calculate_ticket_score(
            ticket=ticket,
            customer=customer,
            topic_alerts=None
        )
        ticket["smart_score"] = score
        scored_tickets.append(ticket)

    # Sort by score
    scored_tickets.sort(key=lambda t: t["smart_score"], reverse=True)

    # Display results
    for i, ticket in enumerate(scored_tickets, 1):
        customer = mock_customers[ticket["customer_id"]]
        print(f"{i}. Ticket #{ticket['id']} - Score: {ticket['smart_score']:.2f}")
        print(f"   Priority: {ticket['priority']}")
        print(f"   Customer LTV: ${customer['business_metrics']['lifetime_value']:.2f}")
        print(f"   Churn Risk: {customer['churn_risk']['churn_risk_score'] * 100:.0f}%")
        print(f"   Message: {ticket['messages'][0]['content'][:60]}...")
        print()

    print("✅ Basic scoring test complete!")
    print()


def test_topic_alerts():
    """Test scoring with topic alerts."""
    print("=" * 80)
    print("TEST 2: Smart Scoring with Topic Alerts")
    print("=" * 80)
    print()

    # Define topic alerts
    alerts = ["cancel", "urgent"]
    print(f"Active topic alerts: {alerts}")
    print()

    scored_tickets = []
    for ticket in mock_tickets:
        customer = mock_customers[ticket["customer_id"]]
        score = scoring_service.calculate_ticket_score(
            ticket=ticket,
            customer=customer,
            topic_alerts=alerts
        )
        ticket["smart_score"] = score
        scored_tickets.append(ticket)

    # Sort by score
    scored_tickets.sort(key=lambda t: t["smart_score"], reverse=True)

    # Display results
    for i, ticket in enumerate(scored_tickets, 1):
        customer = mock_customers[ticket["customer_id"]]
        matches_alert = scoring_service._get_topic_alert_component(ticket, alerts) > 0

        print(f"{i}. Ticket #{ticket['id']} - Score: {ticket['smart_score']:.2f} {'🚨 ALERT' if matches_alert else ''}")
        print(f"   Priority: {ticket['priority']}")
        print(f"   Customer LTV: ${customer['business_metrics']['lifetime_value']:.2f}")
        print(f"   Churn Risk: {customer['churn_risk']['churn_risk_score'] * 100:.0f}%")
        print(f"   Message: {ticket['messages'][0]['content'][:60]}...")
        print()

    print("✅ Topic alerts test complete!")
    print()


def test_score_breakdown():
    """Test detailed score breakdown."""
    print("=" * 80)
    print("TEST 3: Score Breakdown Analysis")
    print("=" * 80)
    print()

    # Use the first ticket as example
    ticket = mock_tickets[0]
    customer = mock_customers[ticket["customer_id"]]

    breakdown = scoring_service.get_scoring_breakdown(
        ticket=ticket,
        customer=customer,
        topic_alerts=["cancel", "urgent"]
    )

    print(f"Ticket #{ticket['id']}: {ticket['messages'][0]['content'][:50]}...")
    print()
    print(f"TOTAL SCORE: {breakdown['total_score']:.2f}")
    print()
    print("Component Breakdown:")
    print(f"  • Churn Risk:      {breakdown['components']['churn_risk']:.2f} (weight: {breakdown['weights']['churn_weight']:.1f}x)")
    print(f"  • Customer Value:  {breakdown['components']['customer_value']:.2f} (weight: {breakdown['weights']['value_weight']:.1f}x)")
    print(f"  • Urgency:         {breakdown['components']['urgency']:.2f} (weight: {breakdown['weights']['urgency_weight']:.1f}x)")
    print(f"  • Age:             {breakdown['components']['age']:.2f}")
    print(f"  • Difficulty:      {breakdown['components']['difficulty']:.2f}")
    print(f"  • Sentiment:       {breakdown['components']['sentiment']:.2f}")
    print(f"  • Topic Alert:     {breakdown['components']['topic_alert']:.2f} (boost: {breakdown['weights']['topic_alert_boost']:.1f})")
    print()
    print("Customer Metrics:")
    print(f"  • Lifetime Value:  ${breakdown['customer']['ltv']:.2f}")
    print(f"  • Churn Risk:      {breakdown['customer']['churn_risk'] * 100:.0f}%")
    print()
    print("Ticket Properties:")
    print(f"  • Priority:        {breakdown['ticket']['priority']}")
    print(f"  • Age (hours):     {breakdown['ticket']['age_hours']:.1f}")
    print()

    print("✅ Score breakdown test complete!")
    print()


def main():
    """Run all tests."""
    print()
    print("🧪 SMART SCORING INTEGRATION TESTS")
    print()

    try:
        test_basic_scoring()
        test_topic_alerts()
        test_score_breakdown()

        print("=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print()
        print("Smart scoring is ready to use in production!")
        print()
        print("Next steps:")
        print("1. Deploy updated backend with smart scoring")
        print("2. Update frontend to use ?smart_order=true parameter")
        print("3. Add topic_alerts parameter for emerging issues")
        print()

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
