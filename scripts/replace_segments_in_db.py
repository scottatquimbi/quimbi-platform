"""
Replace Existing Segment Data with New 13-Axis Clustering

This script:
1. Gets customer IDs from existing customer_profiles table
2. Loads order data from CSV for those customers
3. Runs feature extraction and clustering assignment
4. Updates segment_memberships and dominant_segments columns
5. Replaces the old 8-axis system with new 13-axis system

Usage:
    # Test with 100 customers
    python scripts/replace_segments_in_db.py --limit 100

    # Load all customers (recommended to run in batches)
    python scripts/replace_segments_in_db.py --batch 1000

    # Load specific range
    python scripts/replace_segments_in_db.py --offset 0 --limit 10000
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import asyncio
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import get_db_session
from sqlalchemy import text
from backend.segmentation.ecommerce_feature_extraction import EcommerceFeatureExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SegmentReplacer:
    """Replace existing segment data with new 13-axis clustering."""

    def __init__(self):
        self.feature_extractor = EcommerceFeatureExtractor()
        self.axes = [
            'purchase_frequency', 'purchase_value', 'category_exploration',
            'price_sensitivity', 'purchase_cadence', 'customer_maturity',
            'repurchase_behavior', 'return_behavior', 'communication_preference',
            'problem_complexity_profile', 'loyalty_trajectory', 'product_knowledge',
            'value_sophistication'
        ]

    async def get_customers_batch(self, offset: int = 0, limit: int = 1000):
        """Get batch of customer IDs from database."""
        logger.info(f"Fetching customers (offset={offset}, limit={limit})...")

        async with get_db_session() as session:
            result = await session.execute(text("""
                SELECT customer_id
                FROM customer_profiles
                WHERE store_id = 'linda_quilting'
                ORDER BY customer_id
                OFFSET :offset
                LIMIT :limit
            """), {'offset': offset, 'limit': limit})

            customer_ids = [row[0] for row in result.fetchall()]
            logger.info(f"Found {len(customer_ids)} customers")
            return customer_ids

    async def count_total_customers(self):
        """Count total customers to process."""
        async with get_db_session() as session:
            result = await session.execute(text("""
                SELECT COUNT(*)
                FROM customer_profiles
                WHERE store_id = 'linda_quilting'
            """))
            count = result.scalar()
            logger.info(f"Total customers in database: {count}")
            return count

    def load_csv_for_customers(self, customer_ids: List[str]) -> pd.DataFrame:
        """Load CSV data for specific customers."""
        logger.info("Loading CSV data...")

        product_sales_path = "product_sales_order.csv"
        if not os.path.exists(product_sales_path):
            raise FileNotFoundError(f"CSV not found: {product_sales_path}")

        # Load CSV (chunked for memory efficiency)
        logger.info(f"Reading CSV...")
        df = pd.read_csv(product_sales_path)

        # Filter to our customers
        logger.info(f"Filtering to {len(customer_ids)} customers...")
        df_filtered = df[df['Customer_ID'].astype(str).isin([str(cid) for cid in customer_ids])]

        logger.info(f"Loaded {len(df_filtered)} rows for {len(customer_ids)} customers")
        return df_filtered

    def assign_to_placeholder_segments(self, customer_features: Dict[str, Dict[str, float]]) -> Dict[str, Dict]:
        """
        Assign customers to segments using simple heuristics.

        This is a PLACEHOLDER that will be replaced with actual cluster center assignments
        once we integrate the full clustering results.
        """
        all_memberships = {}

        for customer_id, features in customer_features.items():
            memberships = {}

            # Purchase frequency (6 segments)
            if 'purchase_frequency' in features:
                freq = features['purchase_frequency'].get('order_count', 0)
                if freq >= 50:
                    memberships['purchase_frequency'] = {'segment_0': 0.95, 'segment_1': 0.03, 'segment_2': 0.02}
                elif freq >= 20:
                    memberships['purchase_frequency'] = {'segment_1': 0.90, 'segment_0': 0.07, 'segment_2': 0.03}
                elif freq >= 10:
                    memberships['purchase_frequency'] = {'segment_2': 0.85, 'segment_1': 0.10, 'segment_3': 0.05}
                elif freq >= 5:
                    memberships['purchase_frequency'] = {'segment_3': 0.80, 'segment_2': 0.15, 'segment_4': 0.05}
                elif freq >= 2:
                    memberships['purchase_frequency'] = {'segment_4': 0.85, 'segment_3': 0.10, 'segment_5': 0.05}
                else:
                    memberships['purchase_frequency'] = {'segment_5': 0.90, 'segment_4': 0.08, 'segment_3': 0.02}

            # Purchase value (2 segments - binary high/low)
            if 'purchase_value' in features:
                value = features['purchase_value'].get('total_spent', 0)
                if value >= 5000:  # VIP threshold
                    memberships['purchase_value'] = {'segment_1': 0.98, 'segment_0': 0.02}
                else:
                    memberships['purchase_value'] = {'segment_0': 0.98, 'segment_1': 0.02}

            # Return behavior (6 segments)
            if 'return_behavior' in features:
                has_returns = features['return_behavior'].get('has_returns', 0)
                refund_rate = features['return_behavior'].get('refund_rate', 0)

                if has_returns == 0:
                    # No returns segment (95.8% of population)
                    memberships['return_behavior'] = {
                        'segment_0': 0.98, 'segment_5': 0.01, 'segment_2': 0.01
                    }
                elif refund_rate > 20:
                    # Extreme returner
                    memberships['return_behavior'] = {
                        'segment_1': 0.90, 'segment_4': 0.08, 'segment_2': 0.02
                    }
                elif refund_rate > 10:
                    # Serial returner
                    memberships['return_behavior'] = {
                        'segment_4': 0.85, 'segment_1': 0.10, 'segment_2': 0.05
                    }
                elif refund_rate > 2:
                    # Frequent returner
                    memberships['return_behavior'] = {
                        'segment_2': 0.80, 'segment_5': 0.15, 'segment_0': 0.05
                    }
                else:
                    # Occasional returner
                    memberships['return_behavior'] = {
                        'segment_5': 0.85, 'segment_0': 0.10, 'segment_2': 0.05
                    }

            # Loyalty trajectory (6 segments) - CRITICAL for churn
            if 'loyalty_trajectory' in features:
                churn_risk = features['loyalty_trajectory'].get('churn_risk_score', 0.5)

                if churn_risk > 0.95:
                    # Critical churn (segment_4 from log analysis)
                    memberships['loyalty_trajectory'] = {
                        'segment_4': 0.95, 'segment_0': 0.03, 'segment_3': 0.02
                    }
                elif churn_risk > 0.7:
                    # High churn risk (segment_0 - 57.1% of multi-order customers)
                    memberships['loyalty_trajectory'] = {
                        'segment_0': 0.85, 'segment_3': 0.10, 'segment_4': 0.05
                    }
                elif churn_risk > 0.5:
                    # Declining (segment_3)
                    memberships['loyalty_trajectory'] = {
                        'segment_3': 0.80, 'segment_0': 0.15, 'segment_2': 0.05
                    }
                elif churn_risk > 0.35:
                    # Growing loyalty (segment_2)
                    memberships['loyalty_trajectory'] = {
                        'segment_2': 0.85, 'segment_5': 0.10, 'segment_3': 0.05
                    }
                else:
                    # Loyal & growing (segment_5 - gold standard)
                    memberships['loyalty_trajectory'] = {
                        'segment_5': 0.90, 'segment_2': 0.08, 'segment_3': 0.02
                    }

            # Communication preference (6 segments)
            if 'communication_preference' in features:
                channel_diversity = features['communication_preference'].get('channel_diversity', 1.0)

                if channel_diversity > 3:
                    # Multi-channel (segment_1)
                    memberships['communication_preference'] = {
                        'segment_1': 0.85, 'segment_2': 0.10, 'segment_0': 0.05
                    }
                else:
                    # Single channel (segment_2 - 43.2% of population)
                    memberships['communication_preference'] = {
                        'segment_2': 0.80, 'segment_0': 0.15, 'segment_1': 0.05
                    }

            # Problem complexity (2 segments - simple binary)
            if 'problem_complexity_profile' in features:
                refund_rate = features.get('return_behavior', {}).get('refund_rate', 0)

                if refund_rate > 2:
                    # High complexity
                    memberships['problem_complexity_profile'] = {
                        'segment_1': 0.90, 'segment_0': 0.10
                    }
                else:
                    # Low complexity
                    memberships['problem_complexity_profile'] = {
                        'segment_0': 0.90, 'segment_1': 0.10
                    }

            # Add remaining axes with default assignments
            for axis in self.axes:
                if axis not in memberships:
                    # Default: assign to segment_0 with high confidence
                    memberships[axis] = {'segment_0': 0.85, 'segment_1': 0.10, 'segment_2': 0.05}

            all_memberships[customer_id] = memberships

        return all_memberships

    async def update_database_batch(
        self,
        all_memberships: Dict[str, Dict],
        batch_name: str
    ) -> int:
        """Update database with new segment data."""
        logger.info(f"Updating database ({batch_name})...")

        updated_count = 0
        failed_count = 0

        async with get_db_session() as session:
            for customer_id, memberships in all_memberships.items():
                # Calculate dominant segments
                dominant_segments = {}
                for axis_name, axis_memberships in memberships.items():
                    if axis_memberships:
                        dominant_segment = max(axis_memberships.items(), key=lambda x: x[1])[0]
                        dominant_segments[axis_name] = dominant_segment

                try:
                    result = await session.execute(text("""
                        UPDATE customer_profiles
                        SET
                            segment_memberships = :segment_memberships::jsonb,
                            dominant_segments = :dominant_segments::jsonb,
                            last_updated = NOW()
                        WHERE customer_id = :customer_id
                        RETURNING customer_id
                    """), {
                        'customer_id': str(customer_id),
                        'segment_memberships': json.dumps(memberships),
                        'dominant_segments': json.dumps(dominant_segments)
                    })

                    if result.rowcount > 0:
                        updated_count += 1
                    else:
                        failed_count += 1
                        logger.warning(f"Customer {customer_id} not found in database")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error updating customer {customer_id}: {e}")

            # Commit after each batch
            await session.commit()
            logger.info(f"✅ Batch committed: {updated_count} updated, {failed_count} failed")

        return updated_count

    async def verify_sample(self, customer_ids: List[str]):
        """Verify updates by sampling a few customers."""
        logger.info(f"\nVerifying updates...")

        async with get_db_session() as session:
            for customer_id in customer_ids[:3]:
                result = await session.execute(text("""
                    SELECT customer_id, dominant_segments, segment_memberships
                    FROM customer_profiles
                    WHERE customer_id = :customer_id
                """), {'customer_id': str(customer_id)})

                row = result.fetchone()
                if row:
                    logger.info(f"\n✅ Customer {customer_id}:")
                    logger.info(f"  Dominant: {json.dumps(row[1], indent=2)}")
                    if 'loyalty_trajectory' in row[2]:
                        logger.info(f"  Churn segment: {row[2]['loyalty_trajectory']}")


async def main():
    parser = argparse.ArgumentParser(description='Replace segment data in customer_profiles')
    parser.add_argument('--limit', type=int, help='Number of customers to process')
    parser.add_argument('--offset', type=int, default=0, help='Starting offset')
    parser.add_argument('--batch', type=int, default=1000, help='Batch size for processing')
    parser.add_argument('--all', action='store_true', help='Process all customers in batches')
    args = parser.parse_args()

    logger.info("="*80)
    logger.info("SEGMENT DATA REPLACEMENT - NEW 13-AXIS SYSTEM")
    logger.info("="*80)

    # Check DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL not set")
        return

    replacer = SegmentReplacer()

    # Determine processing mode
    if args.all:
        # Process all customers in batches
        total_customers = await replacer.count_total_customers()
        logger.info(f"Processing ALL {total_customers} customers in batches of {args.batch}")

        offset = args.offset
        total_updated = 0

        while offset < total_customers:
            logger.info(f"\n{'='*80}")
            logger.info(f"BATCH: {offset} to {offset + args.batch}")
            logger.info(f"{'='*80}")

            # Get batch of customer IDs
            customer_ids = await replacer.get_customers_batch(offset, args.batch)
            if not customer_ids:
                break

            # Load CSV data
            df = replacer.load_csv_for_customers(customer_ids)

            # Extract features
            logger.info("Extracting features...")
            customer_features = {}
            for i, customer_id in enumerate(customer_ids):
                if i % 100 == 0 and i > 0:
                    logger.info(f"  Processed {i}/{len(customer_ids)} customers...")

                customer_orders = df[df['Customer_ID'].astype(str) == str(customer_id)]
                if len(customer_orders) == 0:
                    continue

                try:
                    features = replacer.feature_extractor.extract_all_features(
                        customer_id=customer_id,
                        orders=customer_orders,
                        items=customer_orders
                    )
                    customer_features[customer_id] = features
                except Exception as e:
                    logger.warning(f"Failed to extract features for {customer_id}: {e}")

            logger.info(f"✅ Extracted features for {len(customer_features)} customers")

            # Assign to segments
            logger.info("Assigning to segments...")
            all_memberships = replacer.assign_to_placeholder_segments(customer_features)

            # Update database
            batch_updated = await replacer.update_database_batch(
                all_memberships,
                f"batch_{offset}_{offset+args.batch}"
            )
            total_updated += batch_updated

            # Move to next batch
            offset += args.batch
            logger.info(f"Progress: {offset}/{total_customers} customers ({offset/total_customers*100:.1f}%)")

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ ALL BATCHES COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Total updated: {total_updated}/{total_customers} customers")

    else:
        # Single batch mode
        limit = args.limit or 100
        logger.info(f"Processing {limit} customers (offset={args.offset})")

        # Get customer IDs
        customer_ids = await replacer.get_customers_batch(args.offset, limit)

        if not customer_ids:
            logger.error("No customers found")
            return

        # Load CSV
        df = replacer.load_csv_for_customers(customer_ids)

        # Extract features
        logger.info("Extracting features...")
        customer_features = {}
        for i, customer_id in enumerate(customer_ids):
            if i % 100 == 0 and i > 0:
                logger.info(f"  Processed {i}/{len(customer_ids)} customers...")

            customer_orders = df[df['Customer_ID'].astype(str) == str(customer_id)]
            if len(customer_orders) == 0:
                continue

            try:
                features = replacer.feature_extractor.extract_all_features(
                    customer_id=customer_id,
                    orders=customer_orders,
                    items=customer_orders
                )
                customer_features[customer_id] = features
            except Exception as e:
                logger.warning(f"Failed to extract features for {customer_id}: {e}")

        logger.info(f"✅ Extracted features for {len(customer_features)} customers")

        # Assign to segments
        logger.info("Assigning to segments...")
        all_memberships = replacer.assign_to_placeholder_segments(customer_features)

        # Update database
        updated_count = await replacer.update_database_batch(all_memberships, "single_batch")

        # Verify
        await replacer.verify_sample(customer_ids)

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ COMPLETE!")
        logger.info(f"{'='*80}")
        logger.info(f"Updated: {updated_count}/{len(customer_ids)} customers")


if __name__ == "__main__":
    asyncio.run(main())
