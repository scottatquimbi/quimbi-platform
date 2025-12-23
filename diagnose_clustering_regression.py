#!/usr/bin/env python3
"""
Diagnose why clustering enhancements are causing regressions
"""

import asyncio
import numpy as np
from backend.segmentation.ecommerce_clustering_engine import EcommerceClusteringEngine

async def main():
    print("="*80)
    print("CLUSTERING REGRESSION DIAGNOSIS")
    print("="*80)
    print()

    # Sample 100 customers for quick diagnosis
    SAMPLE = 100

    print(f"Testing on {SAMPLE} customers\n")

    # Create engines
    baseline = EcommerceClusteringEngine(
        min_k=2, max_k=6,
        enable_dynamic_k=False,
        enable_robust_scaling=False,
        use_ai_naming=False
    )

    enhanced = EcommerceClusteringEngine(
        min_k=2, max_k=10,
        enable_dynamic_k=True,
        enable_robust_scaling=True,
        use_ai_naming=False
    )

    # Test one axis
    test_axis = 'purchase_frequency'
    print(f"Testing axis: {test_axis}\n")

    try:
        # Run baseline
        print("Running BASELINE clustering...")
        result_baseline = await baseline.discover_multi_axis_segments(
            store_id="diagnosis_baseline",
            axes_to_cluster=[test_axis],
            max_customers=SAMPLE
        )

        if test_axis in result_baseline and result_baseline[test_axis]:
            segments = result_baseline[test_axis]
            print(f"  Baseline found {len(segments)} segments")

            for i, seg in enumerate(segments):
                print(f"    Segment {i+1}: {seg.customer_count} customers ({seg.population_percentage*100:.1f}%)")
                print(f"      Scaler params: {seg.scaler_params}")

            # Check if silhouette is being stored
            if segments:
                print(f"\n  Silhouette score stored? {('silhouette' in segments[0].scaler_params)}")
                if 'silhouette' in segments[0].scaler_params:
                    print(f"  Silhouette value: {segments[0].scaler_params['silhouette']}")
        else:
            print("  ❌ Baseline failed to produce segments")

        print("\n" + "-"*80 + "\n")

        # Run enhanced
        print("Running ENHANCED clustering...")
        result_enhanced = await enhanced.discover_multi_axis_segments(
            store_id="diagnosis_enhanced",
            axes_to_cluster=[test_axis],
            max_customers=SAMPLE
        )

        if test_axis in result_enhanced and result_enhanced[test_axis]:
            segments = result_enhanced[test_axis]
            print(f"  Enhanced found {len(segments)} segments")

            for i, seg in enumerate(segments):
                print(f"    Segment {i+1}: {seg.customer_count} customers ({seg.population_percentage*100:.1f}%)")
                print(f"      Scaler params: {seg.scaler_params}")

            # Check if silhouette is being stored
            if segments:
                print(f"\n  Silhouette score stored? {('silhouette' in segments[0].scaler_params)}")
                if 'silhouette' in segments[0].scaler_params:
                    print(f"  Silhouette value: {segments[0].scaler_params['silhouette']}")
        else:
            print("  ❌ Enhanced failed to produce segments")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("DIAGNOSIS COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
