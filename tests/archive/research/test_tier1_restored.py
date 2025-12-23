"""
Test Tier 1 Clustering with Restored Algorithm and AI Naming

This script tests the adapted multi-axis clustering engine with:
- E-commerce order data (not gaming events)
- AI-powered segment naming (Claude API)
- K-means + fuzzy membership (exponential decay)
- 13 e-commerce axes

Expected outcomes:
- 13 axes clustered
- 3-8 segments per axis (40-60 total)
- AI-generated names (NOT "segment_0")
- Balanced distribution (no 98% in one segment)
- Silhouette scores > 0.3
"""

import asyncio
import sys
import json
from datetime import datetime

# Add parent to path
sys.path.insert(0, '/Users/scottallen/quimbi-platform/packages/intelligence')

from backend.segmentation.multi_axis_clustering_engine import MultiAxisClusteringEngine


async def test_tier1_clustering():
    print("="*80)
    print("TIER 1 CLUSTERING TEST - Restored Algorithm + AI Naming")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Initialize engine
    print("Step 1: Initializing clustering engine...")
    engine = MultiAxisClusteringEngine(
        min_k=2,
        max_k=6,  # Allow up to 6 segments per axis
        min_silhouette=0.3,
        min_population=50,  # Lower threshold for testing
        use_ai_naming=True
    )

    print(f"✓ Engine initialized")
    print(f"  - AI naming enabled: {engine.use_ai_naming}")
    print(f"  - API key set: {bool(engine.anthropic_api_key)}")
    print(f"  - Min k: {engine.min_k}, Max k: {engine.max_k}")
    print(f"  - Min silhouette: {engine.min_silhouette}")
    print(f"  - Min population: {engine.min_population}\n")

    # Run full discovery
    print("Step 2: Running multi-axis segmentation...")
    print("-"*80)

    try:
        segments = await engine.discover_multi_axis_segments('linda_quilting')

        print("\n" + "="*80)
        print("CLUSTERING COMPLETE!")
        print("="*80)

        if not segments:
            print("❌ ERROR: No segments discovered!")
            return False

        # Analyze results
        print(f"\n✓ Discovered {sum(len(s) for s in segments.values())} segments across {len(segments)} axes\n")

        total_segments = 0
        balanced_axes = 0
        ai_named_segments = 0
        fallback_named_segments = 0

        for axis, segs in segments.items():
            print(f"\n{'─'*80}")
            print(f"AXIS: {axis.upper()}")
            print(f"{'─'*80}")
            print(f"Segments: {len(segs)}")

            for seg in segs:
                total_segments += 1

                # Check naming type
                is_fallback = ("segment_" in seg.segment_name and
                              seg.segment_name.split("_")[-1].isdigit())

                if is_fallback:
                    fallback_named_segments += 1
                    naming_status = "⚠️  FALLBACK"
                else:
                    ai_named_segments += 1
                    naming_status = "✓ AI"

                # Check balance
                pct = seg.population_percentage * 100
                if pct < 50:
                    balance_status = "✓ Balanced"
                else:
                    balance_status = f"⚠️  Dominant ({pct:.1f}%)"

                print(f"\n  {naming_status} | {seg.segment_name}")
                print(f"     Population: {seg.customer_count:,} customers ({pct:.1f}%)")
                print(f"     {balance_status}")
                print(f"     Interpretation: {seg.interpretation[:100]}...")

            # Check if axis is balanced (no segment > 50%)
            max_pct = max(s.population_percentage for s in segs)
            if max_pct < 0.50:
                balanced_axes += 1

        # Final summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total axes clustered: {len(segments)} / 13")
        print(f"Total segments: {total_segments}")
        print(f"Average segments per axis: {total_segments / len(segments):.1f}")
        print(f"\nNaming:")
        print(f"  ✓ AI-named segments: {ai_named_segments} ({ai_named_segments/total_segments*100:.1f}%)")
        if fallback_named_segments > 0:
            print(f"  ⚠️  Fallback-named segments: {fallback_named_segments} ({fallback_named_segments/total_segments*100:.1f}%)")

        print(f"\nBalance:")
        print(f"  ✓ Balanced axes (no segment > 50%): {balanced_axes} / {len(segments)}")

        # Validation
        print("\n" + "="*80)
        print("VALIDATION")
        print("="*80)

        validation_passed = True

        # Check 1: Enough axes
        if len(segments) < 8:
            print(f"❌ FAIL: Only {len(segments)} axes clustered (expected at least 8)")
            validation_passed = False
        else:
            print(f"✓ PASS: {len(segments)} axes clustered")

        # Check 2: Enough segments
        if total_segments < 20:
            print(f"❌ FAIL: Only {total_segments} total segments (expected at least 20)")
            validation_passed = False
        else:
            print(f"✓ PASS: {total_segments} total segments")

        # Check 3: AI naming working
        if ai_named_segments < total_segments * 0.8:
            print(f"⚠️  WARNING: Only {ai_named_segments}/{total_segments} segments AI-named")
        else:
            print(f"✓ PASS: {ai_named_segments}/{total_segments} segments AI-named")

        # Check 4: No dominance problem
        if balanced_axes < len(segments) * 0.7:
            print(f"❌ FAIL: Only {balanced_axes}/{len(segments)} axes balanced")
            validation_passed = False
        else:
            print(f"✓ PASS: {balanced_axes}/{len(segments)} axes balanced")

        print("\n" + "="*80)
        if validation_passed:
            print("✓ TIER 1 TEST PASSED!")
        else:
            print("❌ TIER 1 TEST FAILED - See issues above")
        print("="*80)

        return validation_passed

    except Exception as e:
        print(f"\n❌ ERROR during clustering: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_tier1_clustering())
    sys.exit(0 if result else 1)
