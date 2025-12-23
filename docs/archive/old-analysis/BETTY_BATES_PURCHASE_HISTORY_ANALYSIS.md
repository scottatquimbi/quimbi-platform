# Betty Bates Purchase History Analysis

**Date:** 2025-11-09
**Customer:** Betty Bates (gramabates@gmail.com)
**Question:** "I am trying to find out where I bought my Tula pink iron. Can you check your inventory and see if I bought it from you. About year ago."

---

## Customer Question

Betty Bates received a rewards email showing she has accumulated **452 Corey's Cash** points and recently placed an order earning **427 points**. She's asking:

> "Hi Linda, this is Betty Bates. I am trying to find out where I bought my Tula pink iron. Can you check your inventory and see if I bought it from you. About year ago."

**Key Details:**
- Product: **Tula Pink iron** (quilting/crafting iron)
- Timeframe: **Approximately 1 year ago** (around November 2023 - November 2024)
- Uncertainty: Betty isn't sure if she bought it from Linda's or another retailer

---

## How to Retrieve Purchase History

The system can retrieve Betty's purchase history through **three data sources**:

### Option 1: Gorgias Webhook Integration Data (FASTEST ✅)

When a ticket comes in from Gorgias, the webhook includes Shopify integration data if the customer is linked.

**Expected Webhook Structure:**
```json
{
  "id": 123456,
  "subject": "...",
  "customer": {
    "id": 524793636,
    "email": "gramabates@gmail.com",
    "name": "Betty Bates",
    "integrations": {
      "82185": {
        "__integration_type__": "shopify",
        "customer": {
          "id": 7408502702335,
          "email": "gramabates@gmail.com",
          "phone": "+12345678901",
          "orders_count": 12,
          "total_spent": "1250.50"
        }
      }
    }
  }
}
```

**What This Gives Us:**
- ✅ Shopify customer ID: `7408502702335`
- ✅ Total orders: `12`
- ✅ Lifetime value: `$1,250.50`
- ❌ **Individual order details** (need additional query)
- ❌ **Product-level data** (need additional query)

**How Bot Currently Uses This:**

