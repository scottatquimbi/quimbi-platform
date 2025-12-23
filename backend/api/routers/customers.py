"""
Customer & MCP Endpoints Router

Provides:
- Customer profile endpoints with Redis caching
- Churn risk predictions
- Next purchase predictions
- LTV forecasting
- Random customer sampling
- Customer search functionality
- Archetype statistics

All endpoints require API key authentication.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Dict, Any, List
import random
import os
import httpx
from datetime import datetime

# Import MCP server
from mcp_server.segmentation_server import handle_mcp_call, data_store

# Import caching
from backend.cache.redis_cache import (
    get_cached_customer,
    cache_customer,
    get_cached_churn_prediction,
    cache_churn_prediction
)

# Import authentication
from backend.api.dependencies import require_api_key

# Import logging
from backend.middleware.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/mcp",
    tags=["customers", "mcp"],
    dependencies=[Depends(require_api_key)],
    responses={404: {"description": "Not found"}},
)


# ==================== Customer Profile Endpoints ====================

@router.get("/customer/random")
async def get_random_customer():
    """Get a random customer profile."""
    try:
        # Pick a random customer from the data store
        if not data_store.customers:
            raise HTTPException(status_code=503, detail="No customers loaded")

        customer_id = random.choice(list(data_store.customers.keys()))
        result = handle_mcp_call("get_customer_profile", {"customer_id": customer_id})
        return result
    except Exception as e:
        logger.error(f"Failed to get random customer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}")
async def get_customer_profile(customer_id: str):
    """Get customer behavioral profile (convenience endpoint) with Redis caching."""
    try:
        # Try cache first
        cached_result = await get_cached_customer(customer_id)
        if cached_result:
            logger.debug("cache_hit", resource="customer_profile", customer_id=customer_id)
            return cached_result

        # Cache miss - fetch from data store
        logger.debug("cache_miss", resource="customer_profile", customer_id=customer_id)
        result = handle_mcp_call("get_customer_profile", {"customer_id": customer_id})

        # Cache the result (1 hour TTL)
        await cache_customer(customer_id, result, ttl=3600)

        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    except Exception as e:
        logger.error(f"Failed to get customer profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}/churn-risk")
async def get_churn_risk(customer_id: str):
    """Get churn risk prediction for customer (convenience endpoint) with Redis caching."""
    try:
        # Try cache first (30 min TTL for churn predictions)
        cached_result = await get_cached_churn_prediction(customer_id)
        if cached_result:
            logger.debug("cache_hit", resource="churn_prediction", customer_id=customer_id)
            return cached_result

        # Cache miss - calculate churn risk
        logger.debug("cache_miss", resource="churn_prediction", customer_id=customer_id)
        result = handle_mcp_call("predict_churn_risk", {"customer_id": customer_id})

        # Cache the result (30 min TTL)
        await cache_churn_prediction(customer_id, result, ttl=1800)

        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    except Exception as e:
        logger.error(f"Failed to predict churn risk: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}/next-purchase")
async def predict_next_purchase(customer_id: str):
    """Predict when customer will make next purchase."""
    try:
        customer = data_store.customers.get(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

        # Calculate days since last order
        from datetime import datetime
        last_order_date = customer.get("last_order_date")
        if not last_order_date:
            return {
                "customer_id": customer_id,
                "prediction": "insufficient_data",
                "message": "No order history available"
            }

        days_since_last = (datetime.now() - datetime.fromisoformat(last_order_date.replace('Z', '+00:00'))).days

        # Use purchase frequency archetype
        archetype = customer.get("archetypes", {}).get("purchase_frequency", "unknown")

        # Predict based on frequency patterns
        frequency_patterns = {
            "very_frequent": 7,      # Weekly
            "frequent": 14,          # Bi-weekly
            "regular": 30,           # Monthly
            "occasional": 60,        # Bi-monthly
            "rare": 90,              # Quarterly
            "very_rare": 180         # Semi-annually
        }

        expected_days = frequency_patterns.get(archetype, 45)
        days_until_next = max(0, expected_days - days_since_last)

        # Calculate probability
        if days_since_last >= expected_days * 1.5:
            probability = "low"
            risk_level = "at_risk"
        elif days_since_last >= expected_days:
            probability = "medium"
            risk_level = "due"
        else:
            probability = "high"
            risk_level = "on_track"

        return {
            "customer_id": customer_id,
            "days_since_last_order": days_since_last,
            "predicted_days_until_next": days_until_next,
            "probability": probability,
            "risk_level": risk_level,
            "purchase_frequency_archetype": archetype,
            "expected_frequency_days": expected_days
        }
    except Exception as e:
        logger.error(f"Failed to predict next purchase: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}/ltv-forecast")
async def forecast_customer_ltv(customer_id: str, months: int = 12):
    """Forecast customer lifetime value over specified period."""
    try:
        customer = data_store.customers.get(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

        # Get current metrics
        total_value = customer.get("total_value", 0)
        order_count = customer.get("order_count", 0)

        if order_count == 0:
            return {
                "customer_id": customer_id,
                "forecast_months": months,
                "predicted_ltv": 0,
                "message": "No order history available"
            }

        # Calculate average order value and frequency
        avg_order_value = total_value / order_count

        # Get purchase frequency from archetype
        frequency_archetype = customer.get("archetypes", {}).get("purchase_frequency", "occasional")

        # Estimate orders per month
        frequency_map = {
            "very_frequent": 4,     # ~4 orders/month
            "frequent": 2,          # ~2 orders/month
            "regular": 1,           # ~1 order/month
            "occasional": 0.5,      # ~1 order every 2 months
            "rare": 0.33,           # ~1 order every 3 months
            "very_rare": 0.17       # ~1 order every 6 months
        }

        orders_per_month = frequency_map.get(frequency_archetype, 0.5)

        # Get churn risk
        churn_risk = customer.get("churn_risk", 0.3)
        retention_rate = 1 - (churn_risk / 12)  # Monthly retention rate

        # Forecast month by month with decay
        monthly_forecast = []
        cumulative_ltv = total_value  # Start with current LTV

        for month in range(1, months + 1):
            # Apply retention probability
            active_probability = retention_rate ** month
            expected_orders = orders_per_month * active_probability
            expected_value = expected_orders * avg_order_value
            cumulative_ltv += expected_value

            monthly_forecast.append({
                "month": month,
                "expected_orders": round(expected_orders, 2),
                "expected_revenue": round(expected_value, 2),
                "cumulative_ltv": round(cumulative_ltv, 2),
                "retention_probability": round(active_probability * 100, 1)
            })

        return {
            "customer_id": customer_id,
            "current_ltv": round(total_value, 2),
            "current_order_count": order_count,
            "avg_order_value": round(avg_order_value, 2),
            "churn_risk": round(churn_risk, 3),
            "forecast_months": months,
            "predicted_ltv": round(cumulative_ltv, 2),
            "monthly_forecast": monthly_forecast
        }
    except Exception as e:
        logger.error(f"Failed to forecast LTV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Archetype Endpoints ====================

@router.get("/archetype/{archetype_id}")
async def get_archetype_stats(archetype_id: str):
    """Get archetype statistics (convenience endpoint)."""
    try:
        result = handle_mcp_call("get_archetype_stats", {"archetype_id": archetype_id})
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Archetype {archetype_id} not found")
    except Exception as e:
        logger.error(f"Failed to get archetype stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Search Endpoints ====================

@router.post("/search")
async def search_customers(
    archetype_id: Optional[str] = None,
    segment_filter: Optional[Dict[str, str]] = None,
    limit: int = 100
):
    """Search for customers by archetype or segments."""
    try:
        result = handle_mcp_call("search_customers", {
            "archetype_id": archetype_id,
            "segment_filter": segment_filter,
            "limit": limit
        })
        return result
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/search")
async def search_customer_by_email(email: str):
    """
    Search for a customer by email address.

    Returns customer ID if found, which can be used with other endpoints.
    """
    try:
        # Search through data store for matching email
        for customer_id, customer_data in data_store.customers.items():
            if customer_data.get("email", "").lower() == email.lower():
                return {
                    "customer_id": customer_id,
                    "email": customer_data.get("email"),
                    "name": customer_data.get("name", ""),
                    "found": True
                }

        raise HTTPException(status_code=404, detail=f"Customer with email {email} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Customer search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Shopify Order History ====================

@router.get("/customer/{customer_id}/orders")
async def get_customer_order_history(
    customer_id: str,
    limit: int = 50,
    search_terms: Optional[str] = None,
    months_ago: Optional[int] = None
):
    """
    Retrieve detailed order history from Shopify for a customer.

    This endpoint queries Shopify's GraphQL API to get:
    - All orders (up to limit)
    - Product line items with titles, quantities, vendors
    - Order dates and totals
    - Optional filtering by search terms and date range

    Args:
        customer_id: Shopify customer ID (numeric string like "7408502702335")
        limit: Maximum number of orders to return (default 50, max 100)
        search_terms: Optional comma-separated product search terms (e.g., "tula pink,iron")
        months_ago: Optional filter to orders within N months ago

    Returns:
        Customer order history with product details

    Examples:
        - /api/mcp/customer/7408502702335/orders
        - /api/mcp/customer/7408502702335/orders?limit=20
        - /api/mcp/customer/7408502702335/orders?search_terms=tula%20pink&months_ago=12
    """
    try:
        # Get Shopify configuration from environment
        shop_name = os.getenv("SHOPIFY_SHOP_NAME")
        access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        api_version = os.getenv("SHOPIFY_API_VERSION", "2024-10")

        if not shop_name or not access_token:
            logger.error("Shopify credentials not configured")
            raise HTTPException(
                status_code=503,
                detail="Shopify integration not configured. Missing SHOPIFY_SHOP_NAME or SHOPIFY_ACCESS_TOKEN."
            )

        # Validate limit
        if limit > 100:
            limit = 100

        # Construct Shopify GraphQL URL
        graphql_url = f"https://{shop_name}.myshopify.com/admin/api/{api_version}/graphql.json"

        # Convert numeric customer_id to Shopify GID format
        shopify_gid = f"gid://shopify/Customer/{customer_id}"

        # Build GraphQL query
        query = """
        query ($id: ID!, $limit: Int!) {
          customer(id: $id) {
            id
            email
            firstName
            lastName
            orders(first: $limit, sortKey: CREATED_AT, reverse: true) {
              edges {
                node {
                  id
                  name
                  createdAt
                  totalPriceSet {
                    shopMoney {
                      amount
                      currencyCode
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

        logger.info(f"Fetching order history for customer {customer_id} from Shopify")

        # Make GraphQL request
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
                logger.error(f"Shopify API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Shopify API error: {response.text}"
                )

            data = response.json()

            # Check for GraphQL errors
            if "errors" in data:
                logger.error(f"Shopify GraphQL errors: {data['errors']}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Shopify GraphQL error: {data['errors']}"
                )

            # Extract customer data
            customer_data = data.get("data", {}).get("customer")
            if not customer_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Customer {customer_id} not found in Shopify"
                )

            # Process orders
            orders = []
            cutoff_date = None

            if months_ago:
                from datetime import timedelta, timezone
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=months_ago * 30)

            for edge in customer_data.get("orders", {}).get("edges", []):
                order = edge["node"]
                order_date = datetime.fromisoformat(order.get("createdAt", "").replace("Z", "+00:00"))

                # Filter by date if specified
                if cutoff_date and order_date < cutoff_date:
                    continue

                # Extract products
                products = []
                for item_edge in order.get("lineItems", {}).get("edges", []):
                    item = item_edge["node"]
                    product_data = item.get("variant", {}).get("product", {})

                    product_info = {
                        "title": item.get("title", "Unknown"),
                        "quantity": item.get("quantity", 1),
                        "product_title": product_data.get("title", "Unknown"),
                        "vendor": product_data.get("vendor", "Unknown"),
                        "product_type": product_data.get("productType", "Unknown")
                    }

                    # Filter by search terms if specified
                    if search_terms:
                        search_list = [term.strip().lower() for term in search_terms.split(",")]
                        product_text = f"{product_info['title']} {product_info['product_title']}".lower()

                        # Only include if matches any search term
                        if not any(term in product_text for term in search_list):
                            continue

                    products.append(product_info)

                # If search terms specified, only include orders with matching products
                if search_terms and not products:
                    continue

                # Build order response
                total_price = order.get("totalPriceSet", {}).get("shopMoney", {})
                orders.append({
                    "order_id": order.get("name", ""),
                    "shopify_order_id": order.get("id", ""),
                    "created_at": order.get("createdAt", ""),
                    "total": total_price.get("amount", "0.00"),
                    "currency": total_price.get("currencyCode", "USD"),
                    "products": products if not search_terms else products,
                    "product_count": len(products)
                })

            # Calculate total orders and lifetime spent from orders list
            total_orders_count = len(orders)
            lifetime_spent = sum(float(order.get("total", 0)) for order in orders)

            # Build response
            result = {
                "customer_id": customer_id,
                "email": customer_data.get("email"),
                "name": f"{customer_data.get('firstName', '')} {customer_data.get('lastName', '')}".strip(),
                "total_orders_returned": total_orders_count,
                "estimated_lifetime_spent": f"{lifetime_spent:.2f}",
                "orders_returned": len(orders),
                "orders": orders,
                "filters_applied": {
                    "limit": limit,
                    "search_terms": search_terms,
                    "months_ago": months_ago
                },
                "note": "total_orders_returned and estimated_lifetime_spent are calculated from returned orders only"
            }

            logger.info(
                f"Retrieved {len(orders)} orders for customer {customer_id}",
                extra={
                    "customer_id": customer_id,
                    "orders_count": len(orders),
                    "search_terms": search_terms,
                    "months_filter": months_ago
                }
            )

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch order history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
