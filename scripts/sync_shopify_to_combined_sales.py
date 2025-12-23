#!/usr/bin/env python3
"""
Shopify to Railway Postgres Combined Sales Sync

Replaces Azure SQL sync with direct Shopify GraphQL API integration.
Fetches orders from Shopify and transforms them into combined_sales format.

Prerequisites:
1. Set environment variables:
   - SHOPIFY_SHOP_NAME (e.g., "lindas-electric-quilters")
   - SHOPIFY_ACCESS_TOKEN (Admin API token: shpat_...)
   - DATABASE_URL (Railway Postgres connection string)

Usage:
    # Full sync (all orders)
    python scripts/sync_shopify_to_combined_sales.py --full

    # Incremental sync (only orders since last sync)
    python scripts/sync_shopify_to_combined_sales.py --incremental

    # Date range
    python scripts/sync_shopify_to_combined_sales.py --start-date 2024-01-01

    # Dry run (preview data)
    python scripts/sync_shopify_to_combined_sales.py --dry-run --limit 10
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import asyncio

import httpx
import pandas as pd
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ShopifyOrderSync:
    """Sync Shopify orders to Railway Postgres combined_sales table."""

    def __init__(self, shop_name: str, access_token: str, postgres_url: str):
        """
        Initialize Shopify sync configuration.

        Args:
            shop_name: Shopify shop name (e.g., "lindas-electric-quilters")
            access_token: Shopify Admin API access token (starts with shpat_)
            postgres_url: Railway Postgres connection string
        """
        self.shop_name = shop_name
        self.access_token = access_token
        self.postgres_url = postgres_url
        self.api_version = "2024-10"
        self.graphql_url = f"https://{shop_name}.myshopify.com/admin/api/{self.api_version}/graphql.json"
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.postgres_engine = None

        logger.info(f"Initialized Shopify sync for shop: {shop_name}")

    def connect_postgres(self):
        """Connect to Railway Postgres."""
        try:
            logger.info("Connecting to Railway Postgres...")
            self.postgres_engine = create_engine(self.postgres_url)

            # Test connection
            with self.postgres_engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info("✅ Connected to Railway Postgres")
            return self.postgres_engine

        except Exception as e:
            logger.error(f"Failed to connect to Postgres: {e}")
            raise

    async def fetch_orders(self, start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch orders from Shopify GraphQL API.

        Args:
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)
            limit: Maximum orders to fetch (for testing)

        Returns:
            List of order dictionaries
        """
        logger.info("Fetching orders from Shopify GraphQL API...")

        # Build query filter
        query_parts = []
        if start_date:
            query_parts.append(f"created_at:>='{start_date}'")
        if end_date:
            query_parts.append(f"created_at:<='{end_date}'")

        query_string = " AND ".join(query_parts) if query_parts else ""

        # Determine batch size
        batch_size = min(limit, 250) if limit else 250  # Shopify max per query

        all_orders = []
        has_next_page = True
        cursor = None

        try:
            while has_next_page:
                # GraphQL query for orders with line items
                graphql_query = """
                query ($first: Int!, $query: String, $after: String) {
                  orders(first: $first, query: $query, after: $after, sortKey: CREATED_AT) {
                    edges {
                      cursor
                      node {
                        id
                        legacyResourceId
                        name
                        createdAt
                        processedAt
                        customer {
                          id
                          legacyResourceId
                        }
                        totalPriceSet {
                          shopMoney {
                            amount
                            currencyCode
                          }
                        }
                        displayFulfillmentStatus
                        displayFinancialStatus
                        shippingAddress {
                          latitude
                          longitude
                        }
                        lineItems(first: 100) {
                          edges {
                            node {
                              id
                              quantity
                              sku
                              product {
                                id
                                legacyResourceId
                                title
                                productType
                              }
                              variant {
                                id
                                title
                              }
                              originalTotalSet {
                                shopMoney {
                                  amount
                                  currencyCode
                                }
                              }
                              discountedTotalSet {
                                shopMoney {
                                  amount
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                  }
                }
                """

                # Execute GraphQL request
                response = await self.http_client.post(
                    self.graphql_url,
                    json={
                        "query": graphql_query,
                        "variables": {
                            "first": batch_size,
                            "query": query_string or None,
                            "after": cursor
                        }
                    },
                    headers={
                        "X-Shopify-Access-Token": self.access_token,
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    logger.error(f"❌ Shopify API error: {response.status_code} - {response.text}")
                    raise Exception(f"Shopify API request failed: {response.status_code}")

                data = response.json()

                # Check for GraphQL errors
                if "errors" in data:
                    logger.error(f"❌ Shopify GraphQL errors: {data['errors']}")
                    raise Exception(f"GraphQL errors: {data['errors']}")

                # Extract orders
                edges = data.get("data", {}).get("orders", {}).get("edges", [])
                page_info = data.get("data", {}).get("orders", {}).get("pageInfo", {})

                # Process each order
                for edge in edges:
                    order = edge["node"]
                    all_orders.append(order)

                logger.info(f"Fetched {len(all_orders)} orders so far...")

                # Check if we should continue
                has_next_page = page_info.get("hasNextPage", False) and (
                    limit is None or len(all_orders) < limit
                )
                cursor = page_info.get("endCursor")

                # Respect limit
                if limit and len(all_orders) >= limit:
                    all_orders = all_orders[:limit]
                    break

            logger.info(f"✅ Fetched {len(all_orders):,} orders from Shopify")
            return all_orders

        except Exception as e:
            logger.error(f"Failed to fetch orders: {e}")
            raise

    def transform_to_combined_sales(self, orders: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Transform Shopify orders into combined_sales format.

        Shopify provides nested JSON, we need to flatten line items.

        Args:
            orders: List of Shopify order objects

        Returns:
            pandas DataFrame in combined_sales format
        """
        logger.info("Transforming Shopify orders to combined_sales format...")

        rows = []

        for order in orders:
            # Extract order-level fields
            order_id = int(order["legacyResourceId"])

            # Order number can be complex (e.g., "#111-2457170-4806665")
            # Store the numeric part only, or hash if too complex
            order_name = order["name"].replace("#", "")
            try:
                order_number = int(order_name)
            except ValueError:
                # For complex order numbers, use order_id as fallback
                order_number = order_id

            customer_id = int(order.get("customer", {}).get("legacyResourceId", 0)) if order.get("customer") else None

            # Skip orders without customer_id
            if not customer_id:
                logger.warning(f"Skipping order {order_id} - no customer_id")
                continue

            order_date = pd.to_datetime(order["createdAt"])
            created_at = pd.to_datetime(order.get("processedAt", order["createdAt"]))

            # Extract order metadata
            total_price = float(order.get("totalPriceSet", {}).get("shopMoney", {}).get("amount", 0))
            currency = order.get("totalPriceSet", {}).get("shopMoney", {}).get("currencyCode", "USD")
            fulfillment_status = order.get("displayFulfillmentStatus", "UNFULFILLED")
            financial_status = order.get("displayFinancialStatus", "PENDING")

            # Extract location (shipping_address can be None)
            shipping_address = order.get("shippingAddress") or {}
            latitude = shipping_address.get("latitude")
            longitude = shipping_address.get("longitude")

            # Count total items in order
            line_items = order.get("lineItems", {}).get("edges", [])
            order_total_items = sum(item["node"]["quantity"] for item in line_items)

            # Process each line item
            for line_item_edge in line_items:
                line_item = line_item_edge["node"]

                # Extract product details (product and variant can be None)
                product = line_item.get("product") or {}
                variant = line_item.get("variant") or {}

                product_id = int(product.get("legacyResourceId", 0)) if product.get("legacyResourceId") else None
                product_name = product.get("title", "Unknown Product")
                product_type = product.get("productType", "")
                variant_name = variant.get("title", "") if variant else ""
                sku = line_item.get("sku", "")
                quantity = line_item.get("quantity", 1)

                # Calculate line item sales and discount
                original_total = float(line_item.get("originalTotalSet", {}).get("shopMoney", {}).get("amount", 0))
                discounted_total = float(line_item.get("discountedTotalSet", {}).get("shopMoney", {}).get("amount", 0))
                line_item_discount = original_total - discounted_total
                line_item_sales = discounted_total

                # Build row
                row = {
                    # Order identifiers
                    "order_id": order_id,
                    "order_number": order_number,
                    "customer_id": customer_id,

                    # Time dimensions
                    "order_date": order_date,
                    "created_at": created_at,
                    "year": order_date.year,
                    "quarter": order_date.quarter,
                    "month": order_date.month,
                    "month_name": order_date.strftime("%B"),
                    "week": order_date.isocalendar()[1],
                    "day": order_date.day,
                    "week_day": order_date.strftime("%A"),

                    # Product details
                    "sku": sku,
                    "product_id": product_id,
                    "product_name": product_name,
                    "variant_name": variant_name,
                    "product_type": product_type,
                    "category": product_type,  # Use product_type as category

                    # Sales metrics
                    "quantity": quantity,
                    "line_item_sales": line_item_sales,
                    "line_item_discount": line_item_discount,
                    "line_item_refunds": 0.0,  # TODO: Fetch from refunds API if needed
                    "currency": currency,
                    "sales_channel": "online_store",  # Default for now

                    # Order-level enrichment
                    "latitude": latitude,
                    "longitude": longitude,
                    "fulfillment_status": fulfillment_status,
                    "financial_status": financial_status,
                    "order_total": total_price,
                    "order_total_items": order_total_items
                }

                rows.append(row)

        df = pd.DataFrame(rows)
        logger.info(f"✅ Transformed {len(df):,} line items from {len(orders):,} orders")

        return df

    def get_last_sync_date(self) -> Optional[datetime]:
        """Get the date of the last successful sync."""
        try:
            with self.postgres_engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT MAX(order_date) as last_date
                    FROM combined_sales
                """))
                row = result.fetchone()
                if row and row[0]:
                    last_date = row[0]
                    logger.info(f"Last sync date: {last_date}")
                    return last_date
                else:
                    logger.info("No previous sync found, will sync all data")
                    return None

        except Exception as e:
            logger.info("combined_sales table doesn't exist yet, will create it")
            return None

    def create_postgres_table(self):
        """Create combined_sales table in Postgres if it doesn't exist."""
        logger.info("Creating combined_sales table in Postgres...")

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS combined_sales (
            -- Primary keys
            id BIGSERIAL PRIMARY KEY,
            sync_timestamp TIMESTAMP DEFAULT NOW(),

            -- Order identifiers
            order_id BIGINT,
            order_number BIGINT,
            customer_id BIGINT NOT NULL,

            -- Time dimensions
            order_date TIMESTAMP NOT NULL,
            created_at TIMESTAMP,
            year INTEGER,
            quarter INTEGER,
            month INTEGER,
            month_name VARCHAR(20),
            week INTEGER,
            day INTEGER,
            week_day VARCHAR(20),

            -- Product details
            sku VARCHAR(255),
            product_id BIGINT,
            product_name TEXT,
            variant_name TEXT,
            product_type VARCHAR(255),
            category VARCHAR(255),

            -- Sales metrics (line-item level)
            quantity BIGINT,
            line_item_sales NUMERIC(18,2),
            line_item_discount NUMERIC(18,2),
            line_item_refunds NUMERIC(18,2),
            currency VARCHAR(10),
            sales_channel VARCHAR(255),

            -- Order-level enrichment
            latitude FLOAT,
            longitude FLOAT,
            fulfillment_status VARCHAR(100),
            financial_status VARCHAR(100),
            order_total NUMERIC(18,2),
            order_total_items BIGINT
        );

        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_combined_sales_customer ON combined_sales(customer_id);
        CREATE INDEX IF NOT EXISTS idx_combined_sales_order_date ON combined_sales(order_date);
        CREATE INDEX IF NOT EXISTS idx_combined_sales_product ON combined_sales(product_id);
        CREATE INDEX IF NOT EXISTS idx_combined_sales_category ON combined_sales(category);
        CREATE INDEX IF NOT EXISTS idx_combined_sales_sku ON combined_sales(sku);
        CREATE INDEX IF NOT EXISTS idx_combined_sales_order_id ON combined_sales(order_id);
        """

        try:
            with self.postgres_engine.connect() as conn:
                conn.execute(text(create_table_sql))
                conn.commit()

            logger.info("✅ Table and indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise

    def load_to_postgres(self, df: pd.DataFrame, dry_run: bool = False,
                        replace: bool = False) -> int:
        """
        Load data to Railway Postgres.

        Args:
            df: pandas DataFrame with sales data
            dry_run: If True, don't actually write data
            replace: If True, truncate table first (full sync)

        Returns:
            Number of rows loaded
        """
        if df.empty:
            logger.warning("No data to load")
            return 0

        if dry_run:
            logger.info(f"🔍 DRY RUN: Would load {len(df):,} rows")
            logger.info("\nSample data (first 3 rows):")
            print(df.head(3).to_string())
            return 0

        logger.info(f"Loading {len(df):,} rows to Postgres...")

        try:
            # Create table if needed
            self.create_postgres_table()

            # Truncate if full sync
            if replace:
                logger.info("Full sync mode: truncating existing data...")
                with self.postgres_engine.connect() as conn:
                    conn.execute(text("TRUNCATE TABLE combined_sales CASCADE"))
                    conn.commit()

            # Add sync timestamp
            df['sync_timestamp'] = datetime.now()

            # Load data in chunks
            chunk_size = 1000
            total_rows = 0

            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i + chunk_size]
                chunk.to_sql(
                    'combined_sales',
                    self.postgres_engine,
                    if_exists='append',
                    index=False,
                    method='multi'
                )
                total_rows += len(chunk)
                logger.info(f"Loaded {total_rows:,} / {len(df):,} rows...")

            logger.info(f"✅ Successfully loaded {total_rows:,} rows")
            return total_rows

        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise

    async def sync(self, start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   dry_run: bool = False,
                   incremental: bool = False,
                   limit: Optional[int] = None) -> int:
        """
        Run full sync process.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            dry_run: Preview mode, don't write data
            incremental: Only sync new data since last sync
            limit: Max orders (for testing)

        Returns:
            Number of rows synced
        """
        logger.info("=" * 70)
        logger.info("🔄 Starting Shopify → Postgres Sync")
        logger.info("=" * 70)

        try:
            # Connect to Postgres
            self.connect_postgres()

            # Handle incremental sync
            if incremental and not start_date:
                last_date = self.get_last_sync_date()
                if last_date:
                    # Start from day after last sync
                    start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                    logger.info(f"Incremental sync from: {start_date}")

            # Fetch orders from Shopify
            orders = await self.fetch_orders(start_date, end_date, limit)

            if not orders:
                logger.info("No new orders to sync")
                return 0

            # Transform to combined_sales format
            df = self.transform_to_combined_sales(orders)

            if df.empty:
                logger.info("No line items to sync (all orders skipped)")
                return 0

            # Load to Postgres
            replace = not incremental  # Full sync = replace
            rows_loaded = self.load_to_postgres(df, dry_run=dry_run, replace=replace)

            logger.info("=" * 70)
            logger.info(f"✅ Sync Complete! Processed {rows_loaded:,} line items from {len(orders):,} orders")
            logger.info("=" * 70)

            return rows_loaded

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise

        finally:
            # Cleanup connections
            await self.http_client.aclose()
            if self.postgres_engine:
                self.postgres_engine.dispose()


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Sync Shopify orders to Railway Postgres combined_sales table'
    )
    parser.add_argument('--full', action='store_true', help='Full sync (replace all data)')
    parser.add_argument('--incremental', action='store_true', help='Incremental sync (only new data)')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--dry-run', action='store_true', help='Preview mode (no data written)')
    parser.add_argument('--limit', type=int, help='Limit number of orders (for testing)')

    args = parser.parse_args()

    # Validate arguments
    if not args.full and not args.incremental and not args.start_date:
        parser.error("Must specify --full, --incremental, or --start-date")

    # Get credentials from environment
    shop_name = os.getenv("SHOPIFY_SHOP_NAME")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
    postgres_url = os.getenv("DATABASE_URL")

    # Validate credentials
    if not all([shop_name, access_token, postgres_url]):
        logger.error("Missing required environment variables:")
        logger.error("  SHOPIFY_SHOP_NAME (e.g., 'lindas-electric-quilters')")
        logger.error("  SHOPIFY_ACCESS_TOKEN (starts with shpat_)")
        logger.error("  DATABASE_URL (Railway Postgres)")
        sys.exit(1)

    # Create syncer
    syncer = ShopifyOrderSync(
        shop_name=shop_name,
        access_token=access_token,
        postgres_url=postgres_url
    )

    # Run sync
    try:
        await syncer.sync(
            start_date=args.start_date,
            end_date=args.end_date,
            dry_run=args.dry_run,
            incremental=args.incremental,
            limit=args.limit
        )

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
