import pandas as pd

# Read the files
print("Reading files...")
orders = pd.read_csv('SALES_DATA_ORDERS.csv')
products = pd.read_csv('PRODUCT_SALES_ORDER.csv')

# Merge to compare dates
print("Merging and analyzing date mismatches...")
comparison = products.merge(orders, left_on='OrderID', right_on='Id', how='left', suffixes=('_prod', '_ord'))

# Convert dates to datetime
comparison['Date_prod'] = pd.to_datetime(comparison['Date'], errors='coerce')
comparison['Date_ord'] = pd.to_datetime(comparison['date'], errors='coerce')

# Find mismatches
date_mismatches = comparison[
    (comparison['Date_prod'].dt.date != comparison['Date_ord'].dt.date) &
    comparison['Date_prod'].notna() &
    comparison['Date_ord'].notna()
].copy()

print(f"\nTotal date mismatches: {len(date_mismatches):,}")

if len(date_mismatches) > 0:
    # Calculate date difference
    date_mismatches['date_diff_days'] = (date_mismatches['Date_prod'] - date_mismatches['Date_ord']).dt.days

    print("\n" + "="*80)
    print("DATE MISMATCH ANALYSIS")
    print("="*80)

    # Check ordering consistency
    sales_earlier = (date_mismatches['date_diff_days'] > 0).sum()
    product_earlier = (date_mismatches['date_diff_days'] < 0).sum()

    print(f"\nOrdering Pattern:")
    print(f"  Sales date earlier than Product date: {product_earlier:,} cases ({product_earlier/len(date_mismatches)*100:.2f}%)")
    print(f"  Product date earlier than Sales date: {sales_earlier:,} cases ({sales_earlier/len(date_mismatches)*100:.2f}%)")

    # Distribution of differences
    print(f"\nDate Difference Statistics (Product - Sales):")
    print(f"  Mean: {date_mismatches['date_diff_days'].mean():.2f} days")
    print(f"  Median: {date_mismatches['date_diff_days'].median():.2f} days")
    print(f"  Min: {date_mismatches['date_diff_days'].min()} days")
    print(f"  Max: {date_mismatches['date_diff_days'].max()} days")

    print(f"\nDistribution of differences:")
    diff_counts = date_mismatches['date_diff_days'].value_counts().sort_index()
    for diff, count in diff_counts.head(10).items():
        direction = "Product later" if diff > 0 else "Sales later"
        print(f"  {diff:+3d} days ({direction}): {count:,} cases")

    # Sample cases
    print(f"\nSample mismatches:")
    sample = date_mismatches[['OrderID', 'Date_prod', 'Date_ord', 'date_diff_days']].head(10)
    print(sample.to_string(index=False))

    # Check if there's a pattern by source
    print(f"\nMismatch rate by Source:")
    mismatch_by_source = date_mismatches['Source'].value_counts()
    total_by_source = comparison['Source'].value_counts()

    for source in total_by_source.index:
        mismatch_count = mismatch_by_source.get(source, 0)
        total_count = total_by_source[source]
        print(f"  {source}: {mismatch_count:,} / {total_count:,} ({mismatch_count/total_count*100:.2f}%)")

print("\n" + "="*80)
