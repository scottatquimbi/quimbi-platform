import pandas as pd
import numpy as np

print("Reading data...")
customers = pd.read_csv('CUSTOMER_SEGMENTATION.csv')
products = pd.read_csv('COMBINED_SALES_DATA.csv')

print(f"Total customers: {len(customers):,}")
print(f"Total transactions: {len(products):,}")

# Create product category purchasing profiles per customer
print("\nBuilding category purchase profiles...")
category_profiles = products.groupby(['Customer_ID', 'Category'])['QTY'].sum().unstack(fill_value=0)

# Get product type profiles
print("Building product type profiles...")
product_type_profiles = products.groupby(['Customer_ID', 'ProductType'])['QTY'].sum().unstack(fill_value=0)

# Calculate spending per category
category_spending = products.groupby(['Customer_ID', 'Category'])['Sales'].sum().unstack(fill_value=0)

print("\nClassifying customers...")

# Initialize classification columns
customers['customer_type'] = 'Unknown'
customers['expertise_level'] = 'Unknown'
customers['primary_project_type'] = 'Unknown'

classifications = []

for idx, customer in customers.iterrows():
    customer_id = customer['Customer_ID']

    # Get customer's purchases
    cust_products = products[products['Customer_ID'] == customer_id]

    if len(cust_products) == 0:
        continue

    # Category breakdown
    category_breakdown = cust_products.groupby('Category')['QTY'].sum().to_dict()
    total_qty = sum(category_breakdown.values())

    # Product type breakdown
    product_type_breakdown = cust_products.groupby('ProductType')['QTY'].sum().to_dict()

    # Get percentages
    cat_pct = {k: v/total_qty for k, v in category_breakdown.items()}

    # === EXPERTISE LEVEL CLASSIFICATION ===
    expertise_signals = []

    # Signal 1: High LTV suggests professional/serious hobbyist
    if customer['lifetime_value'] > 1000:
        expertise_signals.append('high_spender')

    # Signal 2: Multiple categories suggests experience/knowledge
    if customer['unique_categories'] >= 4:
        expertise_signals.append('multi_category')

    # Signal 3: Machine-related purchases suggest serious quilter
    machine_qty = category_breakdown.get('Machine Related', 0)
    if machine_qty > 0:
        expertise_signals.append('machine_owner')

    # Signal 4: High frequency suggests active engagement
    if customer['total_orders'] >= 10:
        expertise_signals.append('frequent_buyer')

    # Signal 5: Thread purchases (consumable) suggest active production
    thread_qty = category_breakdown.get('Thread', 0)
    if thread_qty >= 10:
        expertise_signals.append('high_thread_user')

    # Signal 6: Batting purchases suggest finishing projects
    batting_qty = category_breakdown.get('Batting', 0)
    if batting_qty >= 5:
        expertise_signals.append('project_finisher')

    # Signal 7: Long tenure suggests sustained interest
    if customer['customer_tenure_days'] > 365:
        expertise_signals.append('long_term')

    # Classify expertise
    signal_count = len(expertise_signals)
    if signal_count >= 5:
        expertise = 'Professional/Hardcore Enthusiast'
    elif signal_count >= 3:
        expertise = 'Serious Hobbyist'
    elif signal_count >= 1:
        expertise = 'Casual Hobbyist'
    else:
        expertise = 'Beginner/Dabbler'

    # === CUSTOMER TYPE CLASSIFICATION ===
    customer_type = 'Unknown'

    # Business/Professional indicators
    if customer['lifetime_value'] > 5000 or customer['total_orders'] > 50:
        customer_type = 'Business/Professional'

    # Shop owner (buying for resale - high volume, diverse products)
    elif customer['total_orders'] > 20 and customer['unique_products'] > 50:
        customer_type = 'Potential Reseller'

    # Gift buyers (low engagement, small orders)
    elif customer['total_orders'] == 1 and customer['avg_order_value'] < 50 and customer['unique_categories'] == 1:
        customer_type = 'Gift Buyer'

    # Active quilter (regular purchases, consumables)
    elif thread_qty >= 5 or batting_qty >= 3:
        customer_type = 'Active Quilter'

    # Project-based (sporadic, medium orders)
    elif customer['total_orders'] <= 3 and customer['avg_order_value'] > 100:
        customer_type = 'Project-Based Buyer'

    # Browsers/explorers (small purchases, diverse categories)
    elif customer['unique_categories'] >= 3 and customer['avg_order_value'] < 75:
        customer_type = 'Explorer/Browser'

    else:
        customer_type = 'Casual Buyer'

    # === PROJECT TYPE INFERENCE ===
    project_type = 'Unknown'

    # Longarm quilter
    if 'Longarm' in str(cust_products['Title'].values) or machine_qty > 0:
        if customer['total_orders'] > 5:
            project_type = 'Longarm Quilter (Professional)'
        else:
            project_type = 'Longarm Quilter (Home)'

    # Apparel/garment maker
    elif cat_pct.get('Fabric', 0) > 0.6 and batting_qty == 0:
        project_type = 'Garment/Apparel Maker'

    # Traditional quilter
    elif batting_qty > 0 and thread_qty > 0:
        project_type = 'Traditional Quilter'

    # Thread artist/embroiderer
    elif cat_pct.get('Thread', 0) > 0.7:
        project_type = 'Thread Artist/Embroiderer'

    # Batting specialist (wholesaler or finishing service?)
    elif cat_pct.get('Batting', 0) > 0.8:
        project_type = 'Batting Specialist'

    # Notion collector/tool enthusiast
    elif cat_pct.get('Other', 0) > 0.7 and customer['unique_products'] > 10:
        project_type = 'Tool/Notion Enthusiast'

    # General crafter
    elif customer['unique_categories'] >= 4:
        project_type = 'Multi-Craft Generalist'

    else:
        # Use primary category
        if customer['primary_category'] == 'Thread':
            project_type = 'Thread-Focused'
        elif customer['primary_category'] == 'Fabric':
            project_type = 'Fabric-Focused'
        elif customer['primary_category'] == 'Batting':
            project_type = 'Batting-Focused'
        else:
            project_type = 'General Quilter'

    classifications.append({
        'Customer_ID': customer_id,
        'customer_type': customer_type,
        'expertise_level': expertise,
        'primary_project_type': project_type,
        'expertise_signals': ','.join(expertise_signals),
        'signal_count': signal_count
    })

