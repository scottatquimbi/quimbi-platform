#!/usr/bin/env python3
"""
Clone staging database to production using Python
Avoids pg_dump version mismatch issues
"""

import sys
import os
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/Users/scottallen/unified-segmentation-ecommerce')

# Database credentials
STAGING = {
    'host': 'switchyard.proxy.rlwy.net',
    'port': 47164,
    'user': 'postgres',
    'password': 'JSKjhRNwAbpJWgRysXyFKNUcopesLIfq',
    'database': 'railway'
}

PRODUCTION = {
    'host': 'tramway.proxy.rlwy.net',
    'port': 53924,
    'user': 'postgres',
    'password': 'ovgyrwRFpdkonlIuQJdPjnXQnrMeGNVK',
    'database': 'railway'
}

def get_connection(config):
    """Create database connection"""
    return psycopg2.connect(**config)

def get_table_names(conn):
    """Get list of tables to copy"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename NOT LIKE 'pg_%'
            AND tablename NOT LIKE 'sql_%'
            ORDER BY tablename;
        """)
        return [row[0] for row in cur.fetchall()]

def get_table_row_count(conn, table):
    """Get row count for a table"""
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        return cur.fetchone()[0]

def copy_table(staging_conn, prod_conn, table_name, batch_size=1000):
    """Copy table data from staging to production"""
    print(f"\n📋 Copying table: {table_name}")

    # Get row count
    staging_count = get_table_row_count(staging_conn, table_name)
    print(f"   Rows in staging: {staging_count:,}")

    if staging_count == 0:
        print(f"   ⏭️  Skipping empty table")
        return

    with staging_conn.cursor() as staging_cur:
        with prod_conn.cursor() as prod_cur:
            # Get column names
            staging_cur.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """)
            columns = [row[0] for row in staging_cur.fetchall()]
            column_list = ', '.join([f'"{col}"' for col in columns])

            print(f"   Columns: {len(columns)}")

            # Clear production table
            print(f"   🗑️  Clearing production table...")
            prod_cur.execute(f'TRUNCATE TABLE "{table_name}" CASCADE')
            prod_conn.commit()

            # Copy data in batches
            print(f"   📥 Copying data in batches of {batch_size:,}...")

            staging_cur.execute(f'SELECT {column_list} FROM "{table_name}"')

            rows_copied = 0
            while True:
                rows = staging_cur.fetchmany(batch_size)
                if not rows:
                    break

                # Insert batch
                placeholders = ', '.join(['%s'] * len(columns))
                insert_query = f'INSERT INTO "{table_name}" ({column_list}) VALUES ({placeholders})'
                execute_values(prod_cur, insert_query, rows, page_size=batch_size)
                prod_conn.commit()

                rows_copied += len(rows)
                print(f"   ✓ {rows_copied:,} / {staging_count:,} rows copied", end='\r')

            print(f"   ✅ {rows_copied:,} rows copied successfully")

def main():
    print("=" * 80)
    print("CLONE STAGING DATABASE TO PRODUCTION")
    print("=" * 80)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Connect to databases
    print("Step 1: Connecting to databases...")
    print("-" * 80)

    try:
        print("Connecting to STAGING...")
        staging_conn = get_connection(STAGING)
        print("✅ Staging connected")

        print("Connecting to PRODUCTION...")
        prod_conn = get_connection(PRODUCTION)
        print("✅ Production connected")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    try:
        # Get list of tables
        print("\nStep 2: Getting table list...")
        print("-" * 80)
        tables = get_table_names(staging_conn)
        print(f"Found {len(tables)} tables to copy:")
        for table in tables:
            count = get_table_row_count(staging_conn, table)
            print(f"  - {table}: {count:,} rows")

        # Copy each table
        print("\nStep 3: Copying tables...")
        print("-" * 80)

        for i, table in enumerate(tables, 1):
            print(f"\n[{i}/{len(tables)}] Processing {table}...")
            try:
                copy_table(staging_conn, prod_conn, table)
            except Exception as e:
                print(f"   ❌ Error copying {table}: {e}")
                print(f"   Continuing with next table...")

        # Verify
        print("\nStep 4: Verifying production database...")
        print("-" * 80)

        for table in tables:
            prod_count = get_table_row_count(prod_conn, table)
            staging_count = get_table_row_count(staging_conn, table)

            if prod_count == staging_count:
                print(f"✅ {table}: {prod_count:,} rows (match)")
            else:
                print(f"⚠️  {table}: {prod_count:,} rows (staging had {staging_count:,})")

        print("\n" + "=" * 80)
        print("CLONE COMPLETE!")
        print("=" * 80)
        print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    finally:
        staging_conn.close()
        prod_conn.close()
        print("\n🔌 Database connections closed")

if __name__ == '__main__':
    main()
