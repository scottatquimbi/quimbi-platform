"""
Test Enhanced Clustering Features
Tests Dynamic K Optimization and Robust Outlier Handling

Run with:
    ENABLE_DYNAMIC_K_RANGE=true CLUSTERING_ROBUST_SCALING=true python test_enhanced_clustering.py
"""

import asyncio
import numpy as np
import logging
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_enhanced_features():
    """Test both Dynamic K and Robust Outlier Handling"""

    logger.info("=" * 70)
    logger.info("TESTING ENHANCED CLUSTERING FEATURES")
    logger.info("=" * 70)

    # Import clustering engine
    from backend.segmentation.ecommerce_clustering_engine import EcommerceClusteringEngine

    # Test configuration
    logger.info("\nConfiguration:")
    logger.info(f"  ENABLE_DYNAMIC_K_RANGE: {os.getenv('ENABLE_DYNAMIC_K_RANGE', 'false')}")
    logger.info(f"  CLUSTERING_ROBUST_SCALING: {os.getenv('CLUSTERING_ROBUST_SCALING', 'true')}")

    # Create engine with enhanced features
    engine = EcommerceClusteringEngine(
        min_k=2,
        max_k=10,  # Increased from 6 to test dynamic K
        min_silhouette=0.3,
        use_ai_naming=False  # Disable for speed
    )

    logger.info(f"\nEngine initialized:")
    logger.info(f"  Dynamic K enabled: {engine.enable_dynamic_k}")
    logger.info(f"  Robust scaling enabled: {engine.enable_robust_scaling}")

    if not engine.enable_dynamic_k and not engine.enable_robust_scaling:
        logger.warning("⚠️  Both features are DISABLED. Set environment variables to test!")
        logger.info("\nTo enable:")
        logger.info("  export ENABLE_DYNAMIC_K_RANGE=true")
        logger.info("  export CLUSTERING_ROBUST_SCALING=true")
        return

    # Test 1: Generate synthetic data with outliers
    logger.info("\n" + "=" * 70)
    logger.info("TEST 1: Robust Outlier Handling")
    logger.info("=" * 70)

    np.random.seed(42)

    # Create 3 clear clusters + outliers
    cluster1 = np.random.normal(0, 1, (300, 5))  # 300 customers, 5 features
    cluster2 = np.random.normal(5, 1, (250, 5))
    cluster3 = np.random.normal(10, 1, (200, 5))
    outliers = np.random.uniform(20, 50, (50, 5))  # Extreme outliers

    X = np.vstack([cluster1, cluster2, cluster3, outliers])

    logger.info(f"\nSynthetic data:")
    logger.info(f"  Total samples: {len(X)}")
    logger.info(f"  Normal clusters: 300, 250, 200 (750 total)")
    logger.info(f"  Outliers: 50 (extreme values 20-50)")
    logger.info(f"  Features: 5")

    # Test preprocessing
    X_scaled, scaler_params = engine._preprocess_features(X, "test_axis")

    logger.info(f"\nPreprocessing result:")
    logger.info(f"  Scaler type: {scaler_params['type']}")

    if scaler_params['type'] == 'robust':
        logger.info(f"  ✅ Using RobustScaler (median/IQR)")
        logger.info(f"  Winsorization: {engine.winsorize_percentile}th percentile")
        logger.info(f"  Expected: Outliers capped, don't distort scaling")
    else:
        logger.info(f"  Using StandardScaler (mean/std)")
        logger.info(f"  Expected: Outliers may distort clustering")

    # Test 2: Dynamic K optimization
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Dynamic K Optimization")
    logger.info("=" * 70)

    optimal_k, silhouette = engine._find_optimal_k(X_scaled, "test_axis")

    logger.info(f"\nOptimal K result:")
    logger.info(f"  Optimal k: {optimal_k}")
    logger.info(f"  Silhouette score: {silhouette:.3f}")

    if engine.enable_dynamic_k:
        logger.info(f"  ✅ Dynamic K optimization active")
        logger.info(f"  k-range tested: {engine.min_k} to {engine.max_k}")
        logger.info(f"  Expected: k=3 or k=4 (3 true clusters + maybe outlier cluster)")
    else:
        logger.info(f"  Fixed k-range used: {engine.min_k} to {engine.max_k}")

    # Test 3: Segment balance validation
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Segment Balance Validation")
    logger.info("=" * 70)

    from sklearn.cluster import KMeans
    kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # Count segment sizes
    from collections import Counter
    segment_counts = Counter(labels)
    segment_sizes = list(segment_counts.values())

    logger.info(f"\nSegment distribution:")
    for segment_id, count in sorted(segment_counts.items()):
        pct = count / len(X) * 100
        logger.info(f"  Segment {segment_id}: {count} customers ({pct:.1f}%)")

    largest_pct = max(segment_sizes) / len(X) * 100
    smallest_pct = min(segment_sizes) / len(X) * 100

    logger.info(f"\nBalance metrics:")
    logger.info(f"  Largest segment: {largest_pct:.1f}%")
    logger.info(f"  Smallest segment: {smallest_pct:.1f}%")
    logger.info(f"  Max allowed (dominant): {engine.max_dominant_segment_pct}%")
    logger.info(f"  Min allowed (segment): {engine.min_segment_size_pct}%")

    is_balanced = engine._validate_segment_balance(labels, len(X), "test_axis")

    if is_balanced:
        logger.info(f"  ✅ Segments are balanced!")
    else:
        logger.info(f"  ⚠️  Segments unbalanced (expected with 50 extreme outliers)")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)

    results = []

    if engine.enable_robust_scaling:
        results.append("✅ Robust Outlier Handling: ACTIVE")
    else:
        results.append("❌ Robust Outlier Handling: DISABLED")

    if engine.enable_dynamic_k:
        results.append(f"✅ Dynamic K Optimization: ACTIVE (k={optimal_k})")
    else:
        results.append(f"❌ Dynamic K Optimization: DISABLED (k={optimal_k})")

    if is_balanced:
        results.append("✅ Segment Balance: PASSED")
    else:
        results.append("⚠️  Segment Balance: NEEDS REVIEW")

    for result in results:
        logger.info(f"  {result}")

    logger.info(f"\nSilhouette Score: {silhouette:.3f}")
    if silhouette >= 0.5:
        logger.info("  ✅ Strong cluster separation")
    elif silhouette >= 0.3:
        logger.info("  ✅ Moderate cluster separation")
    else:
        logger.info("  ⚠️  Weak cluster separation")

    logger.info("\n" + "=" * 70)
    logger.info("NEXT STEPS")
    logger.info("=" * 70)

    if not engine.enable_dynamic_k or not engine.enable_robust_scaling:
        logger.info("\n1. Enable missing features:")
        if not engine.enable_dynamic_k:
            logger.info("     export ENABLE_DYNAMIC_K_RANGE=true")
        if not engine.enable_robust_scaling:
            logger.info("     export CLUSTERING_ROBUST_SCALING=true")
        logger.info("   Then re-run this test")

    logger.info("\n2. Test on real data:")
    logger.info("     python run_full_clustering.py")

    logger.info("\n3. Compare results:")
    logger.info("     - Check silhouette scores (should improve)")
    logger.info("     - Verify segment balance (largest < 50%, smallest > 3%)")
    logger.info("     - Review optimal k per axis (should vary, not all k=3-6)")

    logger.info("\n4. If results good, deploy to production:")
    logger.info("     - Update Railway environment variables")
    logger.info("     - Redeploy clustering job")
    logger.info("     - Monitor segment quality metrics")


if __name__ == "__main__":
    asyncio.run(test_enhanced_features())
