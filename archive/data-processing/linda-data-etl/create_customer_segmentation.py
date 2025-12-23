import pandas as pd
import numpy as np
from datetime import datetime

# Read combined data
print("Reading combined sales data...")
df = pd.read_csv('COMBINED_SALES_DATA.csv')

# Convert dates
df['Date_Customer'] = pd.to_datetime(df['Date_Customer'])
df['Date_Financial'] = pd.to_datetime(df['Date_Financial'])

# Get reference date (most recent date in dataset)
reference_date = df['Date_Customer'].max()
print(f"Reference date (most recent): {reference_date}")

print("\nBuilding customer-level features...")

# Group by customer
customer_features = []

for customer_id, customer_data in df.groupby('Customer_ID'):

    # Get order-level data (aggregate products to order level)
    orders = customer_data.groupby('OrderID').agg({
        'Date_Customer': 'first',
        'Date_Financial': 'first',
        'TotalPrice': 'first',
        'ItemQTY': 'first',
        'Source': 'first',
        'TotalDiscount': 'first',
        'Sales': 'sum',
        'QTY': 'sum'
    }).reset_index()

    # === 1. PURCHASE BEHAVIOR ===
    total_orders = len(orders)
    unique_products = customer_data['ProductId'].nunique()
    unique_categories = customer_data['Category'].nunique()
    unique_product_types = customer_data['ProductType'].nunique()

    # === 2. MONETARY VALUE ===
    total_lifetime_value = orders['TotalPrice'].sum()
    avg_order_value = orders['TotalPrice'].mean()
    total_items_purchased = customer_data['QTY'].sum()

    # === 3. TEMPORAL PATTERNS ===
    first_purchase_date = orders['Date_Customer'].min()
    last_purchase_date = orders['Date_Customer'].max()
    customer_tenure_days = (reference_date - first_purchase_date).days
    days_since_last_purchase = (reference_date - last_purchase_date).days

    # Purchase frequency
    if customer_tenure_days > 0:
        orders_per_month = (total_orders / customer_tenure_days) * 30.44
    else:
        orders_per_month = 0

    # Days between purchases (average)
    if total_orders > 1:
        purchase_dates = orders['Date_Customer'].sort_values()
        days_between = purchase_dates.diff().dt.days.dropna()
        avg_days_between_purchases = days_between.mean()
        std_days_between_purchases = days_between.std()
    else:
        avg_days_between_purchases = None
        std_days_between_purchases = None

    # === 4. RFM SCORES ===
    recency = days_since_last_purchase
    frequency = total_orders
    monetary = total_lifetime_value

    # === 5. CHANNEL BEHAVIOR ===
    channel_counts = orders['Source'].value_counts()
    primary_channel = channel_counts.index[0] if len(channel_counts) > 0 else None
    channels_used = orders['Source'].nunique()

    # Channel percentages
    pct_pos = (orders['Source'] == 'pos').sum() / total_orders if total_orders > 0 else 0
    pct_web = (orders['Source'] == 'web').sum() / total_orders if total_orders > 0 else 0
    pct_shopify = (orders['Source'] == 'shopify_draft_order').sum() / total_orders if total_orders > 0 else 0

    # === 6. PRODUCT CATEGORY AFFINITY ===
    category_counts = customer_data.groupby('Category')['QTY'].sum()
    primary_category = category_counts.idxmax() if len(category_counts) > 0 else None
    primary_category_pct = (category_counts.max() / category_counts.sum()) if category_counts.sum() > 0 else 0

    # === 7. TRANSACTION CHARACTERISTICS ===
    avg_items_per_order = orders['ItemQTY'].mean()
    avg_qty_per_order = orders['QTY'].sum() / total_orders if total_orders > 0 else 0

    # Discount behavior
    orders_with_discount = (orders['TotalDiscount'] > 0).sum()
    discount_rate = orders_with_discount / total_orders if total_orders > 0 else 0
    avg_discount_when_used = orders[orders['TotalDiscount'] > 0]['TotalDiscount'].mean() if orders_with_discount > 0 else 0

    # Refund behavior
    total_refunds = customer_data['Refunds'].fillna(0).sum()
    refund_rate = total_refunds / total_lifetime_value if total_lifetime_value > 0 else 0

    # === 8. SEASONALITY ===
    orders_by_quarter = orders.groupby(orders['Date_Customer'].dt.quarter).size()
    peak_quarter = orders_by_quarter.idxmax() if len(orders_by_quarter) > 0 else None

    orders_by_month = orders.groupby(orders['Date_Customer'].dt.month).size()
    peak_month = orders_by_month.idxmax() if len(orders_by_month) > 0 else None

    # Weekday vs Weekend
    orders['is_weekend'] = orders['Date_Customer'].dt.dayofweek >= 5
    weekend_orders = orders['is_weekend'].sum()
    pct_weekend = weekend_orders / total_orders if total_orders > 0 else 0

    # === 9. LOYALTY INDICATORS ===
    is_repeat_customer = total_orders > 1

    # Purchase velocity (last 3 months vs first 3 months)
    three_months_ago = reference_date - pd.Timedelta(days=90)
    recent_orders = orders[orders['Date_Customer'] >= three_months_ago]
    recent_order_count = len(recent_orders)

    # Customer status
    if days_since_last_purchase <= 90:
        customer_status = 'Active'
    elif days_since_last_purchase <= 180:
        customer_status = 'At Risk'
    else:
        customer_status = 'Churned'

    # === 10. PRODUCT DIVERSITY ===
    # Concentration (how focused vs diverse their purchases are)
    product_concentration = customer_data.groupby('ProductId')['QTY'].sum()
    herfindahl_index = ((product_concentration / product_concentration.sum()) ** 2).sum()

    # Compile features
    features = {
        'Customer_ID': customer_id,

        # Purchase Behavior
        'total_orders': total_orders,
        'unique_products': unique_products,
        'unique_categories': unique_categories,
        'unique_product_types': unique_product_types,

        # Monetary
        'lifetime_value': round(total_lifetime_value, 2),
        'avg_order_value': round(avg_order_value, 2),
        'total_items_purchased': int(total_items_purchased),

        # Temporal
        'first_purchase_date': first_purchase_date,
        'last_purchase_date': last_purchase_date,
        'customer_tenure_days': customer_tenure_days,
        'days_since_last_purchase': days_since_last_purchase,
        'avg_days_between_purchases': round(avg_days_between_purchases, 2) if avg_days_between_purchases else None,
        'std_days_between_purchases': round(std_days_between_purchases, 2) if std_days_between_purchases else None,
        'orders_per_month': round(orders_per_month, 2),

        # RFM
        'rfm_recency': recency,
        'rfm_frequency': frequency,
        'rfm_monetary': round(monetary, 2),

        # Channel
        'primary_channel': primary_channel,
        'channels_used': channels_used,
        'pct_pos': round(pct_pos, 3),
        'pct_web': round(pct_web, 3),
        'pct_shopify': round(pct_shopify, 3),

        # Category
        'primary_category': primary_category,
        'primary_category_pct': round(primary_category_pct, 3),

        # Transaction
        'avg_items_per_order': round(avg_items_per_order, 2),
        'avg_qty_per_order': round(avg_qty_per_order, 2),
        'discount_rate': round(discount_rate, 3),
        'avg_discount_when_used': round(avg_discount_when_used, 2),
        'total_refunds': round(total_refunds, 2),
        'refund_rate': round(refund_rate, 4),

        # Seasonality
        'peak_quarter': peak_quarter,
        'peak_month': peak_month,
        'pct_weekend_orders': round(pct_weekend, 3),

        # Loyalty
        'is_repeat_customer': is_repeat_customer,
        'recent_orders_3mo': recent_order_count,
        'customer_status': customer_status,

        # Diversity
        'product_concentration_herfindahl': round(herfindahl_index, 4)
    }

    customer_features.append(features)

# Create dataframe
customer_df = pd.DataFrame(customer_features)

# Sort by lifetime value descending
customer_df = customer_df.sort_values('lifetime_value', ascending=False)

# Save to CSV
print("\nSaving customer segmentation data...")
customer_df.to_csv('CUSTOMER_SEGMENTATION.csv', index=False)

print(f"\nCustomer segmentation dataset created!")
print(f"Total customers: {len(customer_df):,}")
print(f"Total features: {len(customer_df.columns)}")

# Summary statistics
print("\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)
print(f"\nCustomer Status Distribution:")
print(customer_df['customer_status'].value_counts())

print(f"\nPrimary Channel Distribution:")
print(customer_df['primary_channel'].value_counts())

print(f"\nRepeat vs One-time Customers:")
print(customer_df['is_repeat_customer'].value_counts())

print(f"\nLifetime Value Statistics:")
print(customer_df['lifetime_value'].describe())

print(f"\nAverage Order Value Statistics:")
print(customer_df['avg_order_value'].describe())

print("\nColumns in customer segmentation dataset:")
print(list(customer_df.columns))
