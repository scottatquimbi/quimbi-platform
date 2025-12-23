"""
E-Commerce Feature Extraction Engine

Extracts behavioral features across 14 independent dimensions (axes):

Marketing Axes (1-8):
1. purchase_frequency - How often they buy
2. purchase_value - How much they spend
3. category_exploration - Product variety seeking
4. price_sensitivity - Discount dependency
5. purchase_cadence - When they buy (timing patterns)
6. customer_maturity - Lifecycle stage
7. repurchase_behavior - Loyalty and repeat purchases
8. return_behavior - Return/refund patterns

Support Axes (9-14):
9. communication_preference - Channel and timing preferences
10. problem_complexity_profile - Issue proneness
11. loyalty_trajectory - Engagement trend (churn risk)
12. product_knowledge - Expertise level
13. value_sophistication - Price point preferences
14. support_history - Past ticket behavior (requires Gorgias)

Each axis discovers natural behavioral clusters without hardcoded assumptions.

Author: Quimbi Platform (E-Commerce)
Version: 1.0.0
Date: November 6, 2025
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import logging
from scipy import stats

logger = logging.getLogger(__name__)


class EcommerceFeatureExtractor:
    """
    Extracts behavioral features from e-commerce order history.

    Input: Customer's orders and items
    Output: Feature vectors for each of 14 axes
    """

    def __init__(self, reference_date: Optional[datetime] = None):
        """
        Args:
            reference_date: Date to use as "now" (default: datetime.now())
        """
        self.reference_date = reference_date or datetime.now()


    def extract_all_features(
        self,
        customer_id: str,
        orders: List[Dict[str, Any]],
        items: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, float]]:
        """
        Extract features across all 14 axes.

        Args:
            customer_id: Customer identifier
            orders: List of order dicts
            items: List of item dicts

        Returns:
            {
                'purchase_frequency': {feature: value, ...},
                'purchase_value': {feature: value, ...},
                ...
            }
        """
        # Convert to DataFrames for easier manipulation
        orders_df = pd.DataFrame(orders) if orders else pd.DataFrame()
        items_df = pd.DataFrame(items) if items else pd.DataFrame()

        if orders_df.empty:
            return {}

        # Ensure date column is datetime
        orders_df['order_date'] = pd.to_datetime(orders_df['order_date'])

        features = {}

        # Marketing axes
        features['purchase_frequency'] = self.extract_frequency_features(orders_df)
        features['purchase_value'] = self.extract_value_features(orders_df)
        features['category_exploration'] = self.extract_category_features(items_df)
        features['price_sensitivity'] = self.extract_price_sensitivity_features(orders_df)
        features['purchase_cadence'] = self.extract_cadence_features(orders_df)
        features['customer_maturity'] = self.extract_maturity_features(orders_df)
        features['repurchase_behavior'] = self.extract_repurchase_features(items_df)
        features['return_behavior'] = self.extract_return_features(orders_df, items_df)

        # Support axes
        features['communication_preference'] = self.extract_communication_features(orders_df)
        features['problem_complexity_profile'] = self.extract_complexity_features(orders_df, items_df)
        features['loyalty_trajectory'] = self.extract_loyalty_trajectory_features(orders_df)
        features['product_knowledge'] = self.extract_knowledge_features(items_df)
        features['value_sophistication'] = self.extract_sophistication_features(orders_df, items_df)

        # Note: support_history (axis 14) requires Gorgias ticket data, not implemented here

        return features


    def extract_frequency_features(self, orders_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 1: Purchase Frequency

        How often customers buy and their ordering rhythm.
        """
        if orders_df.empty:
            return {}

        first_order = orders_df['order_date'].min()
        last_order = orders_df['order_date'].max()
        tenure_days = (self.reference_date - first_order).days
        tenure_months = tenure_days / 30.44

        total_orders = len(orders_df)

        # Orders per month
        orders_per_month = total_orders / tenure_months if tenure_months > 0 else 0

        # Average days between orders
        if total_orders > 1:
            sorted_dates = orders_df['order_date'].sort_values()
            gaps = sorted_dates.diff().dt.days.dropna()
            avg_gap = gaps.mean()
            gap_std = gaps.std()
        else:
            avg_gap = tenure_days
            gap_std = 0

        # Purchase consistency (inverse of coefficient of variation)
        consistency = 1.0 / (1.0 + gap_std / (avg_gap or 1))

        # Recent activity (last 90 days)
        recent_90d = orders_df[orders_df['order_date'] >= self.reference_date - timedelta(days=90)]
        recent_orders_90d = len(recent_90d)

        # Days since last purchase (recency)
        days_since_last = (self.reference_date - last_order).days

        return {
            'orders_per_month': orders_per_month,
            'avg_days_between_orders': avg_gap,
            'purchase_consistency': consistency,
            'recent_orders_90d': recent_orders_90d,
            'days_since_last_purchase': days_since_last,
            'total_orders': total_orders
        }


    def extract_value_features(self, orders_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 2: Purchase Value

        How much customers spend and their value trajectory.
        """
        if orders_df.empty:
            return {}

        total_value = orders_df['total_price'].sum()
        avg_order_value = orders_df['total_price'].mean()
        median_order_value = orders_df['total_price'].median()
        max_order_value = orders_df['total_price'].max()

        # Value trend (linear regression over time)
        if len(orders_df) >= 3:
            orders_sorted = orders_df.sort_values('order_date').copy()
            orders_sorted['order_index'] = range(len(orders_sorted))

            slope, intercept, r_value, p_value, std_err = stats.linregress(
                orders_sorted['order_index'],
                orders_sorted['total_price']
            )
            value_trend = slope
        else:
            value_trend = 0

        # Value consistency
        value_std = orders_df['total_price'].std()
        value_cv = value_std / (avg_order_value or 1)  # Coefficient of variation

        return {
            'lifetime_value': total_value,
            'avg_order_value': avg_order_value,
            'median_order_value': median_order_value,
            'max_order_value': max_order_value,
            'value_trend': value_trend,
            'value_consistency': 1.0 / (1.0 + value_cv)
        }


    def extract_category_features(self, items_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 3: Category Exploration

        How diverse is their product selection?
        """
        if items_df.empty:
            return {}

        unique_categories = items_df['category'].nunique() if 'category' in items_df.columns else 0
        unique_products = items_df['product_id'].nunique() if 'product_id' in items_df.columns else 0

        total_items = len(items_df)

        # Category diversity (0-1, higher = more diverse)
        if 'category' in items_df.columns:
            category_counts = items_df['category'].value_counts()
            category_entropy = stats.entropy(category_counts)
            max_entropy = np.log(len(category_counts)) if len(category_counts) > 1 else 1
            category_diversity = category_entropy / max_entropy if max_entropy > 0 else 0
        else:
            category_diversity = 0

        # Product diversity (Herfindahl index)
        if 'product_id' in items_df.columns:
            product_counts = items_df.groupby('product_id')['quantity'].sum()
            total_qty = product_counts.sum()
            product_shares = product_counts / total_qty
            herfindahl = (product_shares ** 2).sum()
            product_diversity = 1 - herfindahl
        else:
            product_diversity = 0

        # Primary category dominance
        if 'category' in items_df.columns and 'quantity' in items_df.columns:
            category_qty = items_df.groupby('category')['quantity'].sum()
            primary_category_pct = category_qty.max() / category_qty.sum()
        else:
            primary_category_pct = 1.0

        return {
            'unique_categories': unique_categories,
            'unique_products': unique_products,
            'category_diversity': category_diversity,
            'product_diversity': product_diversity,
            'primary_category_dominance': primary_category_pct,
            'exploration_breadth': unique_products / (total_items or 1)
        }


    def extract_price_sensitivity_features(self, orders_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 4: Price Sensitivity

        How discount-dependent is the customer?
        """
        if orders_df.empty:
            return {}

        total_orders = len(orders_df)

        # Discount usage
        orders_with_discount = (orders_df['discount_amount'] > 0).sum()
        discount_rate = orders_with_discount / total_orders

        # Average discount when used
        if orders_with_discount > 0:
            avg_discount_amount = orders_df[orders_df['discount_amount'] > 0]['discount_amount'].mean()
            avg_discount_pct = (
                orders_df[orders_df['discount_amount'] > 0]['discount_amount'] /
                orders_df[orders_df['discount_amount'] > 0]['total_price']
            ).mean()
        else:
            avg_discount_amount = 0
            avg_discount_pct = 0

        # Full price ratio
        full_price_ratio = 1 - discount_rate

        return {
            'discount_rate': discount_rate,
            'avg_discount_amount': avg_discount_amount,
            'avg_discount_pct': avg_discount_pct,
            'full_price_ratio': full_price_ratio,
            'discount_dependency': discount_rate  # Alias
        }


    def extract_cadence_features(self, orders_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 5: Purchase Cadence

        When do customers buy? (temporal patterns)
        """
        if orders_df.empty:
            return {}

        orders_df = orders_df.copy()
        orders_df['dayofweek'] = orders_df['order_date'].dt.dayofweek
        orders_df['hour'] = orders_df['order_date'].dt.hour
        orders_df['is_weekend'] = orders_df['dayofweek'] >= 5
        orders_df['is_business_hours'] = orders_df['hour'].between(9, 17)

        total_orders = len(orders_df)

        # Weekend vs weekday
        weekend_orders = orders_df['is_weekend'].sum()
        weekday_orders = total_orders - weekend_orders
        weekend_vs_weekday_ratio = weekend_orders / (weekday_orders or 1)

        # Business hours ratio
        business_hours_ratio = orders_df['is_business_hours'].mean()

        # Time of day preference
        morning_orders = (orders_df['hour'] < 12).sum()
        afternoon_orders = orders_df['hour'].between(12, 17).sum()
        evening_orders = (orders_df['hour'] >= 17).sum()

        preferred_time_numeric = 0  # morning
        if afternoon_orders > morning_orders and afternoon_orders > evening_orders:
            preferred_time_numeric = 1
        elif evening_orders > morning_orders and evening_orders > afternoon_orders:
            preferred_time_numeric = 2

        return {
            'weekend_vs_weekday_ratio': weekend_vs_weekday_ratio,
            'business_hours_ratio': business_hours_ratio,
            'weekend_rate': weekend_orders / total_orders,
            'preferred_time_numeric': preferred_time_numeric,  # 0=morning, 1=afternoon, 2=evening
        }


    def extract_maturity_features(self, orders_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 6: Customer Maturity

        Where is the customer in their lifecycle?
        """
        if orders_df.empty:
            return {}

        first_order = orders_df['order_date'].min()
        tenure_days = (self.reference_date - first_order).days
        tenure_months = tenure_days / 30.44

        total_orders = len(orders_df)

        # Maturity score (0-5)
        maturity_score = 0
        if tenure_months >= 24: maturity_score += 2
        elif tenure_months >= 12: maturity_score += 1

        if total_orders >= 20: maturity_score += 3
        elif total_orders >= 10: maturity_score += 2
        elif total_orders >= 5: maturity_score += 1

        # Lifecycle stage
        if tenure_months < 3:
            lifecycle_stage = 0  # new
        elif tenure_months < 12:
            lifecycle_stage = 1  # developing
        elif tenure_months < 24:
            lifecycle_stage = 2  # established
        else:
            lifecycle_stage = 3  # mature

        # Order rate acceleration (recent vs historical)
        if tenure_months >= 6:
            recent_3mo = orders_df[orders_df['order_date'] >= self.reference_date - timedelta(days=90)]
            recent_rate = len(recent_3mo) / 3  # Orders per month

            historical_rate = total_orders / tenure_months
            acceleration = (recent_rate - historical_rate) / (historical_rate or 1)
        else:
            acceleration = 0

        return {
            'tenure_months': tenure_months,
            'customer_maturity_score': maturity_score,
            'lifecycle_stage': lifecycle_stage,
            'orders_per_tenure_month': total_orders / (tenure_months or 1),
            'acceleration': acceleration
        }


    def extract_repurchase_features(self, items_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 7: Repurchase Behavior

        How loyal/repetitive are their purchases?
        """
        if items_df.empty:
            return {}

        total_items = len(items_df)

        # Product repurchase rate
        if 'product_id' in items_df.columns:
            product_counts = items_df['product_id'].value_counts()
            products_bought_once = (product_counts == 1).sum()
            products_bought_multiple = (product_counts > 1).sum()

            repeat_product_rate = products_bought_multiple / len(product_counts)

            # Average repurchase count for repeated products
            if products_bought_multiple > 0:
                avg_repurchase_count = product_counts[product_counts > 1].mean()
            else:
                avg_repurchase_count = 0
        else:
            repeat_product_rate = 0
            avg_repurchase_count = 0

        # Loyalty index (concentration of purchases in top products)
        if 'product_id' in items_df.columns and 'quantity' in items_df.columns:
            product_qty = items_df.groupby('product_id')['quantity'].sum()
            total_qty = product_qty.sum()

            # Top 20% of products account for what % of quantity?
            n_top = max(1, int(len(product_qty) * 0.2))
            top_products_qty = product_qty.nlargest(n_top).sum()
            loyalty_index = top_products_qty / total_qty
        else:
            loyalty_index = 0

        return {
            'repeat_product_rate': repeat_product_rate,
            'avg_repurchase_count': avg_repurchase_count,
            'loyalty_index': loyalty_index,
            'purchase_variety': 1 - loyalty_index  # Inverse
        }


    def extract_return_features(self, orders_df: pd.DataFrame, items_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 8: Return Behavior

        Return and refund patterns.
        """
        if items_df.empty:
            return {}

        total_items = len(items_df)
        lifetime_value = orders_df['total_price'].sum() if not orders_df.empty else 0

        # Refund metrics
        if 'refund_amount' in items_df.columns:
            total_refunds = items_df['refund_amount'].sum()
            items_with_refund = (items_df['refund_amount'] > 0).sum()

            refund_rate = total_refunds / lifetime_value if lifetime_value > 0 else 0
            items_returned_pct = items_with_refund / total_items
        else:
            refund_rate = 0
            items_returned_pct = 0
            total_refunds = 0

        return {
            'refund_rate': refund_rate,
            'items_returned_pct': items_returned_pct,
            'total_refunds': total_refunds,
            'has_returns': 1.0 if total_refunds > 0 else 0.0
        }


    def extract_communication_features(self, orders_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 9: Communication Preference

        How customers prefer to interact (channel, timing).
        """
        if orders_df.empty:
            return {}

        total_orders = len(orders_df)

        # Channel preference
        if 'source' in orders_df.columns:
            channel_counts = orders_df['source'].value_counts()
            primary_channel = channel_counts.index[0] if len(channel_counts) > 0 else 'unknown'
            channel_diversity = len(channel_counts)

            # Encode primary channel numerically
            channel_map = {'web': 0, 'pos': 1, 'shopify_draft_order': 2}
            primary_channel_numeric = channel_map.get(primary_channel, -1)

            # Channel switching rate
            if len(orders_df) > 1:
                orders_sorted = orders_df.sort_values('order_date')
                channel_switches = (orders_sorted['source'] != orders_sorted['source'].shift()).sum() - 1
                channel_switching_rate = channel_switches / len(orders_df)
            else:
                channel_switching_rate = 0
        else:
            primary_channel_numeric = -1
            channel_diversity = 1
            channel_switching_rate = 0

        # Time preferences (from cadence features)
        orders_df = orders_df.copy()
        orders_df['dayofweek'] = orders_df['order_date'].dt.dayofweek
        orders_df['hour'] = orders_df['order_date'].dt.hour
        orders_df['is_weekend'] = orders_df['dayofweek'] >= 5

        weekend_ratio = orders_df['is_weekend'].sum() / (len(orders_df) - orders_df['is_weekend'].sum() or 1)

        return {
            'primary_channel_numeric': primary_channel_numeric,
            'channel_diversity': channel_diversity,
            'channel_switching_rate': channel_switching_rate,
            'weekend_vs_weekday_ratio': weekend_ratio
        }


    def extract_complexity_features(self, orders_df: pd.DataFrame, items_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 10: Problem Complexity Profile

        How problematic/complex are their purchases?
        """
        if orders_df.empty:
            return {}

        # Return/refund metrics (from return_behavior)
        return_features = self.extract_return_features(orders_df, items_df)

        # Product exploration as complexity proxy
        if not items_df.empty:
            unique_products = items_df['product_id'].nunique() if 'product_id' in items_df.columns else 0
            unique_products_vs_orders = unique_products / len(orders_df)

            # Category switching
            if 'category' in items_df.columns:
                category_switches = items_df['category'].nunique()
            else:
                category_switches = 0
        else:
            unique_products_vs_orders = 0
            category_switches = 0

        # Discount dependency (proxy for price disputes)
        discount_features = self.extract_price_sensitivity_features(orders_df)

        return {
            'refund_rate': return_features.get('refund_rate', 0),
            'items_returned_pct': return_features.get('items_returned_pct', 0),
            'unique_products_vs_orders': unique_products_vs_orders,
            'category_switching': category_switches,
            'discount_dependency': discount_features.get('discount_rate', 0)
        }


    def extract_loyalty_trajectory_features(self, orders_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 11: Loyalty & Engagement Trajectory

        Is customer engagement increasing or declining? (CHURN RISK)
        """
        if orders_df.empty or len(orders_df) < 2:
            return {}

        orders_sorted = orders_df.sort_values('order_date').copy()

        # Order frequency trend (linear regression)
        if len(orders_df) >= 3:
            first_order = orders_sorted['order_date'].iloc[0]
            orders_sorted['months_since_first'] = (
                (orders_sorted['order_date'] - first_order).dt.days / 30.44
            )

            # Trend in order frequency over time
            max_months = orders_sorted['months_since_first'].max()
            if max_months > 0:
                month_buckets = np.arange(0, max_months + 1)
                orders_per_month = []

                for month in month_buckets:
                    count = ((orders_sorted['months_since_first'] >= month) &
                             (orders_sorted['months_since_first'] < month + 1)).sum()
                    orders_per_month.append(count)

                if len(month_buckets) >= 2:
                    slope, _, _, _, _ = stats.linregress(month_buckets, orders_per_month)
                    order_frequency_trend = slope
                else:
                    order_frequency_trend = 0
            else:
                order_frequency_trend = 0
        else:
            order_frequency_trend = 0

        # Value trend
        if len(orders_df) >= 3:
            value_slope, _, _, _, _ = stats.linregress(
                range(len(orders_sorted)),
                orders_sorted['total_price'].values
            )
            value_trend = value_slope
        else:
            value_trend = 0

        # Recency momentum (gaps getting shorter or longer?)
        if len(orders_df) >= 3:
            gaps = orders_sorted['order_date'].diff().dt.days.dropna()
            if len(gaps) >= 2:
                gap_slope, _, _, _, _ = stats.linregress(range(len(gaps)), gaps.values)
                recency_momentum = -gap_slope  # Negative slope = getting faster (positive momentum)
            else:
                recency_momentum = 0
        else:
            recency_momentum = 0

        # Acceleration/deceleration phase
        recent_90d = orders_df[orders_df['order_date'] >= self.reference_date - timedelta(days=90)]
        prior_90d = orders_df[(orders_df['order_date'] >= self.reference_date - timedelta(days=180)) &
                               (orders_df['order_date'] < self.reference_date - timedelta(days=90))]

        recent_rate = len(recent_90d) / 3
        prior_rate = len(prior_90d) / 3 if len(prior_90d) > 0 else 0

        acceleration_phase = 1.0 if recent_rate > prior_rate * 1.5 else 0.0
        deceleration_phase = 1.0 if recent_rate < prior_rate * 0.5 else 0.0

        # Churn risk score (0-1)
        days_since_last = (self.reference_date - orders_sorted['order_date'].max()).days
        gaps = orders_sorted['order_date'].diff().dt.days.dropna()
        expected_gap = gaps.mean() if len(gaps) > 0 else 30

        churn_risk = min(1.0, days_since_last / (expected_gap * 2))

        return {
            'order_frequency_trend': order_frequency_trend,
            'value_trend': value_trend,
            'recency_momentum': recency_momentum,
            'acceleration_phase': acceleration_phase,
            'deceleration_phase': deceleration_phase,
            'churn_risk_score': churn_risk
        }


    def extract_knowledge_features(self, items_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 12: Product Knowledge & Expertise

        How much guidance does the customer need?
        """
        if items_df.empty:
            return {}

        # Product concentration (Herfindahl index)
        if 'product_id' in items_df.columns and 'quantity' in items_df.columns:
            product_qty = items_df.groupby('product_id')['quantity'].sum()
            total_qty = product_qty.sum()
            product_shares = product_qty / total_qty
            herfindahl = (product_shares ** 2).sum()
            product_concentration = herfindahl
        else:
            product_concentration = 0

        # Repeat product rate (from repurchase features)
        if 'product_id' in items_df.columns:
            product_counts = items_df['product_id'].value_counts()
            repeat_products = (product_counts > 1).sum()
            repeat_product_rate = repeat_products / len(product_counts)
        else:
            repeat_product_rate = 0

        # Category mastery (how many categories with 3+ purchases)
        if 'category' in items_df.columns:
            category_counts = items_df.groupby('category').size()
            categories_mastered = (category_counts >= 3).sum()
        else:
            categories_mastered = 0

        # Primary category dominance
        if 'category' in items_df.columns and 'quantity' in items_df.columns:
            category_qty = items_df.groupby('category')['quantity'].sum()
            primary_dominance = category_qty.max() / category_qty.sum()
        else:
            primary_dominance = 1.0

        return {
            'product_concentration': product_concentration,
            'repeat_product_rate': repeat_product_rate,
            'categories_mastered': categories_mastered,
            'primary_category_dominance': primary_dominance,
            'exploration_vs_loyalty': 1 - product_concentration
        }


    def extract_sophistication_features(self, orders_df: pd.DataFrame, items_df: pd.DataFrame) -> Dict[str, float]:
        """
        Axis 13: Value & Spend Sophistication

        How do customers perceive and extract value?
        """
        if orders_df.empty:
            return {}

        # Price point analysis
        if not items_df.empty and 'price' in items_df.columns:
            avg_item_price = items_df['price'].mean()
            price_variance = items_df['price'].std() / (avg_item_price or 1)
        else:
            avg_item_price = 0
            price_variance = 0

        # Discount hunting
        discount_features = self.extract_price_sensitivity_features(orders_df)

        # Spend consistency
        if 'total_price' in orders_df.columns:
            avg_order_value = orders_df['total_price'].mean()
            order_value_std = orders_df['total_price'].std()
            spend_consistency = 1.0 / (1.0 + order_value_std / (avg_order_value or 1))

            # Big splurge rate (orders > 2x average)
            big_splurges = (orders_df['total_price'] > avg_order_value * 2).sum()
            big_splurge_rate = big_splurges / len(orders_df)
        else:
            spend_consistency = 0
            big_splurge_rate = 0

        return {
            'avg_item_price': avg_item_price,
            'price_variance': price_variance,
            'discount_hunt_score': discount_features.get('discount_rate', 0),
            'full_price_comfort': discount_features.get('full_price_ratio', 0),
            'spend_consistency': spend_consistency,
            'big_splurge_rate': big_splurge_rate
        }
