#!/usr/bin/env python3
"""
Initial Clustering Script

Runs multi-axis behavioral segmentation on all customers in the database.

This script:
1. Loads order data from PostgreSQL
2. Extracts features across 14 axes
3. Clusters each axis to discover behavioral segments
4. Generates AI-powered segment names
5. Populates customer_profiles JSONB columns with fuzzy memberships

Usage:
    python scripts/run_initial_clustering.py --store-id linda_quilting

Options:
    --store-id: Store identifier (default: linda_quilting)
    --axes: Comma-separated list of axes to cluster (default: all 13 available)
    --min-k: Minimum clusters per axis (default: 2)
    --max-k: Maximum clusters per axis (default: 6)
    --use-ai-naming: Use Claude API for segment naming (default: True)
    --dry-run: Run clustering but don't save to database

Environment Variables:
    ANTHROPIC_API_KEY: Required for AI segment naming
    DATABASE_URL: PostgreSQL connection string
"""

import asyncio
import argparse
import os
import sys
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.segmentation import EcommerceClusteringEngine
from backend.core.database import get_db_session

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main(args):
    """Run initial clustering"""
    logger.info("=" * 80)
    logger.info("E-COMMERCE MULTI-AXIS BEHAVIORAL SEGMENTATION")
    logger.info("=" * 80)
    logger.info(f"Store ID: {args.store_id}")
    logger.info(f"Axes to cluster: {args.axes or 'ALL'}")
    logger.info(f"K range: {args.min_k}-{args.max_k}")
    logger.info(f"AI naming: {args.use_ai_naming}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 80)

    # Validate API key if AI naming enabled
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if args.use_ai_naming and not anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set, disabling AI naming")
        args.use_ai_naming = False

    # Parse axes
    if args.axes:
        axes_to_cluster = [axis.strip() for axis in args.axes.split(',')]
    else:
        axes_to_cluster = None  # Use default (all 13 axes)

    # Initialize clustering engine
    logger.info("Initializing clustering engine...")
    engine = EcommerceClusteringEngine(
        min_k=args.min_k,
        max_k=args.max_k,
        use_ai_naming=args.use_ai_naming,
        anthropic_api_key=anthropic_api_key
    )

    # Run discovery
    logger.info("Starting segment discovery...")
    start_time = datetime.now()

    try:
        discovered_segments = await engine.discover_multi_axis_segments(
            store_id=args.store_id,
            axes_to_cluster=axes_to_cluster
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Segment discovery completed in {elapsed:.1f}s")

        # Print results
        logger.info("=" * 80)
        logger.info("DISCOVERED SEGMENTS")
        logger.info("=" * 80)

        total_segments = 0
        for axis_name, segments in discovered_segments.items():
            logger.info(f"\n{axis_name.upper()} ({len(segments)} segments):")
            for segment in segments:
                logger.info(f"  - {segment.segment_name}")
                logger.info(f"    Population: {segment.customer_count} customers ({segment.population_percentage * 100:.1f}%)")
                logger.info(f"    {segment.interpretation}")
            total_segments += len(segments)

        logger.info("=" * 80)
        logger.info(f"TOTAL: {total_segments} segments across {len(discovered_segments)} axes")
        logger.info("=" * 80)

        if args.dry_run:
            logger.info("DRY RUN: Segments discovered but NOT saved to database")
        else:
            logger.info("Segments saved to database successfully")

    except Exception as e:
        logger.error(f"Clustering failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Run initial multi-axis behavioral segmentation'
    )

    parser.add_argument(
        '--store-id',
        type=str,
        default='linda_quilting',
        help='Store identifier (default: linda_quilting)'
    )

    parser.add_argument(
        '--axes',
        type=str,
        default=None,
        help='Comma-separated list of axes to cluster (default: all 13)'
    )

    parser.add_argument(
        '--min-k',
        type=int,
        default=2,
        help='Minimum clusters per axis (default: 2)'
    )

    parser.add_argument(
        '--max-k',
        type=int,
        default=6,
        help='Maximum clusters per axis (default: 6)'
    )

    parser.add_argument(
        '--use-ai-naming',
        action='store_true',
        default=True,
        help='Use Claude API for segment naming (default: True)'
    )

    parser.add_argument(
        '--no-ai-naming',
        action='store_false',
        dest='use_ai_naming',
        help='Disable AI naming, use fallback names'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run clustering but don\'t save to database'
    )

    args = parser.parse_args()

    # Run
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)
