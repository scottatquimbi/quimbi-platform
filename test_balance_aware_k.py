"""
Test balance-aware k selection to understand scoring
"""
import asyncio
from backend.segmentation.ecommerce_clustering_engine import EcommerceClusteringEngine
from backend.core.database import get_db_session

async def test_balance_scoring():
    """Test k selection with balance awareness"""
    print("=" * 80)
    print("BALANCE-AWARE K SELECTION TEST")
    print("=" * 80)
    print()

    # Create engine with enhanced features and debug mode
    engine = EcommerceClusteringEngine(
        min_k=2,
        max_k=8,
        enable_dynamic_k=True,
        enable_robust_scaling=True,
        use_ai_naming=False
    )

    # Run on small sample
    print("Running clustering on 100 customers with Dynamic K + Robust Scaling...")
    print()

    results = await engine.discover_multi_axis_segments(
        store_id="test_store",
        axes_to_cluster=['purchase_frequency'],
        max_customers=100
    )

    segments = results.get('purchase_frequency', [])

    print(f"Result: Found {len(segments)} segments")
    print()

    for i, seg in enumerate(segments):
        print(f"Segment {i+1}: {seg.customer_count} customers ({seg.population_percentage*100:.1f}%)")
        print(f"  Silhouette: {seg.scaler_params.get('silhouette', 0.0):.4f}")

    print()
    print("=" * 80)
    print("Check engine logs above for k-selection scoring details")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_balance_scoring())
