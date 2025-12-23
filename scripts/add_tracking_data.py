"""
Add fake but realistic tracking data to tickets.

This allows the AI to reference actual order/tracking information
instead of hallucinating it.
"""
import asyncio
import os
from datetime import datetime, timedelta
from sqlalchemy import text
from backend.core.database import AsyncSessionLocal

# Realistic tracking numbers and carriers
TRACKING_DATA = {
    "T-001": {  # Question about fabric shrinkage
        "order_number": "L-10234",
        "order_date": "2025-11-25",
        "tracking_number": "9400111899562634567890",
        "tracking_url": "https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111899562634567890",
        "carrier": "USPS",
        "carrier_status": "In Transit",
        "last_update": "2025-11-28",
        "estimated_delivery": "2025-12-03",
        "items": [
            {"name": "Kaffe Fassett Shot Cottons Collection", "quantity": 2, "sku": "KF-SC-001"}
        ]
    },
    "T-002": {  # Thread color recommendation
        "order_number": "L-10156",
        "order_date": "2025-11-20",
        "tracking_number": "1Z999AA10123456784",
        "tracking_url": "https://www.ups.com/track?tracknum=1Z999AA10123456784",
        "carrier": "UPS",
        "carrier_status": "Delivered",
        "last_update": "2025-11-23",
        "delivered_date": "2025-11-23",
        "items": [
            {"name": "Aurifil 50wt Thread Set", "quantity": 1, "sku": "AUR-50-SET"}
        ]
    },
    "T-004": {  # Batting recommendation
        "order_number": "L-10089",
        "order_date": "2025-11-15",
        "tracking_number": "9400111899562634567891",
        "tracking_url": "https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111899562634567891",
        "carrier": "USPS",
        "carrier_status": "Delivered",
        "last_update": "2025-11-20",
        "delivered_date": "2025-11-20",
        "items": [
            {"name": "Warm & Natural Cotton Batting", "quantity": 1, "sku": "WN-BAT-QN"}
        ]
    },
    "T-007": {  # Shipping status inquiry
        "order_number": "L-10245",
        "order_date": "2025-11-27",
        "tracking_number": "9400111899562634567892",
        "tracking_url": "https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111899562634567892",
        "carrier": "USPS",
        "carrier_status": "Label Created, Not Yet in System",
        "last_update": "2025-11-27",
        "estimated_delivery": "2025-12-05",
        "items": [
            {"name": "Aurifil 50wt Thread", "quantity": 3, "sku": "AUR-50-2024"}
        ]
    },
    "T-008": {  # Fabric collection restock
        "order_number": "L-10198",
        "order_date": "2025-11-22",
        "tracking_number": None,  # Pre-order, not shipped yet
        "carrier": None,
        "carrier_status": "Pre-Order - Not Yet Shipped",
        "estimated_ship_date": "2025-12-10",
        "items": [
            {"name": "Tula Pink Daydreamer Fat Quarter Bundle", "quantity": 1, "sku": "TP-DD-FQ"}
        ]
    },
    "T-009": {  # Return for store credit
        "order_number": "L-10067",
        "order_date": "2025-11-10",
        "tracking_number": "1Z999AA10123456785",
        "tracking_url": "https://www.ups.com/track?tracknum=1Z999AA10123456785",
        "carrier": "UPS",
        "carrier_status": "Delivered",
        "last_update": "2025-11-15",
        "delivered_date": "2025-11-15",
        "return_initiated": True,
        "return_label_created": "2025-11-28",
        "items": [
            {"name": "Moda Bella Solids Charm Pack", "quantity": 2, "sku": "MOD-BS-CP"}
        ]
    },
    "T-011": {  # Damaged fabric in shipment
        "order_number": "L-10234",
        "order_date": "2025-11-25",
        "tracking_number": "9400111899562634567893",
        "tracking_url": "https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111899562634567893",
        "carrier": "USPS",
        "carrier_status": "Delivered",
        "last_update": "2025-11-29",
        "delivered_date": "2025-11-29",
        "replacement_order": "L-10299",
        "replacement_tracking": "9400111899562634567894",
        "replacement_status": "Shipped",
        "items": [
            {"name": "Riley Blake Confetti Cottons", "quantity": 3, "sku": "RB-CC-001"}
        ]
    },
    "T-013": {  # Pre-order delivery date
        "order_number": "L-10267",
        "order_date": "2025-11-26",
        "tracking_number": None,
        "carrier": None,
        "carrier_status": "Pre-Order - Awaiting Stock",
        "estimated_ship_date": "2025-12-15",
        "estimated_delivery": "2025-12-20",
        "items": [
            {"name": "Kaffe Fassett Collective 2024 Preview", "quantity": 1, "sku": "KF-2024-PRE"}
        ]
    },
    "T-014": {  # Wrong item received
        "order_number": "L-10256",
        "order_date": "2025-11-26",
        "tracking_number": "1Z999AA10123456786",
        "tracking_url": "https://www.ups.com/track?tracknum=1Z999AA10123456786",
        "carrier": "UPS",
        "carrier_status": "Delivered",
        "last_update": "2025-11-30",
        "delivered_date": "2025-11-30",
        "return_label_created": "2025-12-01",
        "replacement_order": "L-10301",
        "replacement_tracking": "9400111899562634567895",
        "replacement_status": "Label Created",
        "items": [
            {"name": "Aurifil 40wt Thread Set (incorrect)", "quantity": 1, "sku": "AUR-40-SET"},
            {"name": "Aurifil 50wt Thread Set (correct, replacement)", "quantity": 1, "sku": "AUR-50-SET"}
        ]
    },
    "T-015": {  # Fabric care instructions
        "order_number": "L-10112",
        "order_date": "2025-11-18",
        "tracking_number": "9400111899562634567896",
        "tracking_url": "https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111899562634567896",
        "carrier": "USPS",
        "carrier_status": "Delivered",
        "last_update": "2025-11-22",
        "delivered_date": "2025-11-22",
        "items": [
            {"name": "Liberty of London Tana Lawn", "quantity": 2, "sku": "LOL-TL-001"}
        ]
    }
}


