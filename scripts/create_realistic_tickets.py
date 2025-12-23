"""
Create Realistic Support Tickets from Linda's Customer Data

This script creates authentic support tickets using real customer IDs
from Linda's Shopify database with realistic quilting/fabric scenarios.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import get_db_session
from backend.models import Ticket, TicketMessage
from sqlalchemy import text

# Realistic quilting/fabric support scenarios
TICKET_SCENARIOS = [
    {
        "subject": "Question about fabric shrinkage",
        "message": "Hi! I just received my order of the Kaffe Fassett shot cottons. Should I prewash these before cutting for my quilt? I'm worried about shrinkage. Thanks!",
        "channel": "email",
        "priority": "normal"
    },
    {
        "subject": "Thread color recommendation needed",
        "message": "I'm working on a spring garden quilt with lots of florals. What thread colors would you recommend for quilting? I want it to blend but still show the stitching.",
        "channel": "chat",
        "priority": "low"
    },
    {
        "subject": "Missing item from order",
        "message": "I placed order #1234 last week for a fat quarter bundle, but when it arrived today I'm missing two of the prints. Can you help?",
        "channel": "email",
        "priority": "high"
    },
    {
        "subject": "Batting recommendation for wall hanging",
        "message": "I'm making a 40x60 wall hanging with detailed machine quilting. What batting would you recommend? Should I go with cotton or bamboo?",
        "channel": "chat",
        "priority": "normal"
    },
    {
        "subject": "Fabric width question",
        "message": "Hi! Quick question - are your Moda precuts cut from 42\" or 44\" wide fabric? I'm planning yardage for a pattern.",
        "channel": "email",
        "priority": "low"
    },
    {
        "subject": "Pattern instructions unclear",
        "message": "I bought the Modern Granny Square pattern from your shop but I'm confused about step 7 - the half-square triangle assembly. Can you help clarify?",
        "channel": "email",
        "priority": "normal"
    },
    {
        "subject": "Shipping status inquiry",
        "message": "I ordered some Aurifil thread on Monday and got a shipping notification, but the tracking hasn't updated in 3 days. Is this normal?",
        "channel": "email",
        "priority": "normal"
    },
    {
        "subject": "Fabric collection restock",
        "message": "Will you be restocking the Tilda Lazy Days collection? I need a few more yards to finish my quilt and it's showing out of stock.",
        "channel": "chat",
        "priority": "low"
    },
    {
        "subject": "Return for store credit",
        "message": "I ordered 3 yards of the wrong colorway by mistake. Can I return it for store credit? The fabric is still in the original packaging.",
        "channel": "email",
        "priority": "normal"
    },
    {
        "subject": "Ruler set recommendation",
        "message": "I'm new to quilting and need to buy my first set of rulers. What sizes would you recommend as essentials?",
        "channel": "chat",
        "priority": "low"
    },
    {
        "subject": "Damaged fabric in shipment",
        "message": "My order arrived today but one of the fat quarters has a tear along the fold line. Can I get a replacement sent out?",
        "channel": "email",
        "priority": "high"
    },
    {
        "subject": "Pattern compatibility question",
        "message": "I want to use charm squares for the Disappearing Nine Patch pattern. Will that work or does it need to be cut from yardage?",
        "channel": "chat",
        "priority": "low"
    },
    {
        "subject": "Pre-order delivery date",
        "message": "I pre-ordered the new Ruby Star Society collection. Do you have an estimated ship date yet?",
        "channel": "email",
        "priority": "low"
    },
    {
        "subject": "Wrong item received",
        "message": "I ordered the 1/4\" quilting foot for my Janome but received a walking foot instead. Can you send the correct item?",
        "channel": "email",
        "priority": "high"
    },
    {
        "subject": "Fabric care instructions",
        "message": "I'm using your hand-dyed fabrics for the first time. What's the best way to wash the finished quilt to preserve the colors?",
        "channel": "chat",
        "priority": "normal"
    },
]


async def get_random_customers(count: int = 15):
    """Get random customer IDs from Linda's database."""
    async with get_db_session() as session:
        result = await session.execute(
            text("""
                SELECT customer_id, lifetime_value, total_orders, churn_risk_score
                FROM customer_profiles
                WHERE lifetime_value IS NOT NULL
                ORDER BY RANDOM()
                LIMIT :count
            """),
            {"count": count}
        )
        customers = result.fetchall()
        return [
            {
                "customer_id": str(int(row[0])),  # Convert to string, remove decimal
                "ltv": row[1],
                "orders": row[2],
                "churn_risk": row[3]
            }
            for row in customers
        ]


