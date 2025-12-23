import pandas as pd

# Read the two CSV files
print("Reading SALES_DATA_ORDERS.csv...")
orders = pd.read_csv('SALES_DATA_ORDERS.csv')

print("Reading PRODUCT_SALES_ORDER.csv...")
products = pd.read_csv('PRODUCT_SALES_ORDER.csv')

# Merge the dataframes on Id/OrderID
print("Merging datasets...")
combined = products.merge(
    orders,
    left_on='OrderID',
    right_on='Id',
    how='left',
    suffixes=('', '_order')
)

# Rename date columns for clarity
combined = combined.rename(columns={
    'Date': 'Date_Customer',  # When customer placed order
    'date': 'Date_Financial'  # When sale was recognized/booked
})

# Drop duplicate columns (keeping product table versions)
columns_to_drop = [
    'Customer_ID_order',  # duplicate
    'Currency_order',  # duplicate
    'Year_order',  # duplicate
    'Month_order',  # duplicate
    'Week_order',  # duplicate
    'Day_order',  # duplicate
    'Source_order'  # duplicate
]

combined = combined.drop(columns=columns_to_drop)

# Save the combined dataset
print("Saving combined dataset...")
combined.to_csv('COMBINED_SALES_DATA.csv', index=False)

print(f"Combined dataset created with {len(combined)} rows and {len(combined.columns)} columns")
print(f"\nColumns in combined dataset:")
print(list(combined.columns))