async def add_tracking_to_tickets():
    """Add tracking data to tickets' custom_fields."""
    import json

    async with AsyncSessionLocal() as session:
        for ticket_number, tracking_data in TRACKING_DATA.items():
            try:
                # Convert to JSON string for PostgreSQL
                tracking_json = json.dumps(tracking_data)

                # Update the ticket's custom_fields with tracking data
                result = await session.execute(
                    text("""
                        UPDATE support_app.tickets
                        SET custom_fields = :tracking_data::jsonb,
                            updated_at = NOW()
                        WHERE ticket_number = :ticket_number
                        RETURNING ticket_number, customer_id, subject
                    """),
                    {
                        "ticket_number": ticket_number,
                        "tracking_data": tracking_json
                    }
                )

                updated = result.fetchone()
                if updated:
                    print(f"✅ Updated {updated[0]}: {updated[2]}")
                    print(f"   Order: {tracking_data.get('order_number')}, Tracking: {tracking_data.get('tracking_number', 'N/A')}")
                else:
                    print(f"⚠️  Ticket {ticket_number} not found")

            except Exception as e:
                print(f"❌ Error updating {ticket_number}: {e}")

        await session.commit()
        print(f"\n✅ Updated {len(TRACKING_DATA)} tickets with tracking data")


async def verify_tracking_data():
    """Verify the tracking data was added correctly."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT
                    ticket_number,
                    subject,
                    custom_fields->>'order_number' as order_number,
                    custom_fields->>'tracking_number' as tracking_number,
                    custom_fields->>'carrier_status' as status
                FROM support_app.tickets
                WHERE ticket_number IN :ticket_numbers
                ORDER BY ticket_number
            """),
            {"ticket_numbers": tuple(TRACKING_DATA.keys())}
        )

        print("\n📋 Verification:")
        print("=" * 80)
        for row in result:
            print(f"{row[0]}: {row[1][:40]}")
            print(f"   Order: {row[2]}, Tracking: {row[3]}")
            print(f"   Status: {row[4]}")
            print()


async def main():
    """Main function to run both operations."""
    print("Adding tracking data to tickets...\n")
    await add_tracking_to_tickets()
    await verify_tracking_data()


if __name__ == "__main__":
    asyncio.run(main())
