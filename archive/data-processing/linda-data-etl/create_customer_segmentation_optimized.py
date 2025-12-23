import pandas as pd
import numpy as np

# Read combined data
print("Reading combined sales data...")
df = pd.read_csv('COMBINED_SALES_DATA.csv')

# Convert dates
df['Date_Customer'] = pd.to_datetime(df['Date_Customer'])
df['Date_Financial'] = pd.to_datetime(df['Date_Financial'])

# Get reference date (most recent date in dataset)
reference_date = df['Date_Customer'].max()
print(f"Reference date (most recent): {reference_date}")

print("\nBuilding customer-level features (optimized)...")
print(f"Total rows: {len(df):,}")
print(f"Unique customers: {df['Customer_ID'].nunique():,}")

# Create order-level aggregations first
print("\nAggregating to order level...")
orders = df.groupby(['Customer_ID', 'OrderID']).agg({
    'Date_Customer': 'first',
    'Date_Financial': 'first',
    'TotalPrice': 'first',
    'ItemQTY': 'first',
    'Source': 'first',
    'TotalDiscount': 'first',
    'Sales': 'sum',
    'QTY': 'sum'
}).reset_index()

print(f"Total orders: {len(orders):,}")

# Calculate order-level features
orders['is_weekend'] = orders['Date_Customer'].dt.dayofweek >= 5
orders['has_discount'] = orders['TotalDiscount'] > 0
orders['quarter'] = orders['Date_Customer'].dt.quarter
orders['month'] = orders['Date_Customer'].dt.month

# Calculate customer-level aggregations
print("\nCalculating customer metrics...")

# Basic counts and sums
customer_agg = orders.groupby('Customer_ID').agg({
    'OrderID': 'count',  # total_orders
    'Date_Customer': ['min', 'max'],  # first and last purchase
    'TotalPrice': ['sum', 'mean'],  # lifetime value, avg order value
    'ItemQTY': 'mean',  # avg items per order
    'is_weekend': 'mean',  # pct weekend
    'has_discount': 'mean',  # discount rate
    'TotalDiscount': lambda x: x[x > 0].mean() if (x > 0).any() else 0,  # avg discount when used
}).reset_index()

# Flatten column names
customer_agg.columns = ['Customer_ID', 'total_orders', 'first_purchase_date', 'last_purchase_date',
                        'lifetime_value', 'avg_order_value', 'avg_items_per_order',
                        'pct_weekend_orders', 'discount_rate', 'avg_discount_when_used']

# Temporal metrics
customer_agg['customer_tenure_days'] = (reference_date - customer_agg['first_purchase_date']).dt.days
customer_agg['days_since_last_purchase'] = (reference_date - customer_agg['last_purchase_date']).dt.days
customer_agg['orders_per_month'] = (customer_agg['total_orders'] / customer_agg['customer_tenure_days'].replace(0, 1)) * 30.44

# RFM
customer_agg['rfm_recency'] = customer_agg['days_since_last_purchase']
customer_agg['rfm_frequency'] = customer_agg['total_orders']
customer_agg['rfm_monetary'] = customer_agg['lifetime_value']

# Customer status
customer_agg['customer_status'] = pd.cut(
    customer_agg['days_since_last_purchase'],
    bins=[-1, 90, 180, np.inf],
    labels=['Active', 'At Risk', 'Churned']
)

# Repeat customer flag
customer_agg['is_repeat_customer'] = customer_agg['total_orders'] > 1

# Recent orders (last 3 months)
three_months_ago = reference_date - pd.Timedelta(days=90)
recent_orders = orders[orders['Date_Customer'] >= three_months_ago].groupby('Customer_ID').size()
customer_agg['recent_orders_3mo'] = customer_agg['Customer_ID'].map(recent_orders).fillna(0).astype(int)

# Channel metrics
print("\nCalculating channel metrics...")
channel_data = orders.groupby('Customer_ID')['Source'].agg([
    ('primary_channel', lambda x: x.mode()[0] if len(x.mode()) > 0 else None),
    ('channels_used', 'nunique')
]).reset_index()

channel_pcts = pd.crosstab(orders['Customer_ID'], orders['Source'], normalize='index')
if 'pos' in channel_pcts.columns:
    channel_data['pct_pos'] = channel_pcts['pos']
else:
    channel_data['pct_pos'] = 0
if 'web' in channel_pcts.columns:
    channel_data['pct_web'] = channel_pcts['web']
else:
    channel_data['pct_web'] = 0
if 'shopify_draft_order' in channel_pcts.columns:
    channel_data['pct_shopify'] = channel_pcts['shopify_draft_order']
else:
    channel_data['pct_shopify'] = 0

