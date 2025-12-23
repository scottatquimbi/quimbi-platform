"""
Show what segments are actually discovered on purchase_frequency axis
"""
import asyncio
from backend.segmentation.ecommerce_clustering_engine import EcommerceClusteringEngine

async def show_segments():
    """Run clustering and show detailed segment info"""
    print("=" * 80)
    print("DISCOVERED SEGMENTS - Purchase Frequency Axis")
    print("=" * 80)
    print()

    # Enhanced engine with balance-aware k-selection
    engine = EcommerceClusteringEngine(
        min_k=2,
        max_k=8,
        enable_dynamic_k=True,
        enable_robust_scaling=True,
        use_ai_naming=False
    )

    print("Running clustering on 1,000 customers...")
    print("Engine config: Dynamic K + Robust Scaling + Balance-Aware Selection")
    print()

    results = await engine.discover_multi_axis_segments(
        store_id="lindas_electric_quilters",
        axes_to_cluster=['purchase_frequency'],
        max_customers=1000
    )

    segments = results.get('purchase_frequency', [])

    print(f"✓ Found {len(segments)} segments")
    print()
    print("=" * 80)
    print("SEGMENT DETAILS")
    print("=" * 80)
    print()

    for i, seg in enumerate(segments):
        print(f"Segment {i+1}: {seg.segment_name}")
        print(f"  Size: {seg.customer_count} customers ({seg.population_percentage*100:.1f}%)")
        print(f"  Silhouette: {seg.scaler_params.get('silhouette', 0.0):.4f}")
        print()
        print(f"  Interpretation:")
        print(f"    {seg.interpretation}")
        print()

        # Show cluster center (feature values)
        feature_names = seg.scaler_params.get('feature_names', [])
        print(f"  Behavioral Profile (cluster center):")
        for j, fname in enumerate(feature_names):
            if j < len(seg.cluster_center):
                value = seg.cluster_center[j]
                print(f"    - {fname}: {value:.3f}")
        print()
        print("-" * 80)
        print()

    print("=" * 80)
    print("SEGMENT DISTRIBUTION")
    print("=" * 80)

    sizes = sorted([seg.customer_count for seg in segments], reverse=True)
    percentages = sorted([seg.population_percentage*100 for seg in segments], reverse=True)

    print(f"Sizes: {sizes}")
    print(f"Percentages: {[f'{p:.1f}%' for p in percentages]}")
    print()

    # Calculate balance
    import numpy as np
    balance = np.std(sizes) / np.mean(sizes)
    print(f"Balance (std/mean): {balance:.3f} (lower = more balanced)")
    print(f"Largest segment: {max(percentages):.1f}%")
    print(f"Smallest segment: {min(percentages):.1f}%")
    print()

if __name__ == "__main__":
    asyncio.run(show_segments())
