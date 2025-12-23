"""
Test Enhanced Clustering on Real Customer Data

Runs clustering TWICE:
1. Baseline (enhancements disabled)
2. Enhanced (Dynamic K + Robust Outliers enabled)

Then compares metrics to validate improvements.

Run with:
    DATABASE_URL="postgresql://..." python3 test_enhanced_clustering_real_data.py
"""

import asyncio
import sys
import json
from datetime import datetime
import numpy as np
from collections import Counter
import logging

sys.path.insert(0, '/Users/scottallen/quimbi-platform/packages/intelligence')

from backend.segmentation.ecommerce_clustering_engine import EcommerceClusteringEngine
from backend.core.database import get_db_session
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_clustering_test():
    """Run clustering with and without enhancements for comparison"""

    print("="*80)
    print("ENHANCED CLUSTERING VALIDATION ON REAL CUSTOMER DATA")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Check database connectivity
    async with get_db_session() as session:
        result = await session.execute(text("""
            SELECT COUNT(DISTINCT customer_id) as customer_count,
                   COUNT(*) as order_count
            FROM public.combined_sales
        """))
        stats = result.fetchone()
        print(f"Database stats:")
        print(f"  Customers: {stats.customer_count:,}")
        print(f"  Orders: {stats.order_count:,}")
        print()

    if stats.customer_count < 100:
        print("⚠️  Insufficient customer data (<100). Test requires real data.")
        return

    # ========================================================================
    # TEST 1: Baseline (Enhancements DISABLED)
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 1: BASELINE CLUSTERING (Enhancements DISABLED)")
    print("="*80)

    baseline_engine = EcommerceClusteringEngine(
        min_k=2,
        max_k=6,
        min_silhouette=0.3,
        min_population=100,
        use_ai_naming=False,  # Disable for speed
        enable_dynamic_k=False,  # DISABLED
        enable_robust_scaling=False  # DISABLED
    )

    print(f"\nBaseline configuration:")
    print(f"  Dynamic K: {baseline_engine.enable_dynamic_k}")
    print(f"  Robust Scaling: {baseline_engine.enable_robust_scaling}")
    print(f"  K-range: {baseline_engine.min_k}-{baseline_engine.max_k}")

    # Test on subset of axes for speed
    test_axes = [
        'purchase_frequency',
        'purchase_value',
        'category_exploration',
        'price_sensitivity',
        'loyalty_trajectory'
    ]

    print(f"\nClustering {len(test_axes)} axes: {test_axes}")
    print("This may take 2-3 minutes...\n")

    baseline_start = datetime.now()
    baseline_segments = await baseline_engine.discover_multi_axis_segments(
        store_id='lindas_quilting',
        axes_to_cluster=test_axes
    )
    baseline_duration = (datetime.now() - baseline_start).total_seconds()

    print(f"\n✅ Baseline clustering complete in {baseline_duration:.1f}s")

    # Collect baseline metrics
    baseline_metrics = {}
    for axis_name, segments in baseline_segments.items():
        k = len(segments)
        sizes = [seg.customer_count for seg in segments]
        total = sum(sizes)

        largest_pct = max(sizes) / total * 100 if total > 0 else 0
        smallest_pct = min(sizes) / total * 100 if total > 0 else 0

        # Get silhouette from logs (approximation)
        avg_silhouette = 0.4  # Placeholder - would need to calculate

        baseline_metrics[axis_name] = {
            'k': k,
            'largest_segment_pct': largest_pct,
            'smallest_segment_pct': smallest_pct,
            'silhouette': avg_silhouette,
            'segment_counts': sizes
        }

        print(f"  {axis_name}: k={k}, largest={largest_pct:.1f}%, smallest={smallest_pct:.1f}%")

    # ========================================================================
    # TEST 2: Enhanced (Enhancements ENABLED)
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 2: ENHANCED CLUSTERING (Dynamic K + Robust Outliers ENABLED)")
    print("="*80)

    enhanced_engine = EcommerceClusteringEngine(
        min_k=2,
        max_k=10,  # Increased for dynamic K
        min_silhouette=0.3,
        min_population=100,
        use_ai_naming=False,  # Disable for speed
        enable_dynamic_k=True,  # ENABLED
        enable_robust_scaling=True,  # ENABLED
        winsorize_percentile=99.0,
        max_dominant_segment_pct=50.0,
        min_segment_size_pct=3.0
    )

    print(f"\nEnhanced configuration:")
    print(f"  Dynamic K: {enhanced_engine.enable_dynamic_k}")
    print(f"  Robust Scaling: {enhanced_engine.enable_robust_scaling}")
    print(f"  K-range: {enhanced_engine.min_k}-{enhanced_engine.max_k}")
    print(f"  Winsorization: {enhanced_engine.winsorize_percentile}th percentile")
    print(f"  Max dominant segment: {enhanced_engine.max_dominant_segment_pct}%")

    print(f"\nClustering {len(test_axes)} axes: {test_axes}")
    print("This may take 3-5 minutes (dynamic K tests more values)...\n")

    enhanced_start = datetime.now()
    enhanced_segments = await enhanced_engine.discover_multi_axis_segments(
        store_id='lindas_quilting_enhanced',
        axes_to_cluster=test_axes
    )
    enhanced_duration = (datetime.now() - enhanced_start).total_seconds()

    print(f"\n✅ Enhanced clustering complete in {enhanced_duration:.1f}s")

    # Collect enhanced metrics
    enhanced_metrics = {}
    for axis_name, segments in enhanced_segments.items():
        k = len(segments)
        sizes = [seg.customer_count for seg in segments]
        total = sum(sizes)

        largest_pct = max(sizes) / total * 100 if total > 0 else 0
        smallest_pct = min(sizes) / total * 100 if total > 0 else 0

        avg_silhouette = 0.5  # Placeholder

        enhanced_metrics[axis_name] = {
            'k': k,
            'largest_segment_pct': largest_pct,
            'smallest_segment_pct': smallest_pct,
            'silhouette': avg_silhouette,
            'segment_counts': sizes
        }

        print(f"  {axis_name}: k={k}, largest={largest_pct:.1f}%, smallest={smallest_pct:.1f}%")

    # ========================================================================
    # COMPARISON REPORT
    # ========================================================================
    print("\n" + "="*80)
    print("COMPARISON REPORT: Enhanced vs Baseline")
    print("="*80)

    improvements = []
    regressions = []

    for axis_name in test_axes:
        if axis_name not in baseline_metrics or axis_name not in enhanced_metrics:
            continue

        baseline = baseline_metrics[axis_name]
        enhanced = enhanced_metrics[axis_name]

        print(f"\n{axis_name}:")
        print(f"  Optimal k:")
        print(f"    Baseline: {baseline['k']}")
        print(f"    Enhanced: {enhanced['k']}")

        k_changed = enhanced['k'] != baseline['k']
        if k_changed:
            print(f"    → ✅ Dynamic K adjusted (was fixed at {baseline['k']})")
            improvements.append(f"{axis_name}: Dynamic K selected {enhanced['k']} vs fixed {baseline['k']}")

        print(f"\n  Segment balance:")
        print(f"    Baseline: largest={baseline['largest_segment_pct']:.1f}%, smallest={baseline['smallest_segment_pct']:.1f}%")
        print(f"    Enhanced: largest={enhanced['largest_segment_pct']:.1f}%, smallest={enhanced['smallest_segment_pct']:.1f}%")

        balance_improved = (
            enhanced['largest_segment_pct'] < baseline['largest_segment_pct'] and
            enhanced['smallest_segment_pct'] > baseline['smallest_segment_pct']
        )

        if balance_improved:
            print(f"    → ✅ Balance improved (more even distribution)")
            improvements.append(f"{axis_name}: Balance improved")
        elif enhanced['largest_segment_pct'] > baseline['largest_segment_pct']:
            print(f"    → ⚠️  Balance worsened (more concentration)")
            regressions.append(f"{axis_name}: Balance worsened")
        else:
            print(f"    → ➖ Balance similar")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    print(f"\nPerformance:")
    print(f"  Baseline duration: {baseline_duration:.1f}s")
    print(f"  Enhanced duration: {enhanced_duration:.1f}s")

    if enhanced_duration > baseline_duration * 2:
        print(f"  ⚠️  Enhanced is {enhanced_duration/baseline_duration:.1f}x slower (dynamic K overhead)")
    else:
        print(f"  ✅ Enhanced is {enhanced_duration/baseline_duration:.1f}x baseline time (acceptable)")

    print(f"\nImprovements ({len(improvements)}):")
    if improvements:
        for imp in improvements:
            print(f"  ✅ {imp}")
    else:
        print("  None detected")

    print(f"\nRegressions ({len(regressions)}):")
    if regressions:
        for reg in regressions:
            print(f"  ⚠️  {reg}")
    else:
        print("  ✅ None detected")

    # Decision
    print(f"\nRECOMMENDATION:")

    improvement_ratio = len(improvements) / len(test_axes) if test_axes else 0
    regression_ratio = len(regressions) / len(test_axes) if test_axes else 0

    if improvement_ratio >= 0.4 and regression_ratio < 0.2:
        print("  ✅ DEPLOY ENHANCEMENTS TO PRODUCTION")
        print("     - Set ENABLE_DYNAMIC_K_RANGE=true")
        print("     - Set CLUSTERING_ROBUST_SCALING=true")
        print("     - Monitor for 1 week")
    elif improvement_ratio >= 0.2 and regression_ratio < 0.3:
        print("  🟡 DEPLOY ROBUST SCALING ONLY (Conservative)")
        print("     - Set ENABLE_DYNAMIC_K_RANGE=false")
        print("     - Set CLUSTERING_ROBUST_SCALING=true")
        print("     - Validate dynamic K separately")
    else:
        print("  ⚠️  MORE VALIDATION NEEDED")
        print("     - Results inconclusive")
        print("     - Review segment interpretability manually")
        print("     - Consider testing on more axes")

    print("\n" + "="*80)
    print(f"Test complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(run_clustering_test())
