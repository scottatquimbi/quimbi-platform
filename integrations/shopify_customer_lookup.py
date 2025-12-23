"""
Shopify Customer Lookup by Phone Number

Uses Shopify Admin GraphQL API to find customer ID by phone number.
Implements phone number normalization and async lookup with error handling.

Usage:
    from integrations.shopify_customer_lookup import get_shopify_lookup

    lookup = get_shopify_lookup()
    if lookup:
        customer_id = await lookup.lookup_by_phone("+1234567890")
"""
import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ShopifyCustomerLookup:
    """Look up Shopify customers by phone number using GraphQL API."""

    def __init__(self, shop_name: str, access_token: str, api_version: str = "2024-10"):
        """
        Initialize Shopify API client.

        Args:
            shop_name: Shopify shop name (e.g., "linda", not full URL)
            access_token: Shopify Admin API access token (starts with shpat_)
            api_version: Shopify API version (default: 2024-10)
        """
        self.shop_name = shop_name
        self.access_token = access_token
        self.api_version = api_version
        self.graphql_url = f"https://{shop_name}.myshopify.com/admin/api/{api_version}/graphql.json"
        self.http_client = httpx.AsyncClient(timeout=10.0)
        logger.info(f"Initialized Shopify lookup for shop: {shop_name}")

    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number for Shopify query.

        Shopify stores phones in E.164 format: +1234567890

        Args:
            phone: Raw phone number (various formats)

        Returns:
            Normalized phone in E.164 format

        Examples:
            "(555) 123-4567" → "+15551234567"
            "555-123-4567" → "+15551234567"
            "+1 555 123 4567" → "+15551234567"
            "+15551234567" → "+15551234567"
        """
        if not phone:
            return ""

        # Remove all non-digit characters except '+'
        digits = ''.join(c for c in phone if c.isdigit() or c == '+')

        # If starts with '+', assume already in E.164
        if digits.startswith('+'):
            return digits

        # If 10 digits (US/Canada), add +1
        if len(digits) == 10:
            return f"+1{digits}"

        # If 11 digits starting with '1', add +
        if len(digits) == 11 and digits.startswith('1'):
            return f"+{digits}"

        # Otherwise return as-is with + prefix
        return f"+{digits}" if not digits.startswith('+') else digits

    async def lookup_by_phone(self, phone: str) -> Optional[str]:
        """
        Look up Shopify customer ID by phone number.

        This method:
        1. Normalizes phone to E.164 format
        2. Queries Shopify GraphQL API
        3. Returns legacyResourceId (numeric string) if found

        Args:
            phone: Phone number (any format)

        Returns:
            Shopify customer ID (numeric string like "7415378247935") or None if not found

        Raises:
            No exceptions raised - returns None on any error
        """
        if not phone:
            logger.warning("Empty phone number provided for lookup")
            return None

        try:
            # Normalize phone to E.164
            normalized_phone = self._normalize_phone(phone)
            logger.info(f"🔍 Looking up Shopify customer by phone: {normalized_phone}")

            # GraphQL query to search customers by phone
            query = """
            query ($query: String!) {
              customers(first: 1, query: $query) {
                edges {
                  node {
                    id
                    legacyResourceId
                    phone
                    email
                    firstName
                    lastName
                  }
                }
              }
            }
            """

            # Build Shopify search query string
            # Shopify search syntax: phone:+1234567890
            phone_query = f"phone:{normalized_phone}"

            # Execute GraphQL request
            response = await self.http_client.post(
                self.graphql_url,
                json={
                    "query": query,
                    "variables": {"query": phone_query}
                },
                headers={
                    "X-Shopify-Access-Token": self.access_token,
                    "Content-Type": "application/json"
                }
            )

            if response.status_code != 200:
                logger.error(f"❌ Shopify API error: {response.status_code} - {response.text}")
                return None

            data = response.json()

            # Check for GraphQL errors
            if "errors" in data:
                logger.error(f"❌ Shopify GraphQL errors: {data['errors']}")
                return None

            # Extract customer from response
            edges = data.get("data", {}).get("customers", {}).get("edges", [])
            if not edges:
                logger.warning(f"❌ No customer found for phone: {normalized_phone}")
                return None

            customer = edges[0]["node"]
            customer_id = customer["legacyResourceId"]  # Numeric ID

            logger.info(f"✅ Found Shopify customer: {customer_id} ({customer.get('firstName')} {customer.get('lastName')}, {customer.get('email')})")
            return str(customer_id)

        except httpx.TimeoutException:
            logger.error(f"⏱️  Shopify API timeout while looking up phone: {phone}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error during Shopify lookup: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error looking up customer by phone: {e}", exc_info=True)
            return None

    async def close(self):
        """Close HTTP client connection."""
        await self.http_client.aclose()
        logger.info("Closed Shopify API client")


# Module-level singleton instance (lazy initialization)
_shopify_lookup: Optional[ShopifyCustomerLookup] = None


def get_shopify_lookup() -> Optional[ShopifyCustomerLookup]:
    """
    Get or create Shopify customer lookup instance.

    Reads configuration from environment variables:
    - SHOPIFY_SHOP_NAME: Shop name (e.g., "linda")
    - SHOPIFY_ACCESS_TOKEN: Admin API token (starts with shpat_)
    - SHOPIFY_API_VERSION: API version (optional, defaults to 2024-10)

    Returns:
        ShopifyCustomerLookup instance or None if credentials not configured
    """
    global _shopify_lookup

    if _shopify_lookup is None:
        shop_name = os.getenv("SHOPIFY_SHOP_NAME")
        access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        api_version = os.getenv("SHOPIFY_API_VERSION", "2024-10")

        if not shop_name or not access_token:
            logger.warning(
                "Shopify customer lookup not configured - missing environment variables: "
                "SHOPIFY_SHOP_NAME, SHOPIFY_ACCESS_TOKEN"
            )
            return None

        _shopify_lookup = ShopifyCustomerLookup(
            shop_name=shop_name,
            access_token=access_token,
            api_version=api_version
        )

        logger.info("✅ Shopify customer lookup initialized")

    return _shopify_lookup
