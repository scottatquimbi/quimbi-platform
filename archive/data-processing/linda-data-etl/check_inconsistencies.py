import pandas as pd
import numpy as np

# Read the files
print("Reading files...")
orders = pd.read_csv('SALES_DATA_ORDERS.csv')
products = pd.read_csv('PRODUCT_SALES_ORDER.csv')
combined = pd.read_csv('COMBINED_SALES_DATA.csv')

print("\n" + "="*80)
print("CONSISTENCY CHECK REPORT")
print("="*80)

# Check 1: Row count validation
print("\n1. ROW COUNT VALIDATION:")
print(f"   PRODUCT_SALES_ORDER rows: {len(products):,}")
print(f"   COMBINED_SALES_DATA rows: {len(combined):,}")
if len(products) == len(combined):
    print("   ✓ Row counts match")
else:
    print(f"   ✗ MISMATCH: Difference of {abs(len(products) - len(combined)):,} rows")

# Check 2: Verify all OrderIDs in products exist in orders
print("\n2. ORDER ID VALIDATION:")
missing_orders = set(products['OrderID']) - set(orders['Id'])
if len(missing_orders) == 0:
    print("   ✓ All OrderIDs in products table exist in orders table")
else:
    print(f"   ✗ ISSUE: {len(missing_orders)} OrderIDs in products not found in orders")
    print(f"   Sample missing IDs: {list(missing_orders)[:5]}")

# Check 3: Compare overlapping fields between products and orders
print("\n3. OVERLAPPING FIELD CONSISTENCY:")

# Map field names that differ
field_mappings = {
    'Date': 'date',
    'Customer_ID': 'Customer_ID',
    'Source': 'Source',
    'Currency': 'Currency',
    'Year': 'Year',
    'Month': 'Month',
    'Week': 'Week',
    'Day': 'Day'
}

# Merge to compare
comparison = products.merge(orders, left_on='OrderID', right_on='Id', how='left', suffixes=('_prod', '_ord'))

inconsistencies_found = False
for prod_field, ord_field in field_mappings.items():
    prod_col = prod_field if prod_field in comparison.columns else f"{prod_field}_prod"
    ord_col = f"{ord_field}_ord" if f"{ord_field}_ord" in comparison.columns else ord_field

    if prod_col in comparison.columns and ord_col in comparison.columns:
        # Handle date comparison separately (may have different formats)
        if 'date' in prod_field.lower() or 'date' in ord_field.lower():
            # Convert to datetime for comparison
            prod_dates = pd.to_datetime(comparison[prod_col], errors='coerce')
            ord_dates = pd.to_datetime(comparison[ord_col], errors='coerce')
            mismatches = (prod_dates.dt.date != ord_dates.dt.date) & prod_dates.notna() & ord_dates.notna()
        else:
            # Direct comparison for other fields
            mismatches = (comparison[prod_col] != comparison[ord_col]) & comparison[prod_col].notna() & comparison[ord_col].notna()

        mismatch_count = mismatches.sum()
        if mismatch_count > 0:
            inconsistencies_found = True
            print(f"   ✗ {prod_field}: {mismatch_count:,} mismatches found")
            # Show sample mismatches
            sample = comparison[mismatches][['OrderID', prod_col, ord_col]].head(3)
            print(f"     Sample mismatches:\n{sample.to_string(index=False)}")
        else:
            print(f"   ✓ {prod_field}: All values match")

if not inconsistencies_found:
    print("   ✓ All overlapping fields are consistent")

# Check 4: Verify combined table has correct merged data
print("\n4. COMBINED TABLE VALIDATION:")

# Sample some rows and verify the merge was done correctly
sample_orders = combined.sample(min(100, len(combined)), random_state=42)
validation_errors = []

for idx, row in sample_orders.iterrows():
    order_id = row['OrderID']

    # Get original order data
    orig_order = orders[orders['Id'] == order_id]

    if len(orig_order) == 0:
        validation_errors.append(f"OrderID {order_id} not found in orders table")
        continue

    orig_order = orig_order.iloc[0]

    # Check if order-specific fields match
    fields_to_check = ['Latitude', 'Longitude', 'FulfillmentStatus', 'FinancialStatus', 'TotalPrice', 'ItemQTY']
    for field in fields_to_check:
        if field in row.index and field in orig_order.index:
            combined_val = row[field]
            order_val = orig_order[field]

            # Handle NaN comparison
            if pd.isna(combined_val) and pd.isna(order_val):
                continue

            if combined_val != order_val:
                validation_errors.append(f"OrderID {order_id}: {field} mismatch (combined: {combined_val}, order: {order_val})")

if len(validation_errors) == 0:
    print(f"   ✓ Sample validation (100 rows): All merged fields match correctly")
else:
    print(f"   ✗ ISSUES FOUND: {len(validation_errors)} validation errors")
    print(f"   Sample errors:")
    for error in validation_errors[:5]:
        print(f"     - {error}")

# Check 5: Check for NULL/missing values introduced by merge
print("\n5. NULL VALUE ANALYSIS:")
# Count nulls in order-specific fields that were added by the merge
order_fields = ['Latitude', 'Longitude', 'FulfillmentStatus', 'FinancialStatus', 'TotalPrice', 'ItemQTY']
null_issues = []
for field in order_fields:
    if field in combined.columns:
        null_count = combined[field].isna().sum()
        if null_count > 0:
            null_issues.append(f"{field}: {null_count:,} nulls ({null_count/len(combined)*100:.2f}%)")

if null_issues:
    print("   Order fields with NULL values:")
    for issue in null_issues:
        print(f"     - {issue}")
else:
    print("   ✓ No NULL values in merged order fields")

# Check 6: Verify no duplicate rows were created
print("\n6. DUPLICATE CHECK:")
orig_dupes = products.duplicated().sum()
combined_dupes = combined.duplicated().sum()
print(f"   Original products duplicates: {orig_dupes:,}")
print(f"   Combined duplicates: {combined_dupes:,}")
if orig_dupes == combined_dupes:
    print("   ✓ No new duplicates introduced")
else:
    print(f"   ✗ WARNING: Duplicate count changed by {combined_dupes - orig_dupes}")

print("\n" + "="*80)
print("END OF REPORT")
print("="*80)
