#!/usr/bin/env python3
"""
Simulate Betty Bates ticket processing without posting to Gorgias.

Shows what the bot would respond with for her question:
"I am trying to find out where I bought my Tula pink iron. Can you check your inventory and see if I bought it from you. About year ago."
"""

import os
import sys
import asyncio
import httpx
from anthropic import Anthropic

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.gorgias_ai_assistant import GorgiasAIAssistant


async def simulate_betty_bates_ticket():
    """Simulate processing Betty Bates' ticket without posting to Gorgias."""

    print("=" * 80)
    print("BETTY BATES TICKET SIMULATION")
    print("=" * 80)
    print()

    # Customer question
    customer_message = (
        "Hi Linda, this is Betty Bates. I am trying to find out where I bought my "
        "Tula pink iron. Can you check your inventory and see if I bought it from you. "
        "About year ago."
    )

    print("📧 CUSTOMER MESSAGE:")
    print(f"From: Betty Bates (gramabates@gmail.com)")
    print(f"Message: {customer_message}")
    print()

    # Step 1: Look up customer by email
    print("🔍 STEP 1: Looking up customer by email...")
    analytics_api_url = "https://ecommerce-backend-staging-a14c.up.railway.app"
    api_key = os.getenv("ADMIN_KEY", "e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Search for customer
        search_url = f"{analytics_api_url}/api/mcp/customer/search"
        response = await client.get(
            search_url,
            params={"email": "gramabates@gmail.com"},
            headers={"X-API-Key": api_key}
        )

        if response.status_code == 404:
            print("❌ Customer not found in database")
            print("   This means Betty hasn't ordered from Linda's before")
            print()
            print("🤖 BOT RESPONSE:")
            print("-" * 80)
            print("""Hi Betty,

I checked our customer records and don't see any previous orders associated with
your email address (gramabates@gmail.com). This suggests you may have purchased
your Tula Pink iron from another retailer.

If you've ordered from us before but used a different email address, please let me
know and I can check under that email instead.

Is there anything else I can help you with today?

Best regards,
Linda's Customer Service""")
            print("-" * 80)
            return

        customer_data = response.json()
        customer_id = customer_data["customer_id"]

        print(f"✅ Found customer: {customer_data['name']}")
        print(f"   Customer ID: {customer_id}")
        print()

        # Step 2: Fetch order history with search for "Tula Pink" + "iron"
        print("🔍 STEP 2: Searching order history for 'tula pink' and 'iron'...")
        print("   Timeframe: Last 18 months")

        orders_url = f"{analytics_api_url}/api/mcp/customer/{customer_id}/orders"
        response = await client.get(
            orders_url,
            params={
                "search_terms": "tula pink,iron",
                "months_ago": 18
            },
            headers={"X-API-Key": api_key}
        )

        if response.status_code != 200:
            print(f"❌ Error fetching order history: {response.status_code}")
            print(f"   {response.text}")
            return

        order_data = response.json()
        orders = order_data.get("orders", [])

        print(f"   Found {len(orders)} matching orders")
        print()

        # Step 3: Generate response based on results
        if orders:
            print("✅ FOUND MATCHING PRODUCTS!")
            print()
            print("📦 ORDERS CONTAINING 'TULA PINK' or 'IRON':")
            print("-" * 80)

            for order in orders:
                from datetime import datetime
                order_date = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
                formatted_date = order_date.strftime("%B %d, %Y")

                print(f"\nOrder: {order['order_id']}")
                print(f"Date: {formatted_date}")
                print(f"Total: ${order['total']} {order['currency']}")
                print(f"Products:")

                for product in order["products"]:
                    print(f"  • {product['title']} (Qty: {product['quantity']})")
                    print(f"    Vendor: {product['vendor']}")
                    print(f"    Type: {product['product_type']}")

            print()
            print("🤖 BOT RESPONSE:")
            print("-" * 80)

            # Get first matching order for response
            first_order = orders[0]
            order_date = datetime.fromisoformat(first_order["created_at"].replace("Z", "+00:00"))
            formatted_date = order_date.strftime("%B %d, %Y")

            # Find the specific product that matches
            matching_product = first_order["products"][0]

            print(f"""Hi Betty,

Great news! Yes, you did purchase from us!

📦 Order Details:
Order Number: {first_order['order_id']}
Order Date: {formatted_date}
Product: {matching_product['title']}
Vendor: {matching_product['vendor']}
Order Total: ${first_order['total']}

{f"You also ordered {len(first_order['products']) - 1} other item(s) in this order." if len(first_order['products']) > 1 else ""}

Is there anything else I can help you with regarding this order?

Best regards,
Linda's Customer Service""")

        else:
            print("❌ NO MATCHING PRODUCTS FOUND")
            print()
            print("🔍 CHECKING ALL ORDERS (without search filter)...")

            # Get all orders to show what they DID buy
            response = await client.get(
                orders_url,
                params={"months_ago": 18, "limit": 10},
                headers={"X-API-Key": api_key}
            )

            all_orders = response.json().get("orders", [])

            print(f"   Customer has {len(all_orders)} total orders in last 18 months")
            print()
            print("🤖 BOT RESPONSE:")
            print("-" * 80)

            if all_orders:
                print(f"""Hi Betty,

I've checked your order history with us going back 18 months, and I don't see a
Tula Pink iron in your purchases from Linda's.

However, I do see you've ordered from us before! Your recent orders include:""")

                for i, order in enumerate(all_orders[:3], 1):
                    from datetime import datetime
                    order_date = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
                    formatted_date = order_date.strftime("%B %d, %Y")

                    product_summary = ", ".join([p["product_type"] for p in order["products"][:2]])
                    print(f"\n{i}. {formatted_date}: {product_summary} (${order['total']})")

                print("""

You may have purchased the Tula Pink iron from:
• Tula Pink's website directly
• Another quilting retailer
• A local quilt shop

Is there anything else I can help you find?

Best regards,
Linda's Customer Service""")
            else:
                print("""Hi Betty,

I've checked your order history with us going back 18 months, and I don't see a
Tula Pink iron in your purchases from Linda's.

It's possible you may have purchased it from another retailer, or it was more than
18 months ago. If you'd like me to check further back, please let me know!

Is there anything else I can help you with today?

Best regards,
Linda's Customer Service""")

        print("-" * 80)


if __name__ == "__main__":
    asyncio.run(simulate_betty_bates_ticket())
