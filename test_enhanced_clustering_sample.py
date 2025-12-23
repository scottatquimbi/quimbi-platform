#!/usr/bin/env python3
"""
Test enhanced clustering on a SAMPLE of real customer data
This is a quick validation test (5-10 minutes) instead of full population (~60 min)
"""

import asyncio
import time
from datetime import datetime
from backend.segmentation.ecommerce_clustering_engine import EcommerceClusteringEngine

# Sample size
SAMPLE_CUSTOMERS = 1000  # Test on 1,000 customers instead of 24K

async def main():
    print("="*80)
    print("ENHANCED CLUSTERING VALIDATION ON SAMPLE DATA")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Sample size: {SAMPLE_CUSTOMERS:,} customers (subset of full population)\n")

    # Test axes (subset for speed)
    test_axes = ['purchase_frequency', 'purchase_value', 'category_exploration']

    print(f"Testing {len(test_axes)} axes: {test_axes}\n")

    results = {}

    # TEST 1: Baseline (no enhancements)
    print("="*80)
    print("TEST 1: BASELINE CLUSTERING (Enhancements DISABLED)")
    print("="*80)
    print("\nBaseline configuration:")
    print("  Dynamic K: False")
    print("  Robust Scaling: False")
    print("  K-range: 2-6")
    print(f"\nClustering {len(test_axes)} axes...")
    print("This may take 2-3 minutes...\n")

    engine_baseline = EcommerceClusteringEngine(
        min_k=2,
        max_k=6,
        enable_dynamic_k=False,
        enable_robust_scaling=False,
        use_ai_naming=False  # Skip AI naming for speed
    )

    start_time = time.time()
    try:
        result_baseline = await engine_baseline.discover_multi_axis_segments(
            store_id="lindas_sample",
            axes_to_cluster=test_axes,
            max_customers=SAMPLE_CUSTOMERS  # LIMIT to sample size
        )
        baseline_duration = time.time() - start_time

        # Extract metrics
        baseline_metrics = {}
        for axis_name, segments in result_baseline.items():
            if segments:
                k = len(segments)
                sizes = [s.customer_count for s in segments]
                total = sum(sizes)
                largest_pct = (max(sizes) / total * 100) if total > 0 else 0
                smallest_pct = (min(sizes) / total * 100) if total > 0 else 0

                # Get silhouette score from first segment (stored in scaler_params)
                silhouette = segments[0].scaler_params.get('silhouette', 0.0) if segments else 0.0

                baseline_metrics[axis_name] = {
                    'k': k,
                    'largest_segment_pct': largest_pct,
                    'smallest_segment_pct': smallest_pct,
                    'silhouette': silhouette
                }

        total_customers = sum(s.customer_count for segments in result_baseline.values() for s in segments)

        results['baseline'] = {
            'duration': baseline_duration,
            'metrics': baseline_metrics,
            'total_customers': total_customers
        }

        print(f"\n✅ Baseline clustering complete in {baseline_duration:.1f}s")
        print(f"   Clustered {total_customers:,} unique customers\n")

    except Exception as e:
        print(f"\n❌ Baseline clustering failed: {e}\n")
        return

    # TEST 2: Enhanced (both features enabled)
    print("="*80)
    print("TEST 2: ENHANCED CLUSTERING (Dynamic K + Robust Outliers ENABLED)")
    print("="*80)
    print("\nEnhanced configuration:")
    print("  Dynamic K: True")
    print("  Robust Scaling: True")
    print("  K-range: 2-10")
    print("  Winsorization: 99.0th percentile")
    print("  Max dominant segment: 50.0%")
    print(f"\nClustering {len(test_axes)} axes...")
    print("This may take 3-5 minutes (dynamic K tests more values)...\n")

    engine_enhanced = EcommerceClusteringEngine(
        min_k=2,
        max_k=10,
        enable_dynamic_k=True,
        enable_robust_scaling=True,
        winsorize_percentile=99.0,
        max_dominant_segment_pct=50.0,
        use_ai_naming=False  # Skip AI naming for speed
    )

    start_time = time.time()
    try:
        result_enhanced = await engine_enhanced.discover_multi_axis_segments(
            store_id="lindas_sample_enhanced",
            axes_to_cluster=test_axes,
            max_customers=SAMPLE_CUSTOMERS  # LIMIT to sample size
        )
        enhanced_duration = time.time() - start_time

        # Extract metrics
        enhanced_metrics = {}
        for axis_name, segments in result_enhanced.items():
            if segments:
                k = len(segments)
                sizes = [s.customer_count for s in segments]
                total = sum(sizes)
                largest_pct = (max(sizes) / total * 100) if total > 0 else 0
                smallest_pct = (min(sizes) / total * 100) if total > 0 else 0

                # Get silhouette score
                silhouette = segments[0].scaler_params.get('silhouette', 0.0) if segments else 0.0

                enhanced_metrics[axis_name] = {
                    'k': k,
                    'largest_segment_pct': largest_pct,
                    'smallest_segment_pct': smallest_pct,
                    'silhouette': silhouette
                }

        total_customers = sum(s.customer_count for segments in result_enhanced.values() for s in segments)

        results['enhanced'] = {
            'duration': enhanced_duration,
            'metrics': enhanced_metrics,
            'total_customers': total_customers
        }

        print(f"\n✅ Enhanced clustering complete in {enhanced_duration:.1f}s")
        print(f"   Clustered {total_customers:,} unique customers\n")

    except Exception as e:
        print(f"\n❌ Enhanced clustering failed: {e}\n")
        return

    # COMPARISON
    print("="*80)
    print("COMPARISON REPORT: Enhanced vs Baseline")
    print("="*80)
    print()

    improvements = []
    regressions = []

    for axis in test_axes:
        baseline = results['baseline']['metrics'].get(axis, {})
        enhanced = results['enhanced']['metrics'].get(axis, {})

        if not baseline or not enhanced:
            continue

        print(f"AXIS: {axis}")
        print(f"  Baseline: k={baseline['k']}, largest_segment={baseline['largest_segment_pct']:.1f}%, silhouette={baseline['silhouette']:.3f}")
        print(f"  Enhanced: k={enhanced['k']}, largest_segment={enhanced['largest_segment_pct']:.1f}%, silhouette={enhanced['silhouette']:.3f}")

        # Detect improvements
        balance_improved = enhanced['largest_segment_pct'] < baseline['largest_segment_pct'] - 5  # 5% threshold
        separation_improved = enhanced['silhouette'] > baseline['silhouette'] + 0.05  # 0.05 threshold

        # Detect regressions
        balance_regressed = enhanced['largest_segment_pct'] > baseline['largest_segment_pct'] + 5
        separation_regressed = enhanced['silhouette'] < baseline['silhouette'] - 0.05

        if balance_improved or separation_improved:
            improvements.append(axis)
            status = "✅ IMPROVEMENT"
            if balance_improved:
                status += f": Better balance ({baseline['largest_segment_pct']:.1f}% → {enhanced['largest_segment_pct']:.1f}%)"
            if separation_improved:
                status += f", Better separation (+{enhanced['silhouette'] - baseline['silhouette']:.2f})"
            print(f"  {status}")
        elif balance_regressed or separation_regressed:
            regressions.append(axis)
            status = "⚠️  REGRESSION"
            if balance_regressed:
                status += f": Worse balance ({baseline['largest_segment_pct']:.1f}% → {enhanced['largest_segment_pct']:.1f}%)"
            if separation_regressed:
                status += f", Worse separation ({enhanced['silhouette'] - baseline['silhouette']:.2f})"
            print(f"  {status}")
        else:
            print(f"  ⚪ NEUTRAL: No significant change")

        print()

    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()
    print(f"Performance:")
    baseline_time = results['baseline']['duration']
    enhanced_time = results['enhanced']['duration']
    ratio = enhanced_time / baseline_time if baseline_time > 0 else 0
    print(f"  Baseline duration: {baseline_time:.1f}s")
    print(f"  Enhanced duration: {enhanced_time:.1f}s")
    if ratio < 2.0:
        print(f"  ✅ Enhanced is {ratio:.1f}x baseline time (acceptable)")
    else:
        print(f"  ⚠️  Enhanced is {ratio:.1f}x baseline time (high overhead)")

    print()
    print(f"Improvements ({len(improvements)}):")
    if improvements:
        for axis in improvements:
            print(f"  ✅ {axis}")
    else:
        print("  None detected")

    print()
    print(f"Regressions ({len(regressions)}):")
    if regressions:
        for axis in regressions:
            print(f"  ⚠️  {axis}")
    else:
        print("  ✅ None detected")

    # Recommendation
    print()
    print("RECOMMENDATION:")
    improvement_rate = len(improvements) / len(test_axes) * 100
    regression_rate = len(regressions) / len(test_axes) * 100

    if improvement_rate >= 40 and regression_rate < 20:
        print("  ✅ DEPLOY BOTH FEATURES")
        print("     - Clear improvements on multiple axes")
        print("     - Minimal regressions")
        print("     - Performance overhead acceptable")
    elif improvement_rate >= 20 and regression_rate < 30:
        print("  ⚠️  DEPLOY ROBUST SCALING ONLY")
        print("     - Moderate improvements detected")
        print("     - Consider Dynamic K for specific axes only")
    else:
        print("  ⚠️  MORE VALIDATION NEEDED")
        print("     - Results inconclusive")
        print("     - Review segment interpretability manually")
        print("     - Consider testing on more axes or larger sample")

    print()
    print("="*80)
    print(f"Test complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
