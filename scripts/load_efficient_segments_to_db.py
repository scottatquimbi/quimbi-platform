#!/usr/bin/env python3
"""
Load efficient segmentation results to Railway database.

This script:
1. Runs the efficient segmentation (or loads existing results)
2. Formats segment assignments for customer_profiles table
3. Uploads to Railway PostgreSQL database

Usage:
    python3 scripts/load_efficient_segments_to_db.py --csv-path product_sales_order.csv --sample-size 5000
"""

import asyncio
import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Any
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from efficient_segmentation import EfficientMultiAxisSegmentation
import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SegmentDatabaseLoader:
    """Loads efficient segmentation results to PostgreSQL."""

    def __init__(self, database_url: str, store_id: str = "linda_quilting"):
        self.database_url = database_url
        self.store_id = store_id
        self.conn = None

    async def connect(self):
        """Connect to database."""
        logger.info(f"Connecting to database...")
        self.conn = await asyncpg.connect(self.database_url)
        logger.info("✅ Connected to database")

    async def close(self):
        """Close database connection."""
        if self.conn:
            await self.conn.close()

    async def load_segments(
        self,
        customer_assignments: Dict[str, Dict[str, int]],
        segment_centroids: Dict[str, Any]
    ):
        """
        Load segment assignments to customer_profiles table.

        Args:
            customer_assignments: {customer_id: {axis: segment_id}}
            segment_centroids: {axis: AxisSegments}
        """
        logger.info("=" * 80)
        logger.info("LOADING SEGMENTS TO DATABASE")
        logger.info("=" * 80)

        start_time = datetime.now()

        # Count customers
        total_customers = len(customer_assignments)
        logger.info(f"Processing {total_customers:,} customers...")

        # Prepare batch upserts
        batch_size = 1000
        batches = []
        current_batch = []

        for customer_id, segments in customer_assignments.items():
            # Format for database
            # segment_memberships: {axis: {segment_id: membership_score}}
            # dominant_segments: {axis: dominant_segment_id}
            # membership_strengths: {axis: max_membership_score}

            segment_memberships = {}
            dominant_segments = {}
            membership_strengths = {}

            for axis, fuzzy_memberships in segments.items():
                # fuzzy_memberships is dict like {"segment_0": 0.85, "segment_1": 0.15}
                # Find dominant segment (highest membership)
                if isinstance(fuzzy_memberships, dict):
                    # Filter out NaN values and convert to float
                    import math
                    clean_memberships = {}
                    has_valid_values = False

                    for seg_id, score in fuzzy_memberships.items():
                        if isinstance(score, (int, float)) and not math.isnan(score):
                            clean_memberships[seg_id] = float(score)
                            has_valid_values = True

                    # Skip this axis if all values are NaN
                    if not has_valid_values or not clean_memberships:
                        continue

                    dominant_segment = max(clean_memberships.items(), key=lambda x: x[1])
                    segment_id = dominant_segment[0]  # e.g., "segment_0"
                    membership_score = dominant_segment[1]  # e.g., 0.85
                    fuzzy_memberships = clean_memberships
                else:
                    # Fallback for hard clustering (single segment_id)
                    segment_id = str(fuzzy_memberships)
                    membership_score = 1.0
                    fuzzy_memberships = {segment_id: 1.0}

                segment_memberships[axis] = fuzzy_memberships  # Store full fuzzy memberships
                dominant_segments[axis] = segment_id  # Store dominant segment name
                membership_strengths[axis] = membership_score  # Store dominant membership score

            current_batch.append((
                str(customer_id),
                self.store_id,
                json.dumps(segment_memberships),
                json.dumps(dominant_segments),
                json.dumps(membership_strengths)
            ))

            if len(current_batch) >= batch_size:
                batches.append(current_batch)
                current_batch = []

        # Add remaining
        if current_batch:
            batches.append(current_batch)

        logger.info(f"Prepared {len(batches)} batches of {batch_size} customers")

        # Upsert to database
        upsert_query = """
            INSERT INTO customer_profiles (
                customer_id,
                store_id,
                segment_memberships,
                dominant_segments,
                membership_strengths,
                last_updated
            ) VALUES ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb, NOW())
            ON CONFLICT (customer_id) DO UPDATE SET
                segment_memberships = EXCLUDED.segment_memberships,
                dominant_segments = EXCLUDED.dominant_segments,
                membership_strengths = EXCLUDED.membership_strengths,
                last_updated = NOW()
        """

        updated_count = 0
        for i, batch in enumerate(batches, 1):
            await self.conn.executemany(upsert_query, batch)
            updated_count += len(batch)

            if i % 10 == 0:
                logger.info(f"  → Progress: {updated_count}/{total_customers} ({updated_count/total_customers*100:.1f}%)")

        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"✅ SEGMENTS LOADED ({elapsed:.1f}s)")
        logger.info(f"   Updated {updated_count:,} customer profiles")
        logger.info("=" * 80)

        return updated_count


async def main():
    parser = argparse.ArgumentParser(
        description="Load efficient segmentation results to Railway database"
    )
    parser.add_argument(
        '--csv-path',
        default='product_sales_order.csv',
        help='Path to order CSV file'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=5000,
        help='Number of customers to sample for pattern discovery'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5000,
        help='Batch size for Stage 2 assignment'
    )
    parser.add_argument(
        '--database-url',
        default=None,
        help='PostgreSQL connection URL (defaults to DATABASE_URL env var)'
    )
    parser.add_argument(
        '--store-id',
        default='linda_quilting',
        help='Store ID for segmentation'
    )
    parser.add_argument(
        '--reuse-results',
        action='store_true',
        help='Skip re-running segmentation, load existing results from previous run'
    )

    args = parser.parse_args()

    # Get database URL
    database_url = args.database_url or os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not set")
        return 1

    # Validate CSV exists
    if not args.reuse_results and not os.path.exists(args.csv_path):
        logger.error(f"CSV file not found: {args.csv_path}")
        return 1

    # Run segmentation (or skip if reusing)
    if args.reuse_results:
        logger.warning("--reuse-results flag set, but results not saved from previous run")
        logger.info("Running segmentation from scratch...")

    # Initialize segmenter
    segmenter = EfficientMultiAxisSegmentation(
        sample_size=args.sample_size,
        min_k=2,
        max_k=6
    )

    # Stage 1: Discover patterns
    logger.info("Starting segmentation...")
    segments = await segmenter.discover_segments_from_sample(args.csv_path)

    # Stage 2: Assign full population
    await segmenter.assign_full_population(
        args.csv_path,
        batch_size=args.batch_size
    )

    # Get assignments
    customer_assignments = segmenter.customer_assignments

    if not customer_assignments:
        logger.error("No customer assignments found - segmentation may have failed")
        return 1

    logger.info(f"Segmentation complete: {len(customer_assignments):,} customers assigned")

    # Load to database
    loader = SegmentDatabaseLoader(database_url, args.store_id)

    try:
        await loader.connect()

        updated_count = await loader.load_segments(
            customer_assignments,
            segments
        )

        logger.info("=" * 80)
        logger.info("SUCCESS")
        logger.info("=" * 80)
        logger.info(f"✅ Loaded {len(segments)} axes with {sum(s.n_clusters for s in segments.values())} segments")
        logger.info(f"✅ Updated {updated_count:,} customer profiles in Railway database")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"Failed to load segments: {e}", exc_info=True)
        return 1

    finally:
        await loader.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