customer_agg = customer_agg.merge(channel_data, on='Customer_ID', how='left')

# Seasonality
print("\nCalculating seasonality metrics...")
peak_quarter = orders.groupby('Customer_ID')['quarter'].agg(lambda x: x.mode()[0] if len(x.mode()) > 0 else None)
peak_month = orders.groupby('Customer_ID')['month'].agg(lambda x: x.mode()[0] if len(x.mode()) > 0 else None)
customer_agg['peak_quarter'] = customer_agg['Customer_ID'].map(peak_quarter)
customer_agg['peak_month'] = customer_agg['Customer_ID'].map(peak_month)

# Product diversity metrics
print("\nCalculating product diversity metrics...")
product_metrics = df.groupby('Customer_ID').agg({
    'ProductId': 'nunique',
    'Category': 'nunique',
    'ProductType': 'nunique',
    'QTY': 'sum',
    'Refunds': lambda x: x.fillna(0).sum()
}).reset_index()

product_metrics.columns = ['Customer_ID', 'unique_products', 'unique_categories',
                           'unique_product_types', 'total_items_purchased', 'total_refunds']

customer_agg = customer_agg.merge(product_metrics, on='Customer_ID', how='left')

# Primary category
print("\nCalculating category affinity...")
category_qty = df.groupby(['Customer_ID', 'Category'])['QTY'].sum().reset_index()
primary_cat = category_qty.loc[category_qty.groupby('Customer_ID')['QTY'].idxmax()][['Customer_ID', 'Category', 'QTY']]
primary_cat.columns = ['Customer_ID', 'primary_category', 'primary_category_qty']

total_qty = df.groupby('Customer_ID')['QTY'].sum().reset_index()
total_qty.columns = ['Customer_ID', 'total_qty']

primary_cat = primary_cat.merge(total_qty, on='Customer_ID')
primary_cat['primary_category_pct'] = primary_cat['primary_category_qty'] / primary_cat['total_qty']

customer_agg = customer_agg.merge(primary_cat[['Customer_ID', 'primary_category', 'primary_category_pct']],
                                  on='Customer_ID', how='left')

# Refund rate
customer_agg['refund_rate'] = customer_agg['total_refunds'] / customer_agg['lifetime_value'].replace(0, np.nan)
customer_agg['refund_rate'] = customer_agg['refund_rate'].fillna(0)

# Days between purchases (for repeat customers only)
print("\nCalculating purchase intervals...")
def calc_avg_days_between(group):
    if len(group) <= 1:
        return pd.Series({'avg_days_between_purchases': None, 'std_days_between_purchases': None})
    dates = group['Date_Customer'].sort_values()
    diffs = dates.diff().dt.days.dropna()
    return pd.Series({
        'avg_days_between_purchases': diffs.mean(),
        'std_days_between_purchases': diffs.std()
    })

purchase_intervals = orders.groupby('Customer_ID').apply(calc_avg_days_between).reset_index()
customer_agg = customer_agg.merge(purchase_intervals, on='Customer_ID', how='left')

# Round numeric columns
print("\nRounding numeric values...")
numeric_cols = customer_agg.select_dtypes(include=[np.number]).columns
for col in numeric_cols:
    if col not in ['Customer_ID', 'total_orders', 'unique_products', 'unique_categories',
                   'unique_product_types', 'customer_tenure_days', 'days_since_last_purchase',
                   'rfm_recency', 'rfm_frequency', 'channels_used', 'recent_orders_3mo',
                   'total_items_purchased', 'peak_quarter', 'peak_month']:
        customer_agg[col] = customer_agg[col].round(2)

# Sort by lifetime value
customer_agg = customer_agg.sort_values('lifetime_value', ascending=False)

# Save to CSV
print("\nSaving customer segmentation data...")
customer_agg.to_csv('CUSTOMER_SEGMENTATION.csv', index=False)

print(f"\nCustomer segmentation dataset created!")
print(f"Total customers: {len(customer_agg):,}")
print(f"Total features: {len(customer_agg.columns)}")

# Summary statistics
print("\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)
print(f"\nCustomer Status Distribution:")
print(customer_agg['customer_status'].value_counts())

print(f"\nPrimary Channel Distribution:")
print(customer_agg['primary_channel'].value_counts())

print(f"\nRepeat vs One-time Customers:")
print(customer_agg['is_repeat_customer'].value_counts())

print(f"\nLifetime Value Statistics:")
print(customer_agg['lifetime_value'].describe())

print("\nTop 10 customers by lifetime value:")
print(customer_agg[['Customer_ID', 'lifetime_value', 'total_orders', 'customer_status']].head(10))
