"""
Direct test of k-selection scoring to understand balance awareness
"""
import asyncio
import numpy as np
from backend.core.database import get_db_session
from backend.segmentation.ecommerce_feature_extraction import EcommerceFeatureExtractor
from sqlalchemy import text
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

async def test_k_scoring():
    """Test k selection scores directly"""
    print("=" * 80)
    print("DIRECT K-SELECTION SCORING TEST")
    print("=" * 80)
    print()

    # Fetch 100 customers
    async with get_db_session() as session:
        query = text("""
            WITH sampled_customers AS (
                SELECT customer_id FROM (
                    SELECT DISTINCT customer_id
                    FROM public.combined_sales
                    WHERE customer_id IS NOT NULL
                ) unique_customers
                ORDER BY RANDOM()
                LIMIT 100
            )
            SELECT cs.customer_id, cs.order_id, cs.order_date,
                   cs.line_item_sales as total_price,
                   cs.line_item_discount as discount_amount,
                   cs.sales_channel as source,
                   cs.product_id, cs.category, cs.product_type, cs.quantity,
                   cs.line_item_sales as price,
                   cs.line_item_refunds as refund_amount
            FROM public.combined_sales cs
            INNER JOIN sampled_customers sc ON cs.customer_id = sc.customer_id
            WHERE cs.customer_id IS NOT NULL
            ORDER BY cs.customer_id, cs.order_date
        """)

        result = await session.execute(query)
        rows = result.fetchall()

    # Extract features
    print(f"Fetched {len(rows)} orders")

    extractor = EcommerceFeatureExtractor()
    customer_features = extractor.extract_features_from_orders(rows)

    print(f"Extracted features for {len(customer_features)} customers")
    print()

    # Get purchase_frequency features
    features_by_customer = {}
    for customer_id, features in customer_features.items():
        features_by_customer[customer_id] = features

    # Build feature matrix for purchase_frequency axis
    feature_names = [
        'orders_per_month',
        'avg_days_between_orders',
        'purchase_consistency',
        'recent_orders_90d',
        'days_since_last_purchase',
        'total_orders'
    ]

    X = []
    customer_ids = []
    for customer_id, features in features_by_customer.items():
        row = [features.get(fname, 0.0) for fname in feature_names]
        X.append(row)
        customer_ids.append(customer_id)

    X = np.array(X)
    print(f"Feature matrix shape: {X.shape}")
    print()

    # Test k values from 2 to 8
    print("Testing k values with balance-aware scoring:")
    print()
    print(f"{'k':<4} {'Silhouette':<12} {'Balance':<12} {'Penalty':<12} {'Combined':<12} {'Sizes':<30}")
    print("-" * 80)

    for k in range(2, 9):
        # Cluster
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)

        # Silhouette
        sil = silhouette_score(X, labels)

        # Balance (std/mean of cluster sizes)
        unique, counts = np.unique(labels, return_counts=True)
        balance = counts.std() / counts.mean()

        # Balance penalty
        balance_penalty = min(0.5, balance / 2.0)

        # Combined score
        combined = sil * (1.0 - balance_penalty)

        # Cluster sizes
        sizes_str = ", ".join([str(c) for c in sorted(counts, reverse=True)])

        print(f"{k:<4} {sil:<12.3f} {balance:<12.3f} {balance_penalty:<12.3f} {combined:<12.3f} [{sizes_str}]")

    print()
    print("=" * 80)
    print("Analysis:")
    print("- Balance = std/mean of cluster sizes (lower = more balanced)")
    print("- Penalty = min(0.5, balance/2.0) (capped at 50%)")
    print("- Combined = silhouette * (1.0 - penalty)")
    print("- Best k should maximize Combined score")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_k_scoring())
