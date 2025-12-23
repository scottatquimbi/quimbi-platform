import pandas as pd
import numpy as np

# Read customer segmentation data
print("Reading customer segmentation data...")
df = pd.read_csv('CUSTOMER_SEGMENTATION.csv')

print(f"Total customers: {len(df):,}")
print(f"Total features: {len(df.columns)}")

# Select numeric features for correlation analysis
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
# Remove ID
numeric_cols = [col for col in numeric_cols if col != 'Customer_ID']

print(f"\nAnalyzing {len(numeric_cols)} numeric features...")

# Calculate correlation matrix
corr_matrix = df[numeric_cols].corr()

# Find high correlations (excluding diagonal)
print("\n" + "="*80)
print("HIGH CORRELATIONS (|r| > 0.7)")
print("="*80)

high_corr_pairs = []
for i in range(len(corr_matrix.columns)):
    for j in range(i+1, len(corr_matrix.columns)):
        corr_val = corr_matrix.iloc[i, j]
        if abs(corr_val) > 0.7:
            high_corr_pairs.append({
                'Feature 1': corr_matrix.columns[i],
                'Feature 2': corr_matrix.columns[j],
                'Correlation': corr_val
            })

high_corr_df = pd.DataFrame(high_corr_pairs).sort_values('Correlation', key=abs, ascending=False)

for _, row in high_corr_df.iterrows():
    print(f"\n{row['Feature 1']} <-> {row['Feature 2']}")
    print(f"  Correlation: {row['Correlation']:.3f}")

# Interesting moderate correlations
print("\n" + "="*80)
print("INTERESTING MODERATE CORRELATIONS (0.4 < |r| < 0.7)")
print("="*80)

moderate_corr_pairs = []
for i in range(len(corr_matrix.columns)):
    for j in range(i+1, len(corr_matrix.columns)):
        corr_val = corr_matrix.iloc[i, j]
        if 0.4 < abs(corr_val) < 0.7:
            moderate_corr_pairs.append({
                'Feature 1': corr_matrix.columns[i],
                'Feature 2': corr_matrix.columns[j],
                'Correlation': corr_val
            })

moderate_corr_df = pd.DataFrame(moderate_corr_pairs).sort_values('Correlation', key=abs, ascending=False)

# Show top 20 most interesting
for _, row in moderate_corr_df.head(20).iterrows():
    print(f"\n{row['Feature 1']} <-> {row['Feature 2']}")
    print(f"  Correlation: {row['Correlation']:.3f}")

# Segment-based analysis
print("\n" + "="*80)
print("SEGMENT-BASED INSIGHTS")
print("="*80)

# Channel vs behavior patterns
print("\n1. CHANNEL PREFERENCE vs CUSTOMER BEHAVIOR:")
for channel in ['pct_pos', 'pct_web', 'pct_shopify']:
    channel_name = channel.replace('pct_', '').upper()
    high_channel = df[df[channel] > 0.8]
    if len(high_channel) > 0:
        print(f"\n{channel_name}-dominant customers (n={len(high_channel):,}):")
        print(f"  Avg LTV: ${high_channel['lifetime_value'].mean():,.2f}")
        print(f"  Avg orders: {high_channel['total_orders'].mean():.1f}")
        print(f"  Repeat rate: {(high_channel['is_repeat_customer'].sum() / len(high_channel) * 100):.1f}%")
        print(f"  Avg order value: ${high_channel['avg_order_value'].mean():,.2f}")

# Status vs metrics
print("\n2. CUSTOMER STATUS vs KEY METRICS:")
for status in df['customer_status'].unique():
    if pd.notna(status):
        status_df = df[df['customer_status'] == status]
        print(f"\n{status} customers (n={len(status_df):,}):")
        print(f"  Avg LTV: ${status_df['lifetime_value'].mean():,.2f}")
        print(f"  Avg tenure: {status_df['customer_tenure_days'].mean():.0f} days")
        print(f"  Avg orders: {status_df['total_orders'].mean():.1f}")
        print(f"  Discount rate: {status_df['discount_rate'].mean():.2%}")

# Repeat vs one-time
print("\n3. REPEAT vs ONE-TIME CUSTOMERS:")
repeat = df[df['is_repeat_customer'] == True]
onetime = df[df['is_repeat_customer'] == False]

print(f"\nRepeat customers (n={len(repeat):,}):")
print(f"  Avg LTV: ${repeat['lifetime_value'].mean():,.2f}")
print(f"  Avg orders: {repeat['total_orders'].mean():.1f}")
print(f"  Avg product diversity: {repeat['unique_categories'].mean():.1f} categories")
print(f"  Discount rate: {repeat['discount_rate'].mean():.2%}")
print(f"  Weekend shopping: {repeat['pct_weekend_orders'].mean():.2%}")

print(f"\nOne-time customers (n={len(onetime):,}):")
print(f"  Avg LTV: ${onetime['lifetime_value'].mean():,.2f}")
print(f"  Avg order value: ${onetime['avg_order_value'].mean():.2f}")
print(f"  Avg product diversity: {onetime['unique_categories'].mean():.1f} categories")
print(f"  Discount rate: {onetime['discount_rate'].mean():.2%}")
print(f"  Weekend shopping: {onetime['pct_weekend_orders'].mean():.2%}")

