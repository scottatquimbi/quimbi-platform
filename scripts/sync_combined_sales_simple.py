#!/usr/bin/env python3
"""
Sync Combined Sales from Azure SQL to Railway Postgres.

SIMPLE VERSION: Just syncs the pre-combined vw_Combined_Sales view from Azure SQL.

Prerequisites:
1. Run create_combined_sales_view.sql in Azure SQL to create the view
2. Set environment variables for Azure SQL and Postgres credentials

Usage:
    # Full sync (replace all data)
    python scripts/sync_combined_sales_simple.py --full

    # Incremental sync (only new records)
    python scripts/sync_combined_sales_simple.py --incremental

    # Date range
    python scripts/sync_combined_sales_simple.py --start-date 2024-01-01

    # Dry run
    python scripts/sync_combined_sales_simple.py --dry-run --limit 100
"""

import os
import sys
from datetime import datetime, timedelta
import logging

import pandas as pd
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CombinedSalesSync:
    """Sync combined sales data from Azure SQL to Railway Postgres."""

    def __init__(self, azure_server, azure_database, azure_username,
                 azure_password, postgres_url):
        """Initialize sync configuration."""
        self.azure_server = azure_server
        self.azure_database = azure_database
        self.azure_username = azure_username
        self.azure_password = azure_password
        self.postgres_url = postgres_url

        self.azure_conn = None
        self.postgres_engine = None

    def connect_azure_sql(self):
        """Connect to Azure SQL Server using pymssql."""
        try:
            import pymssql

            logger.info(f"Connecting to Azure SQL: {self.azure_server}/{self.azure_database}")

            self.azure_conn = pymssql.connect(
                server=self.azure_server,
                database=self.azure_database,
                user=self.azure_username,
                password=self.azure_password,
                port=1433,
                timeout=30,
                as_dict=True
            )

            logger.info("✅ Connected to Azure SQL Server")
            return self.azure_conn

        except ImportError:
            logger.error("pymssql not installed. Installing...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pymssql==2.2.11"])
            import pymssql
            return self.connect_azure_sql()

        except Exception as e:
            logger.error(f"Failed to connect to Azure SQL: {e}")
            raise

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

    def fetch_combined_sales(self, start_date=None, end_date=None, limit=None):
        """
        Fetch combined sales data from Azure SQL.

        Performs JOIN between Product_Sales_Order and SALES_DATA_ORDER.
        No modifications to source database - ETL happens here.

        Args:
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)
            limit: Maximum rows to fetch (for testing)

        Returns:
            pandas.DataFrame with combined sales data
        """
        logger.info("Fetching and combining sales data from Azure SQL...")

        # Build JOIN query - ETL happens here, not in source database
        query = """
        SELECT
            -- Order identifiers
            p.OrderID as order_id,
            p.OrderNumber as order_number,
            p.Customer_ID as customer_id,

            -- Time dimensions
            p.Date as order_date,
            p.CreatedAt as created_at,
            p.Year as year,
            p.Quarter as quarter,
            p.Month as month,
            p.MonthName as month_name,
            p.Week as week,
            p.Day as day,
            p.WeekDay as week_day,

            -- Product details
            p.Sku as sku,
            p.ProductId as product_id,
            p.Title as product_name,
            p.VariantTitle as variant_name,
            p.ProductType as product_type,
            p.Category as category,

            -- Sales metrics
            p.QTY as quantity,
            p.Sales as line_item_sales,
            p.TotalDiscount as line_item_discount,
            p.Refunds as line_item_refunds,
            p.Currency as currency,
            p.Source as sales_channel,

            -- Order-level enrichment
            s.Latitude as latitude,
            s.Longitude as longitude,
            s.FulfillmentStatus as fulfillment_status,
            s.FinancialStatus as financial_status,
            s.TotalPrice as order_total,
            s.ItemQTY as order_total_items

        FROM Product_Sales_Order p
        LEFT JOIN SALES_DATA_ORDER s ON p.OrderID = s.Id
        """

        # Add date filters
        where_clauses = []
        if start_date:
            where_clauses.append(f"p.Date >= '{start_date}'")
        if end_date:
            where_clauses.append(f"p.Date <= '{end_date}'")

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Order by date
        query += " ORDER BY p.Date"

        # Add limit for testing
        if limit:
            # Insert TOP clause after SELECT
            query = query.replace("SELECT", f"SELECT TOP {limit}", 1)

        logger.info(f"Query date range: {start_date or 'ALL'} to {end_date or 'ALL'}")
        if limit:
            logger.info(f"Limit: {limit} rows")

        # Execute query
        try:
            cursor = self.azure_conn.cursor(as_dict=True)
            cursor.execute(query)
            rows = cursor.fetchall()

            df = pd.DataFrame(rows)
            logger.info(f"✅ Fetched {len(df):,} rows from Azure SQL")

            # Convert date columns
            if not df.empty:
                df['order_date'] = pd.to_datetime(df['order_date'])
                if 'created_at' in df.columns and df['created_at'].notna().any():
                    df['created_at'] = pd.to_datetime(df['created_at'])

            return df

        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            raise

    def get_last_sync_date(self):
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

    def load_to_postgres(self, df, dry_run=False, replace=False):
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

    def sync(self, start_date=None, end_date=None, dry_run=False,
             incremental=False, limit=None):
        """
        Run full sync process.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            dry_run: Preview mode, don't write data
            incremental: Only sync new data since last sync
            limit: Max rows (for testing)

        Returns:
            Number of rows synced
        """
        logger.info("=" * 70)
        logger.info("🔄 Starting Combined Sales Sync")
        logger.info("=" * 70)

        try:
            # Connect to databases
            self.connect_azure_sql()
            self.connect_postgres()

            # Handle incremental sync
            if incremental and not start_date:
                last_date = self.get_last_sync_date()
                if last_date:
                    # Start from day after last sync
                    start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                    logger.info(f"Incremental sync from: {start_date}")

            # Fetch data from Azure
            df = self.fetch_combined_sales(start_date, end_date, limit)

            if df.empty:
                logger.info("No new data to sync")
                return 0

            # Load to Postgres
            replace = not incremental  # Full sync = replace
            rows_loaded = self.load_to_postgres(df, dry_run=dry_run, replace=replace)

            logger.info("=" * 70)
            logger.info(f"✅ Sync Complete! Processed {rows_loaded:,} rows")
            logger.info("=" * 70)

            return rows_loaded

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise

        finally:
            # Cleanup connections
            if self.azure_conn:
                self.azure_conn.close()
            if self.postgres_engine:
                self.postgres_engine.dispose()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Sync combined sales data from Azure SQL to Railway Postgres'
    )
    parser.add_argument('--full', action='store_true', help='Full sync (replace all data)')
    parser.add_argument('--incremental', action='store_true', help='Incremental sync (only new data)')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--dry-run', action='store_true', help='Preview mode (no data written)')
    parser.add_argument('--limit', type=int, help='Limit number of rows (for testing)')

    args = parser.parse_args()

    # Validate arguments
    if not args.full and not args.incremental and not args.start_date:
        parser.error("Must specify --full, --incremental, or --start-date")

    # Get credentials from environment
    azure_server = os.getenv("AZURE_SQL_SERVER", "linda.database.windows.net")
    azure_database = os.getenv("AZURE_SQL_DATABASE", "Shopfiy")
    azure_username = os.getenv("AZURE_SQL_USERNAME")
    azure_password = os.getenv("AZURE_SQL_PASSWORD")
    postgres_url = os.getenv("DATABASE_URL")

    # Validate credentials
    if not all([azure_username, azure_password, postgres_url]):
        logger.error("Missing required environment variables:")
        logger.error("  AZURE_SQL_USERNAME")
        logger.error("  AZURE_SQL_PASSWORD")
        logger.error("  DATABASE_URL")
        sys.exit(1)

    # Create syncer
    syncer = CombinedSalesSync(
        azure_server=azure_server,
        azure_database=azure_database,
        azure_username=azure_username,
        azure_password=azure_password,
        postgres_url=postgres_url
    )

    # Run sync
    try:
        syncer.sync(
            start_date=args.start_date,
            end_date=args.end_date,
            dry_run=args.dry_run,
            incremental=args.incremental,
            limit=args.limit
        )

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
