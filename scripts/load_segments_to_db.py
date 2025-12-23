"""
Load Clustering Results to Railway Database

Parses clustering results from CSV-based clustering run and loads:
1. Customer segment memberships (fuzzy) → customer_profiles.segment_memberships
2. Dominant segments per axis → customer_profiles.dominant_segments
3. Segment metadata → segments table (if exists)

Usage:
    # Test with 10 customers first
    python scripts/load_segments_to_db.py --test --limit 10

    # Load all customers
    python scripts/load_segments_to_db.py --all

    # Load specific customers by email/ID
    python scripts/load_segments_to_db.py --customers "email1@example.com,email2@example.com"
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
from backend.segmentation.ecommerce_clustering_engine import EcommerceClusteringEngine
from backend.segmentation.ecommerce_feature_extraction import EcommerceFeatureExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SegmentDataLoader:
    """
    Loads clustering results from CSV data into Railway database.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = EcommerceClusteringEngine(anthropic_api_key=None)  # No API key needed for loading
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
                    ADD COLUMN segment_memberships JSONB DEFAULT '{}'::jsonb
                """))
                await session.commit()
                logger.info("✅ Created segment_memberships column")

            if 'dominant_segments' not in columns:
                logger.warning("⚠️  Column 'dominant_segments' not found in customer_profiles")
                logger.info("Creating column...")
                await session.execute(text("""
                    ALTER TABLE customer_profiles
                    ADD COLUMN dominant_segments JSONB DEFAULT '{}'::jsonb
                """))
                await session.commit()
                logger.info("✅ Created dominant_segments column")

            logger.info("✅ Schema check complete")

    async def load_csv_data(self, sample_size: Optional[int] = None):
        """
        Load order data from CSV files (same as clustering script).
        """
        logger.info("Loading CSV data...")

        # Load product sales order data
        product_sales_path = "product_sales_order.csv"
        sales_data_path = "sales_data_orders.csv"

        if not os.path.exists(product_sales_path):
            raise FileNotFoundError(f"CSV file not found: {product_sales_path}")

        # Load both CSVs
        df_product = pd.read_csv(product_sales_path)
        df_sales = pd.read_csv(sales_data_path) if os.path.exists(sales_data_path) else None

        logger.info(f"Loaded {len(df_product)} rows from {product_sales_path}")
        if df_sales is not None:
            logger.info(f"Loaded {len(df_sales)} orders from {sales_data_path}")

        # Get unique customers
        customer_ids = df_product['Source'].unique().tolist()
        logger.info(f"Found {len(customer_ids)} unique customers")

        if sample_size and sample_size < len(customer_ids):
            customer_ids = customer_ids[:sample_size]
            logger.info(f"Sampling {sample_size} customers for testing")

        return df_product, df_sales, customer_ids

    async def cluster_and_extract(self, df_product, df_sales, customer_ids, axes_to_cluster: List[str]):
        """
        Run clustering on the data and extract segment memberships.
        """
        logger.info(f"Clustering {len(customer_ids)} customers across {len(axes_to_cluster)} axes...")

        # Extract features for all customers
        logger.info("Extracting features...")
        customer_features = {}

        for i, customer_id in enumerate(customer_ids):
            if i % 1000 == 0:
                logger.info(f"  Processed {i}/{len(customer_ids)} customers...")

            # Get customer's orders
            customer_orders = df_product[df_product['Source'] == customer_id]

            if len(customer_orders) == 0:
                continue

            # Extract features
            try:
                features = self.feature_extractor.extract_all_features(
                    customer_id=customer_id,
                    orders=customer_orders,
                    items=customer_orders
                )
                customer_features[customer_id] = features
            except Exception as e:
                logger.warning(f"Failed to extract features for {customer_id}: {e}")
                continue

        logger.info(f"✅ Extracted features for {len(customer_features)} customers")

        # Cluster each axis
        all_segments = {}
        all_memberships = {}

        for axis_name in axes_to_cluster:
            logger.info(f"\nClustering axis: {axis_name}")
            logger.info("="*80)

            # Get features for this axis
            axis_features = {}
            for customer_id, features in customer_features.items():
                if axis_name in features:
                    axis_features[customer_id] = features[axis_name]

            if len(axis_features) == 0:
                logger.warning(f"No features found for axis {axis_name}, skipping")
                continue

            # Convert to numpy array
            feature_names = list(list(axis_features.values())[0].keys())
            X = np.array([[axis_features[cid][fname] for fname in feature_names]
                          for cid in axis_features.keys()])
            customer_list = list(axis_features.keys())

            logger.info(f"Customers: {len(customer_list)}")
            logger.info(f"Features: {feature_names}")

            # Find optimal k
            logger.info("Finding optimal k...")
            best_k, best_score, scaler = self._find_optimal_k(X, min_k=2, max_k=6)
            logger.info(f"✅ Optimal k={best_k} with silhouette={best_score:.3f}")

            # Cluster with optimal k
            X_scaled = scaler.transform(X)
            kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)

            # Calculate fuzzy memberships
            memberships = self._calculate_fuzzy_memberships(X_scaled, kmeans.cluster_centers_)

            # Store segments
            segments = []
            for cluster_idx in range(best_k):
                segment = {
                    'segment_id': f"segment_{cluster_idx}",
                    'cluster_center': kmeans.cluster_centers_[cluster_idx],
                    'feature_names': feature_names,
                    'scaler_mean': scaler.mean_,
                    'scaler_scale': scaler.scale_,
                }
                segments.append(segment)

            all_segments[axis_name] = segments

            # Store memberships for each customer
            for i, customer_id in enumerate(customer_list):
                if customer_id not in all_memberships:
                    all_memberships[customer_id] = {}
                all_memberships[customer_id][axis_name] = {
                    f"segment_{j}": float(memberships[i][j])
                    for j in range(best_k)
                }

            logger.info(f"✅ {axis_name}: {best_k} segments discovered")

        logger.info(f"\n✅ Clustering complete!")
        logger.info(f"Total segments: {sum(len(segs) for segs in all_segments.values())}")
        logger.info(f"Customers with memberships: {len(all_memberships)}")

        return all_segments, all_memberships

    def _find_optimal_k(self, X, min_k=2, max_k=6):
        """Find optimal number of clusters using silhouette score."""
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        best_k = min_k
        best_score = -1

        for k in range(min_k, max_k + 1):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)

            if len(np.unique(labels)) < 2:
                continue

            score = silhouette_score(X_scaled, labels)
            logger.info(f"  k={k}: silhouette={score:.3f}")

            if score > best_score:
                best_score = score
                best_k = k

        return best_k, best_score, scaler

    def _calculate_fuzzy_memberships(self, X_scaled, cluster_centers):
        """Calculate fuzzy membership using exponential decay."""
        memberships = []

        for point in X_scaled:
            distances = np.array([
                np.linalg.norm(point - center)
                for center in cluster_centers
            ])

            # Exponential decay
            similarities = np.exp(-distances)

            # Normalize to sum to 1
            total = similarities.sum()
            if total > 0:
                normalized = similarities / total
            else:
                normalized = np.ones(len(cluster_centers)) / len(cluster_centers)

            memberships.append(normalized)

        return np.array(memberships)

    async def load_to_database(self, all_segments, all_memberships, clustering_run_id: str):
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
                    dominant_segment = max(axis_memberships.items(), key=lambda x: x[1])[0]
                    dominant_segments[axis_name] = dominant_segment

                # Create metadata
                segment_metadata = {
                    'last_clustered': datetime.now(timezone.utc).isoformat(),
                    'clustering_run_id': clustering_run_id,
                    'axes_count': len(memberships),
                    'total_segments': sum(len(segs) for segs in all_segments.values())
                }

                # Build full JSONB structure
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
        Verify that segment data was loaded correctly by checking a few customers.
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
                    logger.info(f"  Dominant segments: {json.dumps(row[2], indent=2)}")
                    logger.info(f"  Sample memberships: {list(row[1].keys())}")
                else:
                    logger.warning(f"❌ Customer {customer_id} not found")


async def main():
    parser = argparse.ArgumentParser(description='Load clustering results to Railway database')
    parser.add_argument('--test', action='store_true', help='Test mode (10 customers only)')
    parser.add_argument('--limit', type=int, help='Limit number of customers to process')
    parser.add_argument('--all', action='store_true', help='Process all customers')
    parser.add_argument('--axes', type=str, help='Comma-separated list of axes to cluster (default: all)')
    args = parser.parse_args()

    # Determine sample size
    if args.test:
        sample_size = 10
    elif args.limit:
        sample_size = args.limit
    elif args.all:
        sample_size = None
    else:
        # Default: test mode
        sample_size = 10
        logger.info("No mode specified, defaulting to test mode (10 customers)")

    # Determine axes to cluster
    if args.axes:
        axes_to_cluster = args.axes.split(',')
    else:
        # All 13 axes
        axes_to_cluster = [
            'purchase_frequency', 'purchase_value', 'category_exploration',
            'price_sensitivity', 'purchase_cadence', 'customer_maturity',
            'repurchase_behavior', 'return_behavior', 'communication_preference',
            'problem_complexity_profile', 'loyalty_trajectory', 'product_knowledge',
            'value_sophistication'
        ]

    logger.info("="*80)
    logger.info("SEGMENT DATA LOADER")
    logger.info("="*80)
    logger.info(f"Mode: {'TEST' if sample_size else 'PRODUCTION'}")
    if sample_size:
        logger.info(f"Sample size: {sample_size} customers")
    else:
        logger.info("Processing: ALL customers")
    logger.info(f"Axes: {len(axes_to_cluster)}")
    logger.info("="*80)

    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        logger.info("Set it with: export DATABASE_URL='postgresql://...'")
        return

    # Create loader
    loader = SegmentDataLoader(database_url)

    # Check schema
    await loader.check_schema()

    # Load CSV data
    df_product, df_sales, customer_ids = await loader.load_csv_data(sample_size=sample_size)

    # Cluster and extract memberships
    clustering_run_id = f"csv_load_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    all_segments, all_memberships = await loader.cluster_and_extract(
        df_product, df_sales, customer_ids, axes_to_cluster
    )

    # Load to database
    updated_count = await loader.load_to_database(all_segments, all_memberships, clustering_run_id)

    # Verify load
    if updated_count > 0:
        await loader.verify_load(customer_ids)

    logger.info("\n" + "="*80)
    logger.info("✅ SEGMENT DATA LOAD COMPLETE!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
