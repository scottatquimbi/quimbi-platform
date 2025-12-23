"""
Modal-based weekly clustering job for Quimbi
Runs every Sunday at 0800 UTC with heavy compute resources
"""
import modal
from datetime import datetime

# Create Modal app
app = modal.App("quimbi-weekly-clustering")

# Define Docker image with dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "numpy",
        "pandas",
        "scikit-learn",
        "psycopg2-binary",
        "sqlalchemy",
        "asyncpg",
        "anthropic"
    )
)

# Heavy compute configuration (adjust as needed)
@app.function(
    image=image,
    schedule=modal.Cron("0 8 * * 0"),  # Every Sunday at 0800 UTC
    cpu=8.0,  # 8 CPU cores (can go up to 16)
    memory=32768,  # 32GB RAM (can go up to 128GB)
    timeout=3600,  # 1 hour max
    secrets=[
        modal.Secret.from_dict({
            "DATABASE_URL": "postgresql://...",  # Set this in Modal dashboard
            "ANTHROPIC_API_KEY": "sk-..."  # For AI segment naming
        })
    ],
)
async def weekly_clustering_job():
    """
    Main clustering job that runs weekly.
    Processes all stores and axes in parallel.
    """
    import os
    import sys
    sys.path.insert(0, "/root")

    from backend.segmentation.ecommerce_clustering_engine import EcommerceClusteringEngine

    start_time = datetime.now()
    print(f"🚀 Starting weekly clustering job at {start_time}")

    # Initialize engine with Railway database
    db_url = os.environ["DATABASE_URL"]
    anthropic_key = os.environ["ANTHROPIC_API_KEY"]

    engine = EcommerceClusteringEngine(
        db_url=db_url,
        anthropic_api_key=anthropic_key
    )

    # Get all active stores from database
    stores = await engine.get_active_stores()  # e.g., ["linda", "client2", "client3"]

    print(f"📊 Clustering {len(stores)} stores across 13 axes")

    results = {}

    # Process each store
    for store_id in stores:
        store_start = datetime.now()
        print(f"\n{'='*80}")
        print(f"Processing store: {store_id}")
        print(f"{'='*80}")

        try:
            # Discover segments across all axes
            segments = await engine.discover_multi_axis_segments(
                store_id=store_id,
                axes_to_cluster=None  # All 13 axes
            )

            # Store results in database (JSONB columns)
            await engine.store_segments_to_db(store_id, segments)

            # Update all customer profiles with fuzzy memberships
            await engine.update_customer_profiles(store_id, segments)

            store_duration = (datetime.now() - store_start).total_seconds()

            results[store_id] = {
                "status": "success",
                "segments_discovered": sum(len(segs) for segs in segments.values()),
                "axes_clustered": len(segments),
                "duration_seconds": store_duration,
                "customers_processed": await engine.get_customer_count(store_id)
            }

            print(f"✅ {store_id}: {results[store_id]['segments_discovered']} segments in {store_duration:.1f}s")

        except Exception as e:
            print(f"❌ Error processing {store_id}: {e}")
            results[store_id] = {
                "status": "error",
                "error": str(e)
            }

    total_duration = (datetime.now() - start_time).total_seconds()

    print(f"\n{'='*80}")
    print(f"✅ Weekly clustering complete!")
    print(f"{'='*80}")
    print(f"Total duration: {total_duration:.1f}s ({total_duration/60:.1f} min)")
    print(f"\nResults:")
    for store_id, result in results.items():
        if result["status"] == "success":
            print(f"  {store_id}: {result['segments_discovered']} segments, "
                  f"{result['customers_processed']} customers, "
                  f"{result['duration_seconds']:.1f}s")
        else:
            print(f"  {store_id}: ❌ {result['error']}")

    return results


# Parallel version (faster - all axes in parallel)
@app.function(
    image=image,
    cpu=2.0,
    memory=8192,
    timeout=600,
    secrets=[modal.Secret.from_dict({"DATABASE_URL": "postgresql://..."})],
)
async def cluster_single_axis(store_id: str, axis_name: str):
    """
    Cluster a single axis for a single store.
    Called in parallel by the orchestrator.
    """
    import os
    import sys
    sys.path.insert(0, "/root")

    from backend.segmentation.ecommerce_clustering_engine import EcommerceClusteringEngine

    db_url = os.environ["DATABASE_URL"]
    engine = EcommerceClusteringEngine(db_url=db_url)

    # Cluster just this one axis
    segments = await engine.discover_multi_axis_segments(
        store_id=store_id,
        axes_to_cluster=[axis_name]
    )

    return {
        "store_id": store_id,
        "axis_name": axis_name,
        "segments_discovered": len(segments.get(axis_name, [])),
        "status": "success"
    }


@app.function(
    schedule=modal.Cron("0 8 * * 0"),
    timeout=3600,
    secrets=[modal.Secret.from_dict({"DATABASE_URL": "postgresql://..."})],
)
async def parallel_clustering_orchestrator():
    """
    FASTEST VERSION: Orchestrates parallel clustering across all stores and axes.

    With 3 stores × 13 axes = 39 parallel functions, completes in ~10 minutes.
    """
    import asyncio
    from datetime import datetime

    start_time = datetime.now()
    print(f"🚀 Starting PARALLEL clustering at {start_time}")

    stores = ["linda", "client2", "client3"]  # TODO: Fetch from DB
    axes = [
        'purchase_frequency', 'purchase_value', 'category_exploration',
        'price_sensitivity', 'purchase_cadence', 'customer_maturity',
        'repurchase_behavior', 'return_behavior', 'communication_preference',
        'problem_complexity_profile', 'loyalty_trajectory', 'product_knowledge',
        'value_sophistication'
    ]

    # Spawn 39 parallel clustering jobs (3 stores × 13 axes)
    tasks = []
    for store_id in stores:
        for axis_name in axes:
            task = cluster_single_axis.spawn(store_id, axis_name)
            tasks.append((store_id, axis_name, task))

    print(f"📊 Spawned {len(tasks)} parallel clustering jobs")

    # Wait for all to complete
    results = []
    for store_id, axis_name, task in tasks:
        try:
            result = task.get()
            results.append(result)
            print(f"✅ {store_id}/{axis_name}: {result['segments_discovered']} segments")
        except Exception as e:
            print(f"❌ {store_id}/{axis_name}: {e}")
            results.append({
                "store_id": store_id,
                "axis_name": axis_name,
                "status": "error",
                "error": str(e)
            })

    total_duration = (datetime.now() - start_time).total_seconds()

    print(f"\n{'='*80}")
    print(f"✅ Parallel clustering complete in {total_duration:.1f}s ({total_duration/60:.1f} min)!")
    print(f"{'='*80}")

    # Group results by store
    by_store = {}
    for result in results:
        store = result["store_id"]
        if store not in by_store:
            by_store[store] = {"success": 0, "error": 0, "segments": 0}

        if result["status"] == "success":
            by_store[store]["success"] += 1
            by_store[store]["segments"] += result["segments_discovered"]
        else:
            by_store[store]["error"] += 1

    print(f"\nResults by store:")
    for store, stats in by_store.items():
        print(f"  {store}: {stats['segments']} segments across "
              f"{stats['success']} axes ({stats['error']} errors)")

    return by_store


# Manual trigger for testing
@app.local_entrypoint()
def test_clustering():
    """Run this locally to test: modal run modal_clustering_job.py"""
    print("Testing clustering job...")
    result = weekly_clustering_job.remote()
    print(f"Result: {result}")


if __name__ == "__main__":
    # For local testing
    import asyncio
    asyncio.run(weekly_clustering_job.local())
