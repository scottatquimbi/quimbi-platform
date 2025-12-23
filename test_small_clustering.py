#!/usr/bin/env python3
"""
Small test of clustering pipeline with limited customers to verify data flow.
Tests: Tier 1 segments → Tier 2 profiling → Tier 3 archetypes
"""
import asyncio
import sys

sys.path.insert(0, '/Users/scottallen/quimbi-platform/packages/intelligence')

from backend.core.database import get_db_session
from backend.segmentation.multi_axis_clustering_engine import MultiAxisClusteringEngine
from backend.segmentation.archetype_analyzer import ArchetypeAnalyzer
from sqlalchemy import text

async def test_small_clustering():
    print("="*80)
    print("SMALL CLUSTERING TEST (100 customers)")
    print("="*80)

    # Initialize engine
    engine = MultiAxisClusteringEngine(
        min_k=2,
        max_k=5,  # Smaller for faster testing
        min_silhouette=0.25,
        min_population=50,  # Lower threshold for test
        use_ai_naming=False
    )

    # ========================================================================
    # TIER 1: K-MEANS CLUSTERING
    # ========================================================================
    print("\n[TIER 1] Running clustering on all data...")
    tier1_segments = await engine.discover_multi_axis_segments('linda_quilting')

    if not tier1_segments:
        print("❌ TIER 1 FAILED: No segments discovered")
        return

    print(f"\n✅ TIER 1 COMPLETE")
    print(f"   Axes: {len(tier1_segments)}")
    print(f"   Total segments: {sum(len(segs) for segs in tier1_segments.values())}")

    # Show segments per axis
    for axis, segs in tier1_segments.items():
        print(f"   - {axis}: {len(segs)} segments")

    # ========================================================================
    # TIER 2: TEST CUSTOMER PROFILING (100 customers only)
    # ========================================================================
    print(f"\n[TIER 2] Testing customer profiling...")

    # Get 100 customer IDs
    async with get_db_session() as session:
        query = text("SELECT DISTINCT customer_id FROM combined_sales WHERE customer_id IS NOT NULL LIMIT 100")
        result = await session.execute(query)
        customer_ids = [str(row.customer_id) for row in result.fetchall()]

    print(f"   Testing with {len(customer_ids)} customers...")

    customer_profiles = {}
    failed_count = 0

    for i, customer_id in enumerate(customer_ids):
        if i % 25 == 0:
            print(f"   Progress: {i}/{len(customer_ids)}...")

        try:
            # KEY TEST: Pass tier1_segments to profiling
            profile = await engine.calculate_customer_profile(
                customer_id,
                'linda_quilting',
                segments_dict=tier1_segments  # In-memory segments
            )

            if profile:
                customer_profiles[customer_id] = profile
            else:
                failed_count += 1
                if failed_count <= 3:
                    print(f"   ⚠️  Customer {customer_id}: No profile returned")
        except Exception as e:
            failed_count += 1
            if failed_count <= 3:
                print(f"   ❌ Customer {customer_id}: {type(e).__name__}: {str(e)[:80]}")

    success_count = len(customer_profiles)
    success_rate = (success_count / len(customer_ids)) * 100 if customer_ids else 0

    print(f"\n✅ TIER 2 COMPLETE")
    print(f"   Profiled: {success_count}/{len(customer_ids)} ({success_rate:.1f}%)")
    print(f"   Failed: {failed_count}")

    if success_count == 0:
        print("\n❌ TEST FAILED: No customers profiled")
        print("   Check: Are segments being passed correctly?")
        print("   Check: Does calculate_customer_profile accept segments_dict?")
        return

    # ========================================================================
    # TIER 3: TEST ARCHETYPE DISCOVERY
    # ========================================================================
    print(f"\n[TIER 3] Testing archetype discovery...")

    analyzer = ArchetypeAnalyzer()
    profile_list = list(customer_profiles.values())

    archetypes = analyzer.count_archetypes(
        profile_list,
        level="strength"
    )

    # Filter archetypes with at least 2 customers (lower threshold for test)
    archetypes = {
        sig: arch for sig, arch in archetypes.items()
        if arch.customer_count >= 2
    }

    print(f"\n✅ TIER 3 COMPLETE")
    print(f"   Archetypes discovered: {len(archetypes)}")

    if len(archetypes) > 0:
        sorted_archetypes = sorted(
            archetypes.items(),
            key=lambda x: x[1].customer_count,
            reverse=True
        )

        print(f"\n   Top 5 archetypes:")
        for i, (archetype_sig, arch_obj) in enumerate(sorted_archetypes[:5]):
            pct = arch_obj.population_percentage * 100
            print(f"   {i+1}. {arch_obj.customer_count} customers ({pct:.1f}%)")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Tier 1: {sum(len(segs) for segs in tier1_segments.values())} segments across {len(tier1_segments)} axes")
    print(f"✅ Tier 2: {success_count}/{len(customer_ids)} customers profiled ({success_rate:.1f}%)")
    print(f"✅ Tier 3: {len(archetypes)} archetypes discovered")

    if success_rate > 80 and len(archetypes) > 0:
        print(f"\n🎉 TEST PASSED! Pipeline is working correctly.")
        print(f"   Ready to run full clustering with 10,000 customers.")
    else:
        print(f"\n⚠️  TEST INCOMPLETE")
        if success_rate < 80:
            print(f"   - Customer profiling success rate too low: {success_rate:.1f}%")
        if len(archetypes) == 0:
            print(f"   - No archetypes discovered (expected at least a few)")

if __name__ == "__main__":
    asyncio.run(test_small_clustering())