# High value vs low value
print("\n4. HIGH-VALUE vs LOW-VALUE CUSTOMERS:")
high_value = df[df['lifetime_value'] >= df['lifetime_value'].quantile(0.75)]
low_value = df[df['lifetime_value'] <= df['lifetime_value'].quantile(0.25)]

print(f"\nTop 25% customers (LTV >= ${df['lifetime_value'].quantile(0.75):.2f}, n={len(high_value):,}):")
print(f"  Avg orders: {high_value['total_orders'].mean():.1f}")
print(f"  Avg unique products: {high_value['unique_products'].mean():.1f}")
print(f"  Avg unique categories: {high_value['unique_categories'].mean():.1f}")
print(f"  Repeat rate: {(high_value['is_repeat_customer'].sum() / len(high_value) * 100):.1f}%")
print(f"  Primary channel distribution:")
print(high_value['primary_channel'].value_counts().head(5))

print(f"\nBottom 25% customers (LTV <= ${df['lifetime_value'].quantile(0.25):.2f}, n={len(low_value):,}):")
print(f"  Avg orders: {low_value['total_orders'].mean():.1f}")
print(f"  Avg unique products: {low_value['unique_products'].mean():.1f}")
print(f"  Avg unique categories: {low_value['unique_categories'].mean():.1f}")
print(f"  Repeat rate: {(low_value['is_repeat_customer'].sum() / len(low_value) * 100):.1f}%")
print(f"  Primary channel distribution:")
print(low_value['primary_channel'].value_counts().head(5))

# Discount sensitivity
print("\n5. DISCOUNT SENSITIVITY:")
high_discount = df[df['discount_rate'] > 0.5]
no_discount = df[df['discount_rate'] == 0]

if len(high_discount) > 0:
    print(f"\nHigh discount users (>50% orders with discount, n={len(high_discount):,}):")
    print(f"  Avg LTV: ${high_discount['lifetime_value'].mean():,.2f}")
    print(f"  Avg orders: {high_discount['total_orders'].mean():.1f}")
    print(f"  Repeat rate: {(high_discount['is_repeat_customer'].sum() / len(high_discount) * 100):.1f}%")

if len(no_discount) > 0:
    print(f"\nNever-discount users (n={len(no_discount):,}):")
    print(f"  Avg LTV: ${no_discount['lifetime_value'].mean():,.2f}")
    print(f"  Avg orders: {no_discount['total_orders'].mean():.1f}")
    print(f"  Repeat rate: {(no_discount['is_repeat_customer'].sum() / len(no_discount) * 100):.1f}%")

# Category preferences
print("\n6. PRIMARY CATEGORY INSIGHTS:")
top_categories = df['primary_category'].value_counts().head(5)
for category, count in top_categories.items():
    if pd.notna(category):
        cat_df = df[df['primary_category'] == category]
        print(f"\n{category} fans (n={count:,}):")
        print(f"  Avg LTV: ${cat_df['lifetime_value'].mean():,.2f}")
        print(f"  Avg orders: {cat_df['total_orders'].mean():.1f}")
        print(f"  Repeat rate: {(cat_df['is_repeat_customer'].sum() / len(cat_df) * 100):.1f}%")
        print(f"  Category concentration: {cat_df['primary_category_pct'].mean():.1%}")

# Seasonality patterns
print("\n7. SEASONALITY PATTERNS:")
print("\nPeak Quarter Distribution:")
print(df['peak_quarter'].value_counts().sort_index())

print("\nPeak Month Distribution:")
print(df['peak_month'].value_counts().sort_index())

# Weekend vs weekday shoppers
print("\n8. WEEKEND vs WEEKDAY SHOPPERS:")
weekend_shoppers = df[df['pct_weekend_orders'] > 0.5]
weekday_shoppers = df[df['pct_weekend_orders'] < 0.3]

if len(weekend_shoppers) > 0:
    print(f"\nWeekend-dominant shoppers (n={len(weekend_shoppers):,}):")
    print(f"  Avg LTV: ${weekend_shoppers['lifetime_value'].mean():,.2f}")
    print(f"  Avg orders: {weekend_shoppers['total_orders'].mean():.1f}")
    print(f"  Primary channel: {weekend_shoppers['primary_channel'].mode()[0] if len(weekend_shoppers) > 0 else 'N/A'}")

if len(weekday_shoppers) > 0:
    print(f"\nWeekday-dominant shoppers (n={len(weekday_shoppers):,}):")
    print(f"  Avg LTV: ${weekday_shoppers['lifetime_value'].mean():,.2f}")
    print(f"  Avg orders: {weekday_shoppers['total_orders'].mean():.1f}")
    print(f"  Primary channel: {weekday_shoppers['primary_channel'].mode()[0] if len(weekday_shoppers) > 0 else 'N/A'}")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
