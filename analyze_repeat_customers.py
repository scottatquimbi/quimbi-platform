"""
Analyze the 6% repeat customers to see if there are sub-segments being missed
"""
import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from backend.core.database import get_db_session
from backend.segmentation.ecommerce_feature_extraction import EcommerceFeatureExtractor
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

async def analyze_repeat_customers():
    """Deep dive into repeat customer segment"""
    print("=" * 80)
    print("REPEAT CUSTOMER ANALYSIS - Finding Sub-Segments")
    print("=" * 80)
    print()

    # Fetch customers with 3+ orders (the "repeat" customers)
    async with get_db_session() as session:
        query = text("""
            SELECT
                customer_id,
                COUNT(DISTINCT order_id) as total_orders,
                SUM(line_item_sales) as total_spent,
                MIN(order_date) as first_order,
                MAX(order_date) as last_order,
                COUNT(DISTINCT DATE_TRUNC('month', order_date)) as active_months
            FROM public.combined_sales
            WHERE customer_id IS NOT NULL
            GROUP BY customer_id
            HAVING COUNT(DISTINCT order_id) >= 3
            ORDER BY total_orders DESC
            LIMIT 500
        """)

        result = await session.execute(query)
        customers = result.fetchall()

    print(f"Found {len(customers)} repeat customers (3+ orders)")
    print()

    # Show distribution
    orders = [c.total_orders for c in customers]
    spent = [float(c.total_spent) for c in customers]  # Convert Decimal to float

    print("Order Count Distribution:")
    print(f"  Min: {min(orders)}")
    print(f"  25th percentile: {np.percentile(orders, 25):.0f}")
    print(f"  Median: {np.percentile(orders, 50):.0f}")
    print(f"  75th percentile: {np.percentile(orders, 75):.0f}")
    print(f"  95th percentile: {np.percentile(orders, 95):.0f}")
    print(f"  Max: {max(orders)}")
    print()

    print("Total Spend Distribution:")
    print(f"  Min: ${min(spent):.2f}")
    print(f"  25th percentile: ${np.percentile(spent, 25):.2f}")
    print(f"  Median: ${np.percentile(spent, 50):.2f}")
    print(f"  75th percentile: ${np.percentile(spent, 75):.2f}")
    print(f"  95th percentile: ${np.percentile(spent, 95):.2f}")
    print(f"  Max: ${max(spent):.2f}")
    print()

    # Fetch full order data for feature extraction
    customer_ids = [c.customer_id for c in customers]
    customer_ids_str = ",".join([f"'{cid}'" for cid in customer_ids[:500]])

    async with get_db_session() as session:
        query = text(f"""
            SELECT customer_id, order_id, order_date,
                   line_item_sales as total_price,
                   line_item_discount as discount_amount,
                   sales_channel as source,
                   product_id, category, product_type, quantity,
                   line_item_sales as price,
                   line_item_refunds as refund_amount
            FROM public.combined_sales
            WHERE customer_id IN ({customer_ids_str})
            ORDER BY customer_id, order_date
        """)

        result = await session.execute(query)
        rows = result.fetchall()

    print(f"Fetched {len(rows)} order records")
    print()

    # Extract purchase_frequency features
    print("Extracting behavioral features...")
    extractor = EcommerceFeatureExtractor()

    # Group by customer
    orders_by_customer = {}
    for row in rows:
        cid = row.customer_id
        if cid not in orders_by_customer:
            orders_by_customer[cid] = []
        orders_by_customer[cid].append(row)

    # Extract features
    feature_names = [
        'orders_per_month',
        'avg_days_between_orders',
        'purchase_consistency',
        'recent_orders_90d',
        'days_since_last_purchase',
        'total_orders'
    ]

    X = []
    customer_list = []

    for cid, orders in orders_by_customer.items():
        # Convert to DataFrame
        df = pd.DataFrame([{
            'order_id': o.order_id,
            'order_date': o.order_date,
            'total_price': o.total_price,
        } for o in orders])

        df['order_date'] = pd.to_datetime(df['order_date'])

        # Extract features
        features = extractor.extract_frequency_features(df)

        row = [features.get(fname, 0.0) for fname in feature_names]
        X.append(row)
        customer_list.append({
            'customer_id': cid,
            'total_orders': len(orders),
            'features': features
        })

    X = np.array(X)
    print(f"Feature matrix: {X.shape}")
    print()

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Test different k values on JUST the repeat customers
    print("=" * 80)
    print("CLUSTERING REPEAT CUSTOMERS ONLY")
    print("=" * 80)
    print()
    print(f"{'k':<4} {'Silhouette':<12} {'Balance':<12} {'Sizes':<40}")
    print("-" * 80)

    for k in range(2, 9):
        if k > len(X):
            break

        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        sil = silhouette_score(X_scaled, labels)

        unique, counts = np.unique(labels, return_counts=True)
        balance = counts.std() / counts.mean()

        sizes_str = ", ".join([str(c) for c in sorted(counts, reverse=True)])

        print(f"{k:<4} {sil:<12.3f} {balance:<12.3f} [{sizes_str}]")

    print()
    print("=" * 80)
    print("DETAILED ANALYSIS - k=4 (likely sweet spot)")
    print("=" * 80)
    print()

    # Cluster with k=4 to show sub-segments
    k = 4
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    for cluster_id in range(k):
        mask = labels == cluster_id
        cluster_customers = [customer_list[i] for i in range(len(customer_list)) if mask[i]]

        print(f"Cluster {cluster_id + 1}: {len(cluster_customers)} customers ({len(cluster_customers)/len(customer_list)*100:.1f}%)")

        # Analyze characteristics
        orders_counts = [c['total_orders'] for c in cluster_customers]

        print(f"  Order counts: {min(orders_counts)}-{max(orders_counts)} (median: {np.median(orders_counts):.0f})")

        # Show cluster center (unscaled)
        cluster_center_scaled = kmeans.cluster_centers_[cluster_id]
        cluster_center = scaler.inverse_transform(cluster_center_scaled.reshape(1, -1))[0]

        print(f"  Behavioral profile:")
        for i, fname in enumerate(feature_names):
            print(f"    - {fname}: {cluster_center[i]:.3f}")

        # Show sample customers
        print(f"  Sample customers:")
        for c in cluster_customers[:3]:
            print(f"    - {c['customer_id']}: {c['total_orders']} orders, {c['features'].get('orders_per_month', 0):.2f} orders/month")

        print()

if __name__ == "__main__":
    asyncio.run(analyze_repeat_customers())