async def create_realistic_tickets():
    """Create realistic support tickets from real customer data."""
    print("🎫 Creating realistic support tickets from Linda's customer data...\n")

    # Get random real customers
    customers = await get_random_customers(len(TICKET_SCENARIOS))

    if not customers:
        print("❌ No customers found in database!")
        return

    print(f"✅ Found {len(customers)} real customers")

    created_count = 0

    async with get_db_session() as session:
        # Create tickets with scenarios
        for idx, (customer, scenario) in enumerate(zip(customers, TICKET_SCENARIOS)):
            # Calculate created_at (spread over last 7 days)
            days_ago = random.randint(0, 7)
            hours_ago = random.randint(0, 23)
            created_at = datetime.utcnow() - timedelta(days=days_ago, hours=hours_ago)

            # Generate ticket number using database function
            from sqlalchemy import select, func
            result = await session.execute(select(func.generate_ticket_number()))
            ticket_number = result.scalar()

            # Create ticket
            ticket = Ticket(
                ticket_number=ticket_number,
                customer_id=customer["customer_id"],
                channel=scenario["channel"],
                subject=scenario["subject"],
                status="open",
                priority=scenario["priority"],
                created_at=created_at,
                updated_at=created_at
            )
            session.add(ticket)
            await session.flush()  # Get ticket ID

            # Create initial message
            message = TicketMessage(
                ticket_id=ticket.id,
                from_agent=False,
                content=scenario["message"],
                author_name=f"Customer {customer['customer_id'][-4:]}",  # Last 4 digits
                author_email=f"customer{customer['customer_id'][-4:]}@example.com",
                created_at=created_at
            )
            session.add(message)

            created_count += 1

            print(f"  {created_count}. Created ticket from customer {customer['customer_id']}")
            print(f"     Subject: {scenario['subject']}")
            print(f"     Priority: {scenario['priority']}, LTV: ${customer['ltv']:.2f}, Churn: {customer['churn_risk']}")
            print()

        # Commit all tickets
        await session.commit()

    print(f"\n✅ Successfully created {created_count} realistic support tickets!")
    print(f"📊 Distribution:")
    print(f"   - Email: {sum(1 for s in TICKET_SCENARIOS if s['channel'] == 'email')} tickets")
    print(f"   - Chat: {sum(1 for s in TICKET_SCENARIOS if s['channel'] == 'chat')} tickets")
    print(f"   - High Priority: {sum(1 for s in TICKET_SCENARIOS if s['priority'] == 'high')} tickets")
    print(f"   - Normal Priority: {sum(1 for s in TICKET_SCENARIOS if s['priority'] == 'normal')} tickets")
    print(f"   - Low Priority: {sum(1 for s in TICKET_SCENARIOS if s['priority'] == 'low')} tickets")


async def clear_existing_tickets():
    """Delete all existing tickets (for testing)."""
    print("🗑️  Clearing existing tickets...\n")

    async with get_db_session() as session:
        # Delete in order due to foreign keys
        await session.execute(text("DELETE FROM ticket_ai_recommendations"))
        await session.execute(text("DELETE FROM ticket_notes"))
        await session.execute(text("DELETE FROM ticket_messages"))
        await session.execute(text("DELETE FROM tickets"))
        await session.commit()

    print("✅ Cleared all existing tickets\n")


async def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Create realistic support tickets")
    parser.add_argument("--clear", action="store_true", help="Clear existing tickets first")
    args = parser.parse_args()

    if args.clear:
        await clear_existing_tickets()

    await create_realistic_tickets()


if __name__ == "__main__":
    asyncio.run(main())
