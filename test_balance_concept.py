"""
Synthetic test to prove balance-aware k selection concept
"""
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Generate synthetic data with 3 natural clusters
np.random.seed(42)

# Cluster 1: 50 customers (low engagement)
cluster1 = np.random.normal(loc=[1, 300, 0.2], scale=[0.5, 100, 0.1], size=(50, 3))

# Cluster 2: 30 customers (medium engagement)
cluster2 = np.random.normal(loc=[3, 150, 0.6], scale=[0.8, 50, 0.15], size=(30, 3))

# Cluster 3: 20 customers (high engagement)
cluster3 = np.random.normal(loc=[8, 40, 0.9], scale=[2.0, 20, 0.1], size=(20, 3))

X = np.vstack([cluster1, cluster2, cluster3])

print("=" * 80)
print("BALANCE-AWARE K SELECTION - SYNTHETIC DATA TEST")
print("=" * 80)
print()
print(f"Generated 100 customers with 3 natural clusters (50, 30, 20)")
print(f"Features: [orders_per_month, days_between_orders, purchase_consistency]")
print()
print("Testing k values 2-8:")
print()
print(f"{'k':<4} {'Silhouette':<12} {'Balance':<12} {'Bal_Qual':<12} {'Combined':<12} {'Sizes':<30}")
print("-" * 80)

best_k = None
best_combined = -1

for k in range(2, 9):
    # Cluster
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)

    # Silhouette
    sil = silhouette_score(X, labels)

    # Balance (std/mean of cluster sizes)
    unique, counts = np.unique(labels, return_counts=True)
    balance = counts.std() / counts.mean()

    # Balance quality (NEW FORMULA: 40% silhouette + 60% balance)
    balance_quality = 1.0 - min(1.0, balance)
    combined = (0.4 * sil) + (0.6 * balance_quality)

    # Track best
    if combined > best_combined:
        best_combined = combined
        best_k = k

    # Cluster sizes
    sizes_str = ", ".join([str(c) for c in sorted(counts, reverse=True)])

    marker = " ← BEST" if k == best_k else ""
    print(f"{k:<4} {sil:<12.3f} {balance:<12.3f} {balance_quality:<12.3f} {combined:<12.3f} [{sizes_str}]{marker}")

print()
print("=" * 80)
print(f"RESULT: Best k={best_k} (combined score={best_combined:.3f})")
print()
print("Expected: k=3 (matches 3 natural clusters)")
print()
print("Key Insight:")
print("- OLD formula (silhouette only): k=2 wins (tight clusters, poor explanatory power)")
print("- NEW formula (40% sil + 60% balance): Should favor k with better balance")
print("=" * 80)