# Create classification dataframe
class_df = pd.DataFrame(classifications)

# Merge with customer data
customers_classified = customers.merge(class_df, on='Customer_ID', how='left')

# Drop the duplicate columns from merge
customers_classified = customers_classified.drop(columns=['customer_type_x', 'expertise_level_x', 'primary_project_type_x'])
customers_classified = customers_classified.rename(columns={
    'customer_type_y': 'customer_type',
    'expertise_level_y': 'expertise_level',
    'primary_project_type_y': 'primary_project_type'
})

print("\nSaving classified customer data...")
customers_classified.to_csv('CUSTOMER_PROFILES.csv', index=False)

print(f"\n{'='*80}")
print("CUSTOMER PROFILE CLASSIFICATION RESULTS")
print(f"{'='*80}")

print(f"\nEXPERTISE LEVEL DISTRIBUTION:")
print(customers_classified['expertise_level'].value_counts())

print(f"\nCUSTOMER TYPE DISTRIBUTION:")
print(customers_classified['customer_type'].value_counts())

print(f"\nPRIMARY PROJECT TYPE DISTRIBUTION:")
print(customers_classified['primary_project_type'].value_counts())

# Detailed segment analysis
print(f"\n{'='*80}")
print("SEGMENT DEEP DIVE")
print(f"{'='*80}")

# Professional/Hardcore analysis
print("\nPROFESSIONAL/HARDCORE ENTHUSIASTS:")
hardcore = customers_classified[customers_classified['expertise_level'] == 'Professional/Hardcore Enthusiast']
if len(hardcore) > 0:
    print(f"  Count: {len(hardcore):,} ({len(hardcore)/len(customers_classified)*100:.1f}%)")
    print(f"  Avg LTV: ${hardcore['lifetime_value'].mean():,.2f}")
    print(f"  Median LTV: ${hardcore['lifetime_value'].median():,.2f}")
    print(f"  Avg orders: {hardcore['total_orders'].mean():.1f}")
    print(f"  Repeat rate: {(hardcore['is_repeat_customer'].sum()/len(hardcore)*100):.1f}%")
    print(f"  Top project types:")
    print(hardcore['primary_project_type'].value_counts().head(5))

# Serious hobbyist
print("\nSERIOUS HOBBYISTS:")
serious = customers_classified[customers_classified['expertise_level'] == 'Serious Hobbyist']
if len(serious) > 0:
    print(f"  Count: {len(serious):,} ({len(serious)/len(customers_classified)*100:.1f}%)")
    print(f"  Avg LTV: ${serious['lifetime_value'].mean():,.2f}")
    print(f"  Median LTV: ${serious['lifetime_value'].median():,.2f}")
    print(f"  Avg orders: {serious['total_orders'].mean():.1f}")
    print(f"  Repeat rate: {(serious['is_repeat_customer'].sum()/len(serious)*100):.1f}%")

# Business/Professional
print("\nBUSINESS/PROFESSIONAL CUSTOMERS:")
business = customers_classified[customers_classified['customer_type'] == 'Business/Professional']
if len(business) > 0:
    print(f"  Count: {len(business):,} ({len(business)/len(customers_classified)*100:.1f}%)")
    print(f"  Avg LTV: ${business['lifetime_value'].mean():,.2f}")
    print(f"  Total revenue: ${business['lifetime_value'].sum():,.2f}")
    print(f"  Revenue share: {(business['lifetime_value'].sum()/customers_classified['lifetime_value'].sum()*100):.1f}%")
    print(f"  Avg orders: {business['total_orders'].mean():.1f}")
    print(f"  Project types:")
    print(business['primary_project_type'].value_counts().head(5))

# Longarm quilters
print("\nLONGARM QUILTERS:")
longarm = customers_classified[customers_classified['primary_project_type'].str.contains('Longarm', na=False)]
if len(longarm) > 0:
    print(f"  Count: {len(longarm):,}")
    print(f"  Avg LTV: ${longarm['lifetime_value'].mean():,.2f}")
    print(f"  Avg orders: {longarm['total_orders'].mean():.1f}")
    print(f"  Professional vs Home:")
    print(longarm['primary_project_type'].value_counts())

# Active quilters
print("\nACTIVE QUILTERS:")
active = customers_classified[customers_classified['customer_type'] == 'Active Quilter']
if len(active) > 0:
    print(f"  Count: {len(active):,}")
    print(f"  Avg LTV: ${active['lifetime_value'].mean():,.2f}")
    print(f"  Avg orders: {active['total_orders'].mean():.1f}")
    print(f"  Repeat rate: {(active['is_repeat_customer'].sum()/len(active)*100):.1f}%")

print(f"\n{'='*80}")

# Export sample profiles for each segment
print("\nSAMPLE HIGH-VALUE PROFILES:")
top_profiles = customers_classified.nlargest(10, 'lifetime_value')[
    ['Customer_ID', 'lifetime_value', 'total_orders', 'expertise_level',
     'customer_type', 'primary_project_type', 'primary_category']
]
print(top_profiles.to_string(index=False))
