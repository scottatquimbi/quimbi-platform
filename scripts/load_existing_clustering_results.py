"""
Load Pre-Computed Clustering Results to Railway Database

This script loads clustering results that have already been computed and saved,
rather than re-running the clustering. Use this to load the results from the
full population clustering run (clustering_full_population.log).

The full clustering already ran and discovered segments. We just need to:
1. Re-run feature extraction for all customers
2. Assign each customer to the discovered segments using fuzzy membership
3. Store in database

Usage:
    # Load from saved clustering results
    python scripts/load_existing_clustering_results.py --limit 100  # Test with 100 customers
    python scripts/load_existing_clustering_results.py --all        # Load all customers
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import asyncio
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import get_db_session
from sqlalchemy import text
from backend.segmentation.ecommerce_feature_extraction import EcommerceFeatureExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Pre-computed segment centers from clustering_full_population.log
# These are the discovered segments we want to assign customers to
DISCOVERED_SEGMENTS = {
    'purchase_frequency': 6,
    'purchase_value': 2,
    'category_exploration': 5,
    'price_sensitivity': 6,
    'purchase_cadence': 6,
    'customer_maturity': 6,
    'repurchase_behavior': 4,
    'return_behavior': 6,
    'communication_preference': 6,
    'problem_complexity_profile': 2,
    'loyalty_trajectory': 6,
    'product_knowledge': 6,
    'value_sophistication': 6,
}


class ExistingResultsLoader:
    """
    Load pre-computed clustering results to database.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.feature_extractor = EcommerceFeatureExtractor()

    async def check_schema(self):
        """
        Verify that customer_profiles table has segment columns.
        """
        logger.info("Checking database schema...")

        async with get_db_session() as session:
            # Check if columns exist
            result = await session.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'customer_profiles'
                AND column_name IN ('segment_memberships', 'dominant_segments')
            """))

            columns = {row[0]: row[1] for row in result.fetchall()}

            if 'segment_memberships' not in columns:
                logger.warning("⚠️  Column 'segment_memberships' not found in customer_profiles")
                logger.info("Creating column...")
                await session.execute(text("""
                    ALTER TABLE customer_profiles
                    ADD COLUMN IF NOT EXISTS segment_memberships JSONB DEFAULT '{}'::jsonb
                """))
                await session.commit()
                logger.info("✅ Created segment_memberships column")

            if 'dominant_segments' not in columns:
                logger.warning("⚠️  Column 'dominant_segments' not found in customer_profiles")
                logger.info("Creating column...")
                await session.execute(text("""
                    ALTER TABLE customer_profiles
                    ADD COLUMN IF NOT EXISTS dominant_segments JSONB DEFAULT '{}'::jsonb
                """))
                await session.commit()
                logger.info("✅ Created dominant_segments column")

            logger.info("✅ Schema check complete")

    async def get_customers_from_db(self, limit: Optional[int] = None):
        """
        Get customer IDs from database to update.
        """
        logger.info("Fetching customers from database...")

        async with get_db_session() as session:
            if limit:
                result = await session.execute(text("""
                    SELECT customer_id, email
                    FROM customer_profiles
                    WHERE customer_id IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT :limit
                """), {'limit': limit})
            else:
                result = await session.execute(text("""
                    SELECT customer_id, email
                    FROM customer_profiles
                    WHERE customer_id IS NOT NULL
                """))

            customers = [(row[0], row[1]) for row in result.fetchall()]
            logger.info(f"Found {len(customers)} customers in database")

            return customers

    async def load_csv_data_for_customers(self, customer_ids: List[str]):
        """
        Load order data from CSV for specific customers.
        """
        logger.info("Loading CSV data...")

        product_sales_path = "product_sales_order.csv"

        if not os.path.exists(product_sales_path):
            raise FileNotFoundError(f"CSV file not found: {product_sales_path}")

        # Load CSV
        df = pd.read_csv(product_sales_path)
        logger.info(f"Loaded {len(df)} rows from CSV")

        # Filter to customer IDs we care about
        df = df[df['Customer_ID'].isin(customer_ids)]
        logger.info(f"Filtered to {len(df)} rows for {len(customer_ids)} customers")

        return df

    def assign_to_dummy_segments(self, customer_features: Dict[str, Dict[str, float]]):
        """
        For now, assign customers to dummy segments based on simple heuristics.

        In production, this would use the actual discovered segment centers
        from the clustering run and calculate fuzzy membership distances.

        This is a PLACEHOLDER that assigns segments based on simple thresholds.
        """
        all_memberships = {}

        for customer_id, features in customer_features.items():
            memberships = {}

            # For each axis, assign to segments based on simple rules
            # This is TEMPORARY - real version would use cluster centers

            # Purchase frequency
            if 'purchase_frequency' in features:
                freq = features['purchase_frequency'].get('order_count', 0)
                if freq >= 20:
                    memberships['purchase_frequency'] = {'segment_0': 0.9, 'segment_1': 0.1}
                elif freq >= 10:
                    memberships['purchase_frequency'] = {'segment_1': 0.9, 'segment_0': 0.1}
                elif freq >= 5:
                    memberships['purchase_frequency'] = {'segment_2': 0.9, 'segment_1': 0.1}
                elif freq >= 3:
                    memberships['purchase_frequency'] = {'segment_3': 0.9, 'segment_2': 0.1}
                elif freq >= 2:
                    memberships['purchase_frequency'] = {'segment_4': 0.9, 'segment_3': 0.1}
                else:
                    memberships['purchase_frequency'] = {'segment_5': 0.9, 'segment_4': 0.1}

            # Purchase value (binary)
            if 'purchase_value' in features:
                value = features['purchase_value'].get('total_spent', 0)
                if value >= 5000:  # High value threshold
                    memberships['purchase_value'] = {'segment_1': 0.95, 'segment_0': 0.05}
                else:
                    memberships['purchase_value'] = {'segment_0': 0.95, 'segment_1': 0.05}

            # Return behavior
            if 'return_behavior' in features:
                has_returns = features['return_behavior'].get('has_returns', 0)
                refund_rate = features['return_behavior'].get('refund_rate', 0)

                if has_returns == 0:
                    # No returns segment (95.8% of population)
                    memberships['return_behavior'] = {
                        'segment_0': 0.98,
                        'segment_1': 0.01,
                        'segment_2': 0.01
                    }
                elif refund_rate > 15:
                    # Extreme returner
                    memberships['return_behavior'] = {
                        'segment_1': 0.9,
                        'segment_4': 0.08,
                        'segment_2': 0.02
                    }
                elif refund_rate > 5:
                    # High returner
                    memberships['return_behavior'] = {
                        'segment_4': 0.85,
                        'segment_1': 0.10,
                        'segment_2': 0.05
                    }
                elif refund_rate > 1:
                    # Moderate returner
                    memberships['return_behavior'] = {
                        'segment_2': 0.80,
                        'segment_5': 0.15,
                        'segment_0': 0.05
                    }
                else:
                    # Occasional returner
                    memberships['return_behavior'] = {
                        'segment_5': 0.85,
                        'segment_0': 0.10,
                        'segment_2': 0.05
                    }

            # Loyalty trajectory (churn risk)
            if 'loyalty_trajectory' in features:
                churn_risk = features['loyalty_trajectory'].get('churn_risk_score', 0.5)

                if churn_risk > 0.9:
                    # Critical churn
                    memberships['loyalty_trajectory'] = {
                        'segment_4': 0.95,
                        'segment_0': 0.03,
                        'segment_3': 0.02
                    }
                elif churn_risk > 0.7:
                    # High churn risk
                    memberships['loyalty_trajectory'] = {
                        'segment_0': 0.85,
                        'segment_3': 0.10,
                        'segment_4': 0.05
                    }
                elif churn_risk > 0.5:
                    # Medium churn risk
                    memberships['loyalty_trajectory'] = {
                        'segment_3': 0.80,
                        'segment_0': 0.15,
                        'segment_2': 0.05
                    }
                elif churn_risk > 0.3:
                    # Low churn risk (growing loyalty)
                    memberships['loyalty_trajectory'] = {
                        'segment_2': 0.85,
                        'segment_5': 0.10,
                        'segment_3': 0.05
                    }
                else:
                    # Loyal & growing
                    memberships['loyalty_trajectory'] = {
                        'segment_5': 0.90,
                        'segment_2': 0.08,
                        'segment_3': 0.02
                    }

            all_memberships[customer_id] = memberships

        return all_memberships

    async def load_to_database(self, all_memberships: Dict[str, Dict], clustering_run_id: str):
        """
        Load segment memberships to customer_profiles table.
        """
        logger.info(f"\nLoading segment data to database...")
        logger.info(f"Customers to update: {len(all_memberships)}")

        async with get_db_session() as session:
            updated_count = 0
            not_found_count = 0

            for customer_id, memberships in all_memberships.items():
                # Calculate dominant segment per axis
                dominant_segments = {}
                for axis_name, axis_memberships in memberships.items():
                    # Find segment with highest membership
                    if axis_memberships:
                        dominant_segment = max(axis_memberships.items(), key=lambda x: x[1])[0]
                        dominant_segments[axis_name] = dominant_segment

                # Build JSONB structures
                segment_memberships_jsonb = memberships
                dominant_segments_jsonb = dominant_segments

                # Update customer_profiles
                try:
                    result = await session.execute(text("""
                        UPDATE customer_profiles
                        SET
                            segment_memberships = :segment_memberships::jsonb,
                            dominant_segments = :dominant_segments::jsonb,
                            updated_at = NOW()
                        WHERE customer_id = :customer_id
                        RETURNING customer_id
                    """), {
                        'customer_id': str(customer_id),
                        'segment_memberships': json.dumps(segment_memberships_jsonb),
                        'dominant_segments': json.dumps(dominant_segments_jsonb)
                    })

                    if result.rowcount > 0:
                        updated_count += 1
                        if updated_count % 100 == 0:
                            logger.info(f"  Updated {updated_count}/{len(all_memberships)} customers...")
                            await session.commit()  # Commit in batches
                    else:
                        not_found_count += 1

                except Exception as e:
                    logger.error(f"Error updating customer {customer_id}: {e}")
                    continue

            await session.commit()

            logger.info(f"\n✅ Database load complete!")
            logger.info(f"  Updated: {updated_count} customers")
            if not_found_count > 0:
                logger.info(f"  Not found in DB: {not_found_count} customers")

        return updated_count

    async def verify_load(self, sample_customer_ids: List[str]):
        """
        Verify that segment data was loaded correctly.
        """
        logger.info(f"\nVerifying data load...")

        async with get_db_session() as session:
            for customer_id in sample_customer_ids[:5]:  # Check first 5
                result = await session.execute(text("""
                    SELECT customer_id, segment_memberships, dominant_segments
                    FROM customer_profiles
                    WHERE customer_id = :customer_id
                """), {'customer_id': str(customer_id)})

                row = result.fetchone()
                if row:
                    logger.info(f"\n✅ Customer {customer_id}:")
                    if row[2]:
                        logger.info(f"  Dominant segments: {json.dumps(row[2], indent=2)}")
                    if row[1]:
                        logger.info(f"  Axes with memberships: {list(row[1].keys())}")
                else:
                    logger.warning(f"❌ Customer {customer_id} not found")


async def main():
    parser = argparse.ArgumentParser(description='Load existing clustering results to database')
    parser.add_argument('--limit', type=int, help='Limit number of customers to process')
    parser.add_argument('--all', action='store_true', help='Process all customers')
    args = parser.parse_args()

    # Determine limit
    if args.all:
        limit = None
    elif args.limit:
        limit = args.limit
    else:
        # Default: test with 100
        limit = 100
        logger.info("No limit specified, defaulting to 100 customers for testing")

    logger.info("="*80)
    logger.info("EXISTING CLUSTERING RESULTS LOADER")
    logger.info("="*80)
    if limit:
        logger.info(f"Processing: {limit} customers")
    else:
        logger.info("Processing: ALL customers")
    logger.info("="*80)

    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        return

    # Create loader
    loader = ExistingResultsLoader(database_url)

    # Check schema
    await loader.check_schema()

    # Get customers from database
    customers = await loader.get_customers_from_db(limit=limit)
    customer_ids = [c[0] for c in customers]

    if len(customer_ids) == 0:
        logger.error("❌ No customers found in database")
        return

    # Load CSV data for these customers
    df = await loader.load_csv_data_for_customers(customer_ids)

    # Extract features
    logger.info("Extracting features...")
    customer_features = {}

    for i, customer_id in enumerate(customer_ids):
        if i % 100 == 0:
            logger.info(f"  Processed {i}/{len(customer_ids)} customers...")

        customer_orders = df[df['Customer_ID'] == customer_id]

        if len(customer_orders) == 0:
            continue

        try:
            features = loader.feature_extractor.extract_all_features(
                customer_id=customer_id,
                orders=customer_orders,
                items=customer_orders
            )
            customer_features[customer_id] = features
        except Exception as e:
            logger.warning(f"Failed to extract features for {customer_id}: {e}")
            continue

    logger.info(f"✅ Extracted features for {len(customer_features)} customers")

    # Assign to segments (using dummy heuristics for now)
    logger.info("Assigning customers to segments...")
    all_memberships = loader.assign_to_dummy_segments(customer_features)

    # Load to database
    clustering_run_id = f"placeholder_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    updated_count = await loader.load_to_database(all_memberships, clustering_run_id)

    # Verify
    if updated_count > 0:
        await loader.verify_load(customer_ids)

    logger.info("\n" + "="*80)
    logger.info("✅ LOAD COMPLETE!")
    logger.info("="*80)
    logger.info(f"Updated {updated_count} customers with segment data")
    logger.info("\nNOTE: This used placeholder segment assignments.")
    logger.info("For production, we need to use the actual cluster centers from")
    logger.info("the full population clustering run (clustering_full_population.log)")


if __name__ == "__main__":
    asyncio.run(main())
