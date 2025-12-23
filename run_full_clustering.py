"""
Full 3-Tier Clustering Pipeline

Tier 1: K-means clustering per axis with AI naming (40-60 segments)
Tier 2: Archetype combinations from Tier 1 segments (100-200 archetypes)
Tier 3: Individual customer fuzzy membership vectors

This runs on the full dataset from combined_sales.
"""

import asyncio
import sys
import json
from datetime import datetime
import numpy as np

sys.path.insert(0, '/Users/scottallen/quimbi-platform/packages/intelligence')

from backend.segmentation.multi_axis_clustering_engine import MultiAxisClusteringEngine
from backend.segmentation.archetype_analyzer import ArchetypeAnalyzer
from backend.core.database import get_db_session
from sqlalchemy import text


async def run_full_clustering():
    """Run complete 3-tier clustering pipeline"""

    print("="*80)
    print("FULL 3-TIER CLUSTERING PIPELINE")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # ========================================================================
    # TIER 1: Discover segments per axis
    # ========================================================================
    print("\n" + "="*80)
    print("TIER 1: K-MEANS CLUSTERING PER AXIS")
    print("="*80)

    engine = MultiAxisClusteringEngine(
        min_k=2,
        max_k=8,  # Allow up to 8 segments per axis for more granularity
        min_silhouette=0.25,  # Slightly lower threshold
        min_population=100,  # Need at least 100 customers
        use_ai_naming=False  # Disabled due to model 404 errors
    )

    print(f"Engine configuration:")
    print(f"  - K range: {engine.min_k}-{engine.max_k}")
    print(f"  - Min silhouette: {engine.min_silhouette}")
    print(f"  - Min population: {engine.min_population}")
    print(f"  - AI naming: {engine.use_ai_naming}")

    # Run Tier 1 clustering
    print(f"\nRunning multi-axis segmentation...")
    print(f"(This will take 5-15 minutes depending on data size)\n")

    tier1_segments = await engine.discover_multi_axis_segments('linda_quilting')

    if not tier1_segments:
        print("\n❌ TIER 1 FAILED: No segments discovered")
        return None

    # Tier 1 Summary
    total_segments = sum(len(segs) for segs in tier1_segments.values())
    print(f"\n{'='*80}")
    print(f"TIER 1 COMPLETE")
    print(f"{'='*80}")
    print(f"Axes clustered: {len(tier1_segments)}")
    print(f"Total segments: {total_segments}")
    print(f"Avg segments/axis: {total_segments/len(tier1_segments):.1f}")

    # Show segment summary
    print(f"\nSegment distribution:")
    for axis, segs in tier1_segments.items():
        print(f"  {axis}: {len(segs)} segments")
        for seg in segs[:2]:  # Show first 2 per axis
            print(f"    - {seg.segment_name} ({seg.population_percentage*100:.1f}%)")
        if len(segs) > 2:
            print(f"    ... and {len(segs)-2} more")

    # ========================================================================
    # TIER 2: Create archetypes from segment combinations
    # ========================================================================
    print(f"\n{'='*80}")
    print("TIER 2: ARCHETYPE CREATION")
    print(f"{'='*80}")

    # Load all customer profiles with their segment memberships
    print("Loading customer segment memberships...")

    # Validate Tier 1 results
    if not tier1_segments:
        print("❌ CRITICAL: No segments from Tier 1 to use for profiling")
        return

    print(f"✅ Using {len(tier1_segments)} axes with segments for profiling:")
    for axis, segs in tier1_segments.items():
        print(f"   - {axis}: {len(segs)} segments")

    async with get_db_session() as session:
        # Get ALL customer IDs (no limit - full production run)
        query = text("SELECT DISTINCT customer_id FROM combined_sales WHERE customer_id IS NOT NULL ORDER BY customer_id")
        result = await session.execute(query)
        customer_ids = [str(row.customer_id) for row in result.fetchall()]

    print(f"\n🚀 PRODUCTION RUN: Processing ALL {len(customer_ids)} customers...")

    # For each customer, get their dominant segment per axis
    customer_profiles = {}
    failed_count = 0

    for i, customer_id in enumerate(customer_ids):
        if i % 1000 == 0:
            success_rate = (len(customer_profiles) / max(1, i)) * 100 if i > 0 else 0
            print(f"  Progress: {i}/{len(customer_ids)} ({success_rate:.1f}% success rate)")

        # DEBUG: First customer detailed logging
        if i == 0:
            print(f"\n🔍 DEBUG: First customer {customer_id}")
            print(f"   Tier 1 axes: {list(tier1_segments.keys())}")
            print(f"   Segments passed: {type(tier1_segments)}")

        try:
            # Calculate customer profile WITH in-memory segments from Tier 1
            profile = await engine.calculate_customer_profile(
                customer_id,
                'linda_quilting',
                segments_dict=tier1_segments  # KEY FIX: Pass Tier 1 segments
            )

            if profile:
                customer_profiles[customer_id] = profile
                # DEBUG: First successful profile
                if i == 0:
                    print(f"   ✅ Profile created with {len(profile.axis_profiles)} axis profiles")
                    print(f"   Profile axes: {list(profile.axis_profiles.keys())}")
            else:
                failed_count += 1
                if failed_count <= 10:  # Show more errors
                    print(f"  ⚠️  Customer {customer_id}: No profile returned")
        except Exception as e:
            failed_count += 1
            if failed_count <= 10:  # Show more errors
                import traceback
                print(f"  ❌ Customer {customer_id}: {type(e).__name__}: {str(e)}")
                if i == 0:  # Full traceback for first customer
                    print(traceback.format_exc())
            continue

    print(f"\nSuccessfully profiled {len(customer_profiles)} customers")
    if failed_count > 0:
        print(f"Failed to profile {failed_count} customers ({(failed_count/len(customer_ids))*100:.1f}%)")

    # Create archetypes using the analyzer
    analyzer = ArchetypeAnalyzer()

    # Convert dict to list of profiles
    profile_list = list(customer_profiles.values())

    archetypes = analyzer.count_archetypes(
        profile_list,
        level="strength"  # Use strength binning (180-240 archetypes)
    )

    print(f"Archetypes discovered before filtering: {len(archetypes)}")
    if len(archetypes) > 0:
        customer_counts = [arch.customer_count for arch in archetypes.values()]
        print(f"Customer count range: {min(customer_counts)}-{max(customer_counts)}")
        print(f"Archetypes with >=10 customers: {sum(1 for c in customer_counts if c >= 10)}")

    # Filter out archetypes with less than 10 customers
    archetypes = {
        sig: arch for sig, arch in archetypes.items()
        if arch.customer_count >= 10
    }

    print(f"\n{'='*80}")
    print(f"TIER 2 COMPLETE")
    print(f"{'='*80}")
    print(f"Unique archetypes: {len(archetypes)}")
    if len(archetypes) > 0:
        print(f"Avg customers/archetype: {len(customer_profiles)/len(archetypes):.1f}")
    else:
        print(f"❌ WARNING: No archetypes discovered (expected 100-200)")
        print(f"Customer profiles loaded: {len(customer_profiles)}")

    # Show top 10 archetypes
    sorted_archetypes = sorted(
        archetypes.items(),
        key=lambda x: x[1].customer_count,  # x[1] is Archetype object
        reverse=True
    )

    print(f"\nTop 10 archetypes by population:")
    for i, (archetype_sig, arch_obj) in enumerate(sorted_archetypes[:10]):
        print(f"  {i+1}. {arch_obj.customer_count} customers ({arch_obj.population_percentage*100:.1f}%)")
        print(f"     Signature: {str(archetype_sig.dominant_tuple)[:100]}...")

    # ========================================================================
    # TIER 3: Generate individual customer vectors
    # ========================================================================
    print(f"\n{'='*80}")
    print("TIER 3: CUSTOMER FUZZY MEMBERSHIP VECTORS")
    print(f"{'='*80}")

    # For each customer, create their complete fuzzy membership vector
    print(f"Generating fuzzy membership vectors for {len(customer_profiles)} customers...")

    customer_vectors = {}

    for customer_id, profile in customer_profiles.items():
        # Create vector with fuzzy memberships across all segments
        vector = {}

        for axis_name, axis_profile in profile.axis_profiles.items():
            vector[axis_name] = axis_profile.memberships

        customer_vectors[customer_id] = {
            'fuzzy_memberships': vector,
            'dominant_segments': profile.dominant_segments,
            'archetype': None  # Will be filled from Tier 2
        }

        # Link to archetype
        for archetype_sig, arch_obj in archetypes.items():
            if customer_id in arch_obj.customer_ids:
                customer_vectors[customer_id]['archetype'] = str(archetype_sig.dominant_tuple)
                break

    print(f"\n{'='*80}")
    print(f"TIER 3 COMPLETE")
    print(f"{'='*80}")
    print(f"Customer vectors generated: {len(customer_vectors)}")

    # Show example vector
    example_id = list(customer_vectors.keys())[0]
    example = customer_vectors[example_id]

    print(f"\nExample customer vector (ID: {example_id}):")
    print(f"  Archetype: {example['archetype'][:80]}...")
    print(f"  Dominant segments:")
    for axis, segment in list(example['dominant_segments'].items())[:5]:
        memberships = example['fuzzy_memberships'][axis]
        top_membership = max(memberships.values())
        print(f"    {axis}: {segment} ({top_membership:.3f})")

    # ========================================================================
    # SAVE RESULTS
    # ========================================================================
    print(f"\n{'='*80}")
    print("SAVING RESULTS")
    print(f"{'='*80}")

    results = {
        'timestamp': datetime.now().isoformat(),
        'tier1': {
            'axes': len(tier1_segments),
            'total_segments': total_segments,
            'segments_by_axis': {
                axis: [
                    {
                        'name': seg.segment_name,
                        'population': seg.customer_count,
                        'percentage': seg.population_percentage,
                        'interpretation': seg.interpretation
                    }
                    for seg in segs
                ]
                for axis, segs in tier1_segments.items()
            }
        },
        'tier2': {
            'total_archetypes': len(archetypes),
            'top_archetypes': [
                {
                    'signature': str(sig.dominant_tuple),
                    'customer_count': arch.customer_count,
                    'percentage': arch.population_percentage
                }
                for sig, arch in sorted_archetypes[:50]
            ]
        },
        'tier3': {
            'total_customers': len(customer_vectors),
            'sample_vectors': {
                cid: vec
                for cid, vec in list(customer_vectors.items())[:10]
            }
        }
    }

    output_file = '/tmp/clustering_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"✓ Results saved to: {output_file}")

    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    print(f"\n{'='*80}")
    print("COMPLETE 3-TIER CLUSTERING SUMMARY")
    print(f"{'='*80}")
    print(f"\nTier 1 (Segments):")
    print(f"  - {len(tier1_segments)} axes clustered")
    print(f"  - {total_segments} total segments")
    print(f"  - Average {total_segments/len(tier1_segments):.1f} segments per axis")

    print(f"\nTier 2 (Archetypes):")
    print(f"  - {len(archetypes)} unique behavioral archetypes")
    print(f"  - Combination of {len(tier1_segments)} dimensional segments")

    print(f"\nTier 3 (Customer Vectors):")
    print(f"  - {len(customer_vectors)} customers profiled")
    print(f"  - Each with {len(tier1_segments)}-dimensional fuzzy membership vector")
    print(f"  - Linked to archetype signature")

    print(f"\n{'='*80}")
    print("CLUSTERING PIPELINE COMPLETE!")
    print(f"{'='*80}\n")

    return {
        'tier1_segments': tier1_segments,
        'tier2_archetypes': archetypes,
        'tier3_vectors': customer_vectors
    }


if __name__ == "__main__":
    result = asyncio.run(run_full_clustering())
    sys.exit(0 if result else 1)
