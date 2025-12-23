#!/usr/bin/env python3
"""Generate AI recommendations for all open tickets."""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from backend.core.database import get_db_session
from backend.models import Ticket


async def get_open_tickets():
    """Get all open ticket IDs."""
    async with get_db_session() as db:
        result = await db.execute(
            select(Ticket.id, Ticket.ticket_number)
            .where(Ticket.status == "open")
            .order_by(Ticket.created_at.desc())
        )
        return result.fetchall()


async def main():
    """Generate recommendations for all tickets via API calls."""
    import aiohttp

    base_url = os.getenv("API_URL", "https://ecommerce-backend-staging-a14c.up.railway.app")
    api_key = os.getenv("ADMIN_KEY", "e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31")

    tickets = await get_open_tickets()
    print(f"Found {len(tickets)} open tickets")

    async with aiohttp.ClientSession() as session:
        for ticket_id, ticket_number in tickets:
            print(f"Generating recommendation for {ticket_number}...", end=" ")

            # Call the AI recommendation endpoint which generates recommendations
            url = f"{base_url}/api/ai/tickets/{ticket_id}/recommendation"
            headers = {"X-API-Key": api_key}

            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        priority = data.get("priority")
                        actions = data.get("actions", [])
                        if priority:
                            print(f"✅ Priority: {priority}, Actions: {len(actions)}")
                        else:
                            print("⚠️ No recommendation generated")
                    else:
                        text = await response.text()
                        print(f"❌ Error {response.status}: {text[:100]}")
            except Exception as e:
                print(f"❌ Exception: {e}")

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
