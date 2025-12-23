"""
Load Clustering Results into Production Database

Loads the JSON output from run_full_clustering.py into the production database schema.

Input: /tmp/clustering_results.json
Output: Populated tables in production database
- dim_segment_master
- dim_archetype_combination
- fact_customer_fuzzy_memberships
- fact_customer_archetype
- clustering_run_metadata

Usage:
    DATABASE_URL="postgresql://..." python3 scripts/load_clustering_results.py
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
import uuid
from typing import Dict, Any, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database import get_db_session


async def load_clustering_results(
    results_file: str = '/tmp/clustering_results.json',
    store_id: str = 'linda_quilting'
):
    """Load clustering results from JSON into database"""

    print("="*80)
    print("CLUSTERING RESULTS LOADER")
    print("="*80)
    print(f"Results file: {results_file}")
    print(f"Store ID: {store_id}\n")

    # Load results
    print("Loading results from JSON...")
    with open(results_file, 'r') as f:
        results = json.load(f)

    print(f"✓ Loaded results from {results['timestamp']}\n")

    async with get_db_session() as session:
        try:
            # ================================================================
            # TIER 1: Load Segments
            # ================================================================
            print("\n" + "="*80)
            print("TIER 1: LOADING SEGMENTS")
            print("="*80)

            tier1 = results['tier1']
            segments_loaded = 0

            for axis_name, segments in tier1['segments_by_axis'].items():
                print(f"\nAxis: {axis_name} ({len(segments)} segments)")

                for seg in segments:
                    # Generate segment ID
                    segment_id = str(uuid.uuid4())

                    # Insert segment
                    query = text("""
                        INSERT INTO dim_segment_master (
                            segment_id, store_id, axis_name, segment_name,
                            cluster_center, feature_names, scaler_params,
                            customer_count, population_percentage,
                            interpretation, last_clustered, created_at, updated_at
                        ) VALUES (
                            :segment_id, :store_id, :axis_name, :segment_name,
                            :cluster_center, :feature_names, :scaler_params,
                            :customer_count, :population_percentage,
                            :interpretation, :last_clustered, now(), now()
                        )
                        ON CONFLICT (segment_id) DO UPDATE SET
                            customer_count = EXCLUDED.customer_count,
                            population_percentage = EXCLUDED.population_percentage,
                            updated_at = now()
                    """)

                    await session.execute(query, {
                        'segment_id': segment_id,
                        'store_id': store_id,
                        'axis_name': axis_name,
                        'segment_name': seg['name'],
                        'cluster_center': json.dumps({}),  # Not in output, would need to save from clustering
                        'feature_names': [],  # Not in output
                        'scaler_params': json.dumps({}),  # Not in output
                        'customer_count': seg['population'],
                        'population_percentage': seg['percentage'],
                        'interpretation': seg['interpretation'],
                        'last_clustered': datetime.now(timezone.utc)
                    })

                    segments_loaded += 1

                print(f"  Loaded {len(segments)} segments")

            await session.commit()
            print(f"\n✓ Loaded {segments_loaded} total segments")

            # ================================================================
            # TIER 2: Load Archetypes
            # ================================================================
            print("\n" + "="*80)
            print("TIER 2: LOADING ARCHETYPES")
            print("="*80)

            tier2 = results['tier2']
            archetypes_loaded = 0

            print(f"Total archetypes: {tier2['total_archetypes']}")
            print(f"Loading top {len(tier2['top_archetypes'])} archetypes...")

            for arch in tier2['top_archetypes']:
                # Generate archetype ID from signature
                archetype_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, arch['signature']))

                # Insert archetype
                query = text("""
                    INSERT INTO dim_archetype_combination (
                        archetype_id, store_id, dominant_segments,
                        archetype_signature, customer_count, population_percentage,
                        last_calculated, created_at, updated_at
                    ) VALUES (
                        :archetype_id, :store_id, :dominant_segments,
                        :archetype_signature, :customer_count, :population_percentage,
                        :last_calculated, now(), now()
                    )
                    ON CONFLICT (archetype_id) DO UPDATE SET
                        customer_count = EXCLUDED.customer_count,
                        population_percentage = EXCLUDED.population_percentage,
                        updated_at = now()
                """)

                await session.execute(query, {
                    'archetype_id': archetype_id,
                    'store_id': store_id,
                    'dominant_segments': json.dumps({}),  # Would need to parse signature
                    'archetype_signature': arch['signature'],
                    'customer_count': arch['customer_count'],
                    'population_percentage': arch['percentage'],
                    'last_calculated': datetime.now(timezone.utc)
                })

                archetypes_loaded += 1

            await session.commit()
            print(f"\n✓ Loaded {archetypes_loaded} archetypes")

            # ================================================================
            # TIER 3: Load Customer Vectors
            # ================================================================
            print("\n" + "="*80)
            print("TIER 3: LOADING CUSTOMER VECTORS")
            print("="*80)

            tier3 = results['tier3']
            customers_loaded = 0

            print(f"Total customers: {tier3['total_customers']}")
            print(f"Loading sample vectors: {len(tier3['sample_vectors'])}...")

            for customer_id, vector in tier3['sample_vectors'].items():
                # Load fuzzy memberships per axis
                for axis_name, memberships in vector['fuzzy_memberships'].items():
                    # Find dominant segment
                    dominant_segment = max(memberships.items(), key=lambda x: x[1])

                    query = text("""
                        INSERT INTO fact_customer_fuzzy_memberships (
                            customer_id, store_id, axis_name,
                            segment_memberships, dominant_segment, dominant_membership_score,
                            calculated_at, created_at
                        ) VALUES (
                            :customer_id, :store_id, :axis_name,
                            :segment_memberships, :dominant_segment, :dominant_membership_score,
                            :calculated_at, now()
                        )
                        ON CONFLICT (customer_id, axis_name, store_id) DO UPDATE SET
                            segment_memberships = EXCLUDED.segment_memberships,
                            dominant_segment = EXCLUDED.dominant_segment,
                            dominant_membership_score = EXCLUDED.dominant_membership_score,
                            calculated_at = EXCLUDED.calculated_at
                    """)

                    await session.execute(query, {
                        'customer_id': customer_id,
                        'store_id': store_id,
                        'axis_name': axis_name,
                        'segment_memberships': json.dumps(memberships),
                        'dominant_segment': dominant_segment[0],
                        'dominant_membership_score': dominant_segment[1],
                        'calculated_at': datetime.now(timezone.utc)
                    })

                # Load archetype assignment
                if vector.get('archetype'):
                    archetype_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, vector['archetype']))

                    query = text("""
                        INSERT INTO fact_customer_archetype (
                            customer_id, store_id, archetype_id, archetype_signature,
                            dominant_segments, calculated_at, created_at, updated_at
                        ) VALUES (
                            :customer_id, :store_id, :archetype_id, :archetype_signature,
                            :dominant_segments, :calculated_at, now(), now()
                        )
                        ON CONFLICT (customer_id) DO UPDATE SET
                            archetype_id = EXCLUDED.archetype_id,
                            archetype_signature = EXCLUDED.archetype_signature,
                            dominant_segments = EXCLUDED.dominant_segments,
                            calculated_at = EXCLUDED.calculated_at,
                            updated_at = now()
                    """)

                    await session.execute(query, {
                        'customer_id': customer_id,
                        'store_id': store_id,
                        'archetype_id': archetype_id,
                        'archetype_signature': vector['archetype'],
                        'dominant_segments': json.dumps(vector['dominant_segments']),
                        'calculated_at': datetime.now(timezone.utc)
                    })

                customers_loaded += 1

            await session.commit()
            print(f"\n✓ Loaded {customers_loaded} customer vectors")

            # ================================================================
            # METADATA: Record Clustering Run
            # ================================================================
            print("\n" + "="*80)
            print("RECORDING CLUSTERING RUN METADATA")
            print("="*80)

            query = text("""
                INSERT INTO clustering_run_metadata (
                    store_id, run_started_at, run_completed_at, status,
                    config, total_customers, axes_clustered,
                    total_segments, total_archetypes, created_at
                ) VALUES (
                    :store_id, :run_started_at, :run_completed_at, :status,
                    :config, :total_customers, :axes_clustered,
                    :total_segments, :total_archetypes, now()
                )
            """)

            await session.execute(query, {
                'store_id': store_id,
                'run_started_at': datetime.fromisoformat(results['timestamp']),
                'run_completed_at': datetime.now(timezone.utc),
                'status': 'completed',
                'config': json.dumps({
                    'min_k': 2,
                    'max_k': 8,
                    'min_silhouette': 0.25,
                    'min_population': 100,
                    'use_ai_naming': True
                }),
                'total_customers': tier3['total_customers'],
                'axes_clustered': list(tier1['segments_by_axis'].keys()),
                'total_segments': tier1['total_segments'],
                'total_archetypes': tier2['total_archetypes']
            })

            await session.commit()
            print("✓ Clustering run metadata recorded")

            # ================================================================
            # SUMMARY
            # ================================================================
            print("\n" + "="*80)
            print("LOAD COMPLETE")
            print("="*80)
            print(f"\nTier 1 (Segments):")
            print(f"  - {segments_loaded} segments loaded")
            print(f"  - {tier1['axes']} axes")

            print(f"\nTier 2 (Archetypes):")
            print(f"  - {archetypes_loaded} archetypes loaded")
            print(f"  - {tier2['total_archetypes']} total archetypes discovered")

            print(f"\nTier 3 (Customer Vectors):")
            print(f"  - {customers_loaded} customer vectors loaded (sample)")
            print(f"  - {tier3['total_customers']} total customers profiled")

            print(f"\n✅ All data loaded successfully!")

        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error loading data: {e}")
            import traceback
            traceback.print_exc()
            raise


async def main():
    """Main entry point"""
    results_file = sys.argv[1] if len(sys.argv) > 1 else '/tmp/clustering_results.json'
    store_id = sys.argv[2] if len(sys.argv) > 2 else 'linda_quilting'

    await load_clustering_results(results_file, store_id)


if __name__ == "__main__":
    asyncio.run(main())
