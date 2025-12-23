"""
Churn Data Pipeline

Prepares point-in-time correct training data for churn prediction model.

Key Concepts:
- Observation Window: Historical period to extract features (default 180 days)
- Prediction Window: Future period to predict churn (default 90 days)
- Churn Definition: No purchase in N days = churned (default 90 days)

Point-in-Time Correctness:
- For each observation date, only use data BEFORE that date
- Label is based on future behavior AFTER the prediction window
- Prevents data leakage

Example:
    Observation Date: 2025-01-01
    Observation Window: 180 days (2024-07-05 to 2025-01-01)
    Prediction Window: 90 days (2025-01-01 to 2025-04-01)

    Features: Extracted from orders between 2024-07-05 and 2025-01-01
    Label: Did customer churn between 2025-01-01 and 2025-04-01?

Author: Quimbi ML Team
Version: 1.0.0
Date: November 12, 2025
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from backend.core.database import AsyncSessionLocal
from backend.segmentation.ecommerce_feature_extraction import EcommerceFeatureExtractor

logger = logging.getLogger(__name__)


class ChurnDataPipeline:
    """
    Prepares training data for churn prediction model.

    Creates point-in-time correct feature matrices where:
    - Features are extracted from observation window BEFORE observation date
    - Labels are based on behavior AFTER observation date
    """

    def __init__(
        self,
        observation_window_days: int = 180,  # Historical data to use for features
        prediction_window_days: int = 90,    # Predict churn in next 90 days
        churn_definition_days: int = 90       # No purchase in 90 days = churn
    ):
        """
        Args:
            observation_window_days: Days of history to extract features from
            prediction_window_days: Days into future to predict churn
            churn_definition_days: Days without purchase = churned
        """
        self.observation_window = observation_window_days
        self.prediction_window = prediction_window_days
        self.churn_definition = churn_definition_days
        self.feature_extractor = EcommerceFeatureExtractor()

        logger.info(
            f"ChurnDataPipeline initialized: "
            f"observation_window={observation_window_days}d, "
            f"prediction_window={prediction_window_days}d, "
            f"churn_definition={churn_definition_days}d"
        )


    async def create_training_dataset(
        self,
        start_date: datetime,
        end_date: datetime,
        sampling_interval_days: int = 30,
        min_orders_required: int = 2,
        max_customers_per_snapshot: Optional[int] = None
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Create point-in-time correct training dataset.

        Strategy:
        1. Create snapshots at regular intervals (e.g., monthly)
        2. For each snapshot, extract features from observation window
        3. Label based on future behavior in prediction window
        4. Combine all snapshots into single training set

        Args:
            start_date: Earliest observation date
            end_date: Latest observation date
            sampling_interval_days: Days between snapshots (default 30)
            min_orders_required: Minimum orders to include customer (default 2)
            max_customers_per_snapshot: Max customers per snapshot (for sampling)

        Returns:
            X: Feature matrix (DataFrame)
            y: Target labels (Series) - 1 = churned, 0 = retained
        """
        logger.info(
            f"Creating training dataset from {start_date.date()} to {end_date.date()} "
            f"with {sampling_interval_days}d sampling interval"
        )

        # Generate observation dates
        observation_dates = []
        current_date = start_date
        while current_date <= end_date:
            observation_dates.append(current_date)
            current_date += timedelta(days=sampling_interval_days)

        logger.info(f"Will create {len(observation_dates)} temporal snapshots")

        # Create snapshot for each observation date
        all_features = []
        all_labels = []

        for obs_date in observation_dates:
            logger.info(f"Processing snapshot for {obs_date.date()}...")

            # Get features and labels for this snapshot
            snapshot_features, snapshot_labels = await self._create_snapshot(
                observation_date=obs_date,
                min_orders_required=min_orders_required,
                max_customers=max_customers_per_snapshot
            )

            if len(snapshot_features) > 0:
                all_features.append(snapshot_features)
                all_labels.extend(snapshot_labels)
                logger.info(
                    f"  ✅ {len(snapshot_features)} customers, "
                    f"churn_rate={np.mean(snapshot_labels):.1%}"
                )
            else:
                logger.warning(f"  ⚠️ No customers for snapshot {obs_date.date()}")

        # Combine all snapshots
        if not all_features:
            raise ValueError("No training data generated - check date range and data availability")

        X = pd.concat(all_features, ignore_index=True)
        y = pd.Series(all_labels, name='churned')

        logger.info(
            f"✅ Training dataset created: "
            f"{len(X)} samples, {len(X.columns)} features, "
            f"churn_rate={y.mean():.1%}"
        )

        return X, y


    async def _create_snapshot(
        self,
        observation_date: datetime,
        min_orders_required: int = 2,
        max_customers: Optional[int] = None
    ) -> Tuple[pd.DataFrame, List[int]]:
        """
        Create single temporal snapshot with point-in-time correct features and labels.

        Args:
            observation_date: Date to create snapshot for
            min_orders_required: Minimum orders to include customer
            max_customers: Optional limit on customers (for sampling)

        Returns:
            features_df: Feature matrix for this snapshot
            labels: Churn labels (1 = churned, 0 = retained)
        """
        # Define time windows
        feature_start = observation_date - timedelta(days=self.observation_window)
        feature_end = observation_date
        label_end = observation_date + timedelta(days=self.prediction_window)

        logger.debug(
            f"Snapshot windows: features=[{feature_start.date()} to {feature_end.date()}], "
            f"labels=[{feature_end.date()} to {label_end.date()}]"
        )

        # Get customer data from database
        async with AsyncSessionLocal() as session:
            # This is a placeholder - in production, you'd query actual order data
            # For now, we'll use customer_profiles as proxy
            query = """
                WITH customer_orders AS (
                    -- This query would need to be adapted to your actual schema
                    -- For now, using customer_profiles as proxy
                    SELECT
                        customer_id,
                        total_orders,
                        days_since_last_purchase,
                        customer_tenure_days,
                        lifetime_value,
                        segment_memberships
                    FROM platform.customer_profiles
                    WHERE
                        total_orders >= :min_orders
                        -- In production, add date filters here
                )
                SELECT * FROM customer_orders
            """

            if max_customers:
                query += f" LIMIT {max_customers}"

            result = await session.execute(
                text(query),
                {"min_orders": min_orders_required}
            )

            customers = result.fetchall()

        if not customers:
            return pd.DataFrame(), []

        # Extract features and labels for each customer
        features_list = []
        labels_list = []

        for customer in customers:
            customer_id = str(customer.customer_id)

            # Extract features (from observation window)
            # In production, this would load actual orders filtered by date
            features = self._extract_features_for_snapshot(
                customer=customer,
                observation_date=observation_date
            )

            # Determine label (based on future behavior)
            # In production, this would check if customer made purchase after observation_date
            is_churned = self._calculate_churn_label(
                customer=customer,
                observation_date=observation_date,
                label_end_date=label_end
            )

            if features is not None:
                features_list.append(features)
                labels_list.append(1 if is_churned else 0)

        # Convert to DataFrame
        if features_list:
            features_df = pd.DataFrame(features_list)
            return features_df, labels_list
        else:
            return pd.DataFrame(), []


    def _extract_features_for_snapshot(
        self,
        customer: Any,
        observation_date: datetime
    ) -> Optional[Dict[str, float]]:
        """
        Extract ML features for a customer at observation date.

        This is a simplified version that works with customer_profiles.
        In production, this would:
        1. Load orders from observation window
        2. Use EcommerceFeatureExtractor to extract 13-axis features
        3. Flatten into single feature vector

        Args:
            customer: Database row with customer data
            observation_date: Reference date for feature extraction

        Returns:
            Dictionary of feature name -> value
        """
        try:
            # Get segment memberships (fuzzy clustering features)
            segment_memberships = customer.segment_memberships or {}

            # Extract RFM features
            features = {
                'total_orders': float(customer.total_orders or 0),
                'lifetime_value': float(customer.lifetime_value or 0),
                'days_since_last_purchase': float(customer.days_since_last_purchase or 0),
                'customer_tenure_days': float(customer.customer_tenure_days or 0),

                # Derived features
                'avg_order_value': (
                    float(customer.lifetime_value) / float(customer.total_orders)
                    if customer.total_orders > 0 else 0
                ),
                'orders_per_month': (
                    float(customer.total_orders) / (float(customer.customer_tenure_days) / 30.44)
                    if customer.customer_tenure_days > 0 else 0
                ),
                'recency_ratio': (
                    float(customer.days_since_last_purchase) / float(customer.customer_tenure_days)
                    if customer.customer_tenure_days > 0 else 0
                ),
            }

            # Add fuzzy membership strengths for each axis
            for axis_name, membership_dict in segment_memberships.items():
                if isinstance(membership_dict, dict):
                    for segment_id, membership_strength in membership_dict.items():
                        feature_name = f"fuzzy_{axis_name}_{segment_id}"
                        features[feature_name] = float(membership_strength)

            # TODO: In production, use EcommerceFeatureExtractor to get full 13-axis features:
            # orders = load_orders_in_window(customer_id, feature_start, feature_end)
            # items = load_items_in_window(customer_id, feature_start, feature_end)
            # axis_features = self.feature_extractor.extract_all_features(
            #     customer_id, orders, items
            # )
            # features.update(self._flatten_axis_features(axis_features))

            return features

        except Exception as e:
            logger.error(f"Error extracting features for customer {customer.customer_id}: {e}")
            return None


    def _calculate_churn_label(
        self,
        customer: Any,
        observation_date: datetime,
        label_end_date: datetime
    ) -> bool:
        """
        Determine if customer churned in prediction window.

        In production, this would:
        1. Check if customer made ANY purchase between observation_date and label_end_date
        2. If no purchase, they churned
        3. If purchase exists, they retained

        For now, using proxy logic based on days_since_last_purchase.

        Args:
            customer: Database row with customer data
            observation_date: Start of prediction window
            label_end_date: End of prediction window

        Returns:
            True if customer churned, False if retained
        """
        # Proxy logic (replace with actual query in production)
        days_since_last = customer.days_since_last_purchase or 0

        # If days_since_last > churn_definition, they've likely churned
        is_churned = days_since_last > self.churn_definition

        # TODO: In production, use actual order query:
        # orders_in_window = query_orders(
        #     customer_id,
        #     start_date=observation_date,
        #     end_date=label_end_date
        # )
        # is_churned = len(orders_in_window) == 0

        return is_churned


    def _flatten_axis_features(self, axis_features: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """
        Flatten nested axis features into single-level dictionary.

        Args:
            axis_features: {
                'purchase_frequency': {'total_purchases': 10, 'avg_days_between': 30, ...},
                'purchase_value': {'total_lifetime_value': 1000, 'avg_order_value': 100, ...},
                ...
            }

        Returns:
            {
                'purchase_frequency__total_purchases': 10,
                'purchase_frequency__avg_days_between': 30,
                'purchase_value__total_lifetime_value': 1000,
                ...
            }
        """
        flattened = {}

        for axis_name, features in axis_features.items():
            if isinstance(features, dict):
                for feature_name, value in features.items():
                    flat_key = f"{axis_name}__{feature_name}"
                    flattened[flat_key] = float(value) if value is not None else 0.0

        return flattened


    async def prepare_inference_features(
        self,
        customer_id: str,
        reference_date: Optional[datetime] = None
    ) -> Optional[pd.DataFrame]:
        """
        Prepare features for inference (predicting churn for a single customer).

        Args:
            customer_id: Customer to predict churn for
            reference_date: Date to use as "now" (default: datetime.now())

        Returns:
            Single-row DataFrame with features, ready for model.predict()
        """
        if reference_date is None:
            reference_date = datetime.now()

        # Load customer data
        async with AsyncSessionLocal() as session:
            query = """
                SELECT
                    customer_id,
                    total_orders,
                    days_since_last_purchase,
                    customer_tenure_days,
                    lifetime_value,
                    segment_memberships
                FROM platform.customer_profiles
                WHERE customer_id = :customer_id
            """

            result = await session.execute(
                text(query),
                {"customer_id": customer_id}
            )

            customer = result.fetchone()

        if not customer:
            logger.warning(f"Customer {customer_id} not found")
            return None

        # Extract features
        features = self._extract_features_for_snapshot(
            customer=customer,
            observation_date=reference_date
        )

        if features is None:
            return None

        # Convert to DataFrame
        features_df = pd.DataFrame([features])

        return features_df