See [integrations/gorgias_ai_assistant.py:607](integrations/gorgias_ai_assistant.py#L607):

```python
def _extract_shopify_metrics(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Shopify metrics from Gorgias webhook integrations."""
    integrations = customer_data.get("integrations", {})

    for integration_id, integration_data in integrations.items():
        if integration_data.get("__integration_type__") == "shopify":
            shopify_customer = integration_data.get("customer", {})
            return {
                "shopify_customer_id": shopify_customer.get("id"),
                "orders_count": shopify_customer.get("orders_count", 0),
                "total_spent": float(shopify_customer.get("total_spent", "0.0")),
                "email": shopify_customer.get("email"),
                "phone": shopify_customer.get("phone")
            }

    return {}
```

**Limitation:** This only gives us **aggregate metrics**, not individual order line items.

---

### Option 2: MCP Analytics API (BEHAVIORAL DATA ✅)

The MCP API can retrieve behavioral analytics from the database.

**API Endpoint:**
```
GET https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/{customer_id}/analytics
Headers: X-API-Key: e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31
```

**Returns:**
```json
{
  "customer_id": "7408502702335",
  "archetype": {
    "archetype_id": "arch_729945",
    "member_count": 69,
    "avg_lifetime_value": 400.31,
    "avg_order_frequency": 4.01
  },
  "dominant_segments": {
    "purchase_frequency": "moderate_buyer",
    "price_sensitivity": "premium_oriented"
  },
  "membership_strengths": {...},
  "business_metrics": {
    "lifetime_value": 1250.50,
    "total_orders": 12,
    "avg_order_value": 104.21,
    "days_since_last_purchase": 15,
    "customer_tenure_days": 892
  }
}
```

**What This Gives Us:**
- ✅ Lifetime value and order count (confirms Shopify data)
- ✅ Behavioral segments (premium buyer, etc.)
- ✅ Customer tenure (892 days = ~2.4 years)
- ❌ **Product-level details** (no order line items)

**Limitation:** Database has **aggregate customer profiles**, not individual product purchases.

---

### Option 3: Shopify GraphQL API (DETAILED ORDERS ✅ BEST FOR THIS QUESTION)

To answer Betty's question about the **specific Tula Pink iron**, we need **product-level order history**.

**Shopify GraphQL Query:**
```graphql
query ($query: String!) {
  customers(first: 1, query: $query) {
    edges {
      node {
        id
        legacyResourceId
        email
        firstName
        lastName
        ordersCount
        totalSpent
        orders(first: 50, sortKey: CREATED_AT, reverse: true) {
          edges {
            node {
              id
              name
              createdAt
              totalPriceSet {
                shopMoney {
                  amount
                }
              }
              lineItems(first: 100) {
                edges {
                  node {
                    title
                    quantity
                    variant {
                      product {
                        title
                        vendor
                        productType
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

**Query Variables:**
```json
{
  "query": "email:gramabates@gmail.com"
}
```

**API Endpoint:**
```
POST https://linda.myshopify.com/admin/api/2024-10/graphql.json
Headers:
  X-Shopify-Access-Token: {SHOPIFY_ACCESS_TOKEN from Railway env}
  Content-Type: application/json
```

**What This Gives Us:**
- ✅ **All orders** (up to 50 most recent)
- ✅ **Every product purchased** (title, quantity, vendor)
- ✅ **Order dates** (can filter to ~1 year ago)
- ✅ **Can search for "Tula Pink" in product titles**

**This is the BEST option for answering Betty's question.**

---

## Recommended Implementation

### Step 1: Create Shopify Order History Endpoint

Add new endpoint to [backend/main.py](backend/main.py):

```python
@app.get("/api/mcp/customer/{customer_id}/orders", dependencies=[Depends(require_api_key)])
async def get_customer_order_history(customer_id: str, limit: int = 50):
    """
    Retrieve detailed order history from Shopify for a customer.

    Returns:
      - All orders (up to limit)
      - Product line items
      - Order dates
      - Total spent per order
    """
    shop_name = os.getenv("SHOPIFY_SHOP_NAME", "linda")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
    api_version = os.getenv("SHOPIFY_API_VERSION", "2024-10")

    if not access_token:
        raise HTTPException(status_code=500, detail="Shopify not configured")

    graphql_url = f"https://{shop_name}.myshopify.com/admin/api/{api_version}/graphql.json"

    # Convert numeric customer_id to Shopify GID format
    shopify_gid = f"gid://shopify/Customer/{customer_id}"

    query = """
    query ($id: ID!) {
      customer(id: $id) {
        id
        email
        firstName
        lastName
        ordersCount
        orders(first: $limit, sortKey: CREATED_AT, reverse: true) {
          edges {
            node {
              id
              name
              createdAt
              totalPriceSet {
                shopMoney {
                  amount
                }
              }
              lineItems(first: 100) {
                edges {
                  node {
                    title
                    quantity
                    variant {
                      product {
                        title
                        vendor
                        productType
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            graphql_url,
            json={
                "query": query,
                "variables": {"id": shopify_gid, "limit": limit}
            },
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json"
            }
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Shopify API error")

        data = response.json()

        if "errors" in data:
            raise HTTPException(status_code=500, detail=data["errors"])

        customer_data = data.get("data", {}).get("customer")
        if not customer_data:
            raise HTTPException(status_code=404, detail="Customer not found in Shopify")

        # Format response
        orders = []
        for edge in customer_data.get("orders", {}).get("edges", []):
            order = edge["node"]

            # Extract products
            products = []
            for item_edge in order.get("lineItems", {}).get("edges", []):
                item = item_edge["node"]
                product = item.get("variant", {}).get("product", {})

                products.append({
                    "title": item.get("title", "Unknown"),
                    "quantity": item.get("quantity", 1),
                    "product_title": product.get("title", "Unknown"),
                    "vendor": product.get("vendor", "Unknown"),
                    "product_type": product.get("productType", "Unknown")
                })

            orders.append({
                "order_id": order.get("name", ""),
                "created_at": order.get("createdAt", ""),
                "total": order.get("totalPriceSet", {}).get("shopMoney", {}).get("amount", "0.00"),
                "products": products
            })

        return {
            "customer_id": customer_id,
            "email": customer_data.get("email"),
            "name": f"{customer_data.get('firstName', '')} {customer_data.get('lastName', '')}".strip(),
            "total_orders": customer_data.get("ordersCount", 0),
            "orders": orders
        }
```

### Step 2: Update Bot to Use Order History

Modify [integrations/gorgias_ai_assistant.py](integrations/gorgias_ai_assistant.py) to fetch detailed orders when needed:

```python
async def _fetch_order_history(self, shopify_customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch detailed order history from Shopify via analytics API.

    Used when customer asks about specific past purchases.
    """
    if not shopify_customer_id:
        return None

    try:
        url = f"{self.analytics_api_url}/api/mcp/customer/{shopify_customer_id}/orders"
        headers = {"X-API-Key": self.analytics_api_key}

        response = await self.http_client.get(url, headers=headers, timeout=15.0)

        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to fetch order history: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error fetching order history: {e}")
        return None
```

### Step 3: Search Orders for Specific Products

Add helper to search for products in order history:

```python
def _search_orders_for_product(
    self,
    order_history: Dict[str, Any],
    search_terms: List[str],
    months_ago: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Search customer's order history for products matching search terms.

    Args:
        order_history: Order history from /orders endpoint
        search_terms: Product keywords to search for (e.g., ["tula pink", "iron"])
        months_ago: Filter to orders within N months ago (optional)

    Returns:
        List of matching orders with product details
    """
    from datetime import datetime, timedelta

    matching_orders = []
    cutoff_date = None

    if months_ago:
        cutoff_date = datetime.now() - timedelta(days=months_ago * 30)

    for order in order_history.get("orders", []):
        # Filter by date if specified
        if cutoff_date:
            order_date = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
            if order_date < cutoff_date:
                continue

        # Search products in this order
        matching_products = []
        for product in order.get("products", []):
            product_text = f"{product.get('title', '')} {product.get('product_title', '')}".lower()

            # Check if ANY search term matches
            if any(term.lower() in product_text for term in search_terms):
                matching_products.append(product)

        # If any products matched, include this order
        if matching_products:
            matching_orders.append({
                "order_id": order.get("order_id"),
                "created_at": order.get("created_at"),
                "total": order.get("total"),
                "matching_products": matching_products
            })

    return matching_orders
```

---

## Example: Answering Betty's Question

### Current Bot Response (WITHOUT order history):

```
Hi Betty,

I'd be happy to help you track down where you purchased your Tula Pink iron!

I can see you're a valued customer with 452 Corey's Cash points and a recent order. However,
I don't have access to your detailed product purchase history in this system.

Could you provide:
- Approximate date of purchase (month/year)
- Order number if you have it
- Any other details about the purchase

I'll check our records to confirm if you bought it from us!

Best regards,
Linda's Customer Service
```

**Problem:** Bot can't definitively answer the question without order history.

### Improved Bot Response (WITH order history):

**Scenario A: Found Tula Pink Iron**

```python
# Fetch order history
order_history = await self._fetch_order_history("7408502702335")

# Search for Tula Pink iron in last 18 months
matches = self._search_orders_for_product(
    order_history,
    search_terms=["tula pink", "iron"],
    months_ago=18
)

if matches:
    # Found it!
    match = matches[0]  # Most recent
    created_at = datetime.fromisoformat(match["created_at"].replace("Z", "+00:00"))
    formatted_date = created_at.strftime("%B %d, %Y")

    product = match["matching_products"][0]
```

**Bot Response:**

```
Hi Betty,

Great news! Yes, you did purchase your Tula Pink iron from us!

📦 Order Details:
- Order #: 1234
- Date: March 15, 2024 (about 8 months ago)
- Product: Tula Pink Perfect Scissors Iron
- Order Total: $89.99

You can find this order in your account history. Is there anything else I can help
you with regarding this product?

Best regards,
Linda's Customer Service

✨ You have 452 Corey's Cash available - that's $4.52 off your next order!
```

**Scenario B: NOT Found**

```
Hi Betty,

I've checked your order history with us going back 18 months, and I don't see a
Tula Pink iron in your purchases from Linda's.

You may have purchased it from:
- Another quilting retailer
- Tula Pink's website directly
- A local quilt shop

Your orders with us include:
- March 2024: Fabric bundles and thread
- November 2023: Quilt batting and rulers
- August 2023: Tula Pink fabric collection

Is there anything else I can help you find?

Best regards,
Linda's Customer Service
```

---

## Implementation Checklist

- [ ] Add `/api/mcp/customer/{customer_id}/orders` endpoint to backend/main.py
- [ ] Add `_fetch_order_history()` method to GorgiasAIAssistant
- [ ] Add `_search_orders_for_product()` helper method
- [ ] Update bot prompt to mention order history capabilities
- [ ] Test with Betty's actual email (gramabates@gmail.com)
- [ ] Verify Shopify API credentials work in Railway
- [ ] Monitor for Shopify API rate limits (2 requests/second)
- [ ] Add caching for order history (avoid repeated API calls)
- [ ] Document in API_DOCUMENTATION.md

---

## API Rate Limits

**Shopify GraphQL API:**
- Standard: 50 points/second (bucket size 1000)
- Each query costs variable points (simple query = 2-5 points)
- Order history query: ~10-15 points
- **Max ~3-5 order history queries per second**

**Recommendation:** Cache order history for 15 minutes to avoid repeat queries.

---

## Testing

### Test Query:

```bash
# After implementing endpoint
curl -s "https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/7408502702335/orders?limit=20" \
  -H "X-API-Key: e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31" | python3 -m json.tool

# Expected response:
{
  "customer_id": "7408502702335",
  "email": "gramabates@gmail.com",
  "name": "Betty Bates",
  "total_orders": 12,
  "orders": [
    {
      "order_id": "#1234",
      "created_at": "2024-03-15T10:30:00Z",
      "total": "89.99",
      "products": [
        {
          "title": "Tula Pink Perfect Scissors Iron",
          "quantity": 1,
          "product_title": "Tula Pink Perfect Scissors Iron",
          "vendor": "Tula Pink",
          "product_type": "Quilting Tools"
        }
      ]
    },
    ...
  ]
}
```

---

## Security Considerations

1. **API Key Required:** Order history endpoint must require `ADMIN_KEY`
2. **Customer ID Validation:** Only return orders for authenticated customer
3. **PII Handling:** Order history contains sensitive data (addresses, payment info)
4. **Rate Limiting:** Prevent abuse via rate limits
5. **Shopify Token Security:** SHOPIFY_ACCESS_TOKEN must remain in Railway env only

---

## Future Enhancements

1. **Natural Language Search:** "Show me all fabric purchases" → auto-search product types
2. **Reorder Suggestions:** "Would you like to order another one?"
3. **Product Recommendations:** "Customers who bought this also bought..."
4. **Warranty Lookup:** "Check if product is still under warranty"
5. **Shipping Tracking:** "Where is my order?" integration with ShipStation

---

**Status:** Ready to implement - requires Shopify GraphQL endpoint addition

**Estimated Time:** 2-3 hours
- 1 hour: Add `/orders` endpoint and test
- 1 hour: Integrate into GorgiasAIAssistant
- 30 min: Test with Betty's real ticket
- 30 min: Documentation

**Priority:** Medium (improves customer experience, not critical for core bot function)
