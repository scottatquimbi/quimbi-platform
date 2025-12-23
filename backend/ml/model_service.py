"""
ML Model Service

Provides a unified interface for loading and using ML models in production.

This service manages:
- Model loading and caching
- Feature preparation
- Prediction orchestration
- Fallback to rules-based logic if ML unavailable

Author: Quimbi ML Team
Version: 1.0.0
Date: November 12, 2025
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


class MLModelService:
    """
    Singleton service for ML model inference.

    Usage:
        service = MLModelService()
        service.load_models(churn_model_dir="models/churn/v1")

        result = await service.predict_churn(customer_id="12345")
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance


    def __init__(self):
        if self._initialized:
            return

        self.churn_model = None
        self.ltv_model = None
        self.churn_pipeline = None
        self.models_loaded = False

        self._initialized = True

        logger.info("MLModelService initialized (models not loaded)")


    def load_models(
        self,
        churn_model_dir: Optional[str] = None,
        ltv_model_dir: Optional[str] = None
    ) -> None:
        """
        Load ML models from disk.

        Args:
            churn_model_dir: Path to churn model directory
            ltv_model_dir: Path to LTV model directory
        """
        logger.info("Loading ML models...")

        # Load churn model
        if churn_model_dir:
            try:
                from backend.ml.churn_model import ChurnModel
                from backend.ml.churn_data_pipeline import ChurnDataPipeline

                self.churn_model = ChurnModel(model_path=churn_model_dir)
                self.churn_pipeline = ChurnDataPipeline()

                logger.info(f"✅ Churn model loaded from {churn_model_dir}")

            except Exception as e:
                logger.error(f"Failed to load churn model: {e}")
                self.churn_model = None

        # Load LTV model
        if ltv_model_dir:
            try:
                from backend.ml.ltv_model import LTVModel

                self.ltv_model = LTVModel(model_path=ltv_model_dir)

                logger.info(f"✅ LTV model loaded from {ltv_model_dir}")

            except Exception as e:
                logger.error(f"Failed to load LTV model: {e}")
                self.ltv_model = None

        self.models_loaded = (self.churn_model is not None or self.ltv_model is not None)

        if self.models_loaded:
            logger.info("✅ ML models ready for inference")
        else:
            logger.warning("⚠️ No ML models loaded - will use fallback logic")


    async def predict_churn(
        self,
        customer_id: str,
        reference_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Predict churn probability for a customer.

        Uses ML model if available, otherwise falls back to rules-based logic.

        Args:
            customer_id: Customer identifier
            reference_date: Date to use as "now" (default: datetime.now())

        Returns:
            {
                'customer_id': '12345',
                'churn_probability': 0.85,
                'is_at_risk': True,
                'confidence': 'high',
                'risk_level': 'critical',  # low, medium, high, critical
                'risk_factors': [...],
                'recommendation': '...',
                'model_version': 'ml_v1' or 'rules_v1'
            }
        """
        if reference_date is None:
            reference_date = datetime.now()

        # Try ML model first
        if self.churn_model is not None and self.churn_pipeline is not None:
            try:
                return await self._predict_churn_ml(customer_id, reference_date)
            except Exception as e:
                logger.error(f"ML churn prediction failed for {customer_id}: {e}")
                logger.info("Falling back to rules-based churn prediction")

        # Fallback to rules-based logic
        return self._predict_churn_rules(customer_id)


    async def _predict_churn_ml(
        self,
        customer_id: str,
        reference_date: datetime
    ) -> Dict[str, Any]:
        """
        Predict churn using ML model.

        Args:
            customer_id: Customer identifier
            reference_date: Reference date for features

        Returns:
            Churn prediction with ML metadata
        """
        # Prepare features
        features = await self.churn_pipeline.prepare_inference_features(
            customer_id=customer_id,
            reference_date=reference_date
        )

        if features is None:
            raise ValueError(f"Could not prepare features for customer {customer_id}")

        # Get prediction
        prediction = self.churn_model.predict_customer(features)

        # Map to standard output format
        churn_probability = prediction['churn_probability']
        is_at_risk = prediction['is_at_risk']

        # Determine risk level
        if churn_probability > 0.8:
            risk_level = "critical"
        elif churn_probability > 0.6:
            risk_level = "high"
        elif churn_probability > 0.4:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Generate recommendation
        recommendation = self._generate_retention_recommendation(
            risk_level=risk_level,
            risk_factors=prediction['risk_factors']
        )

        return {
            'customer_id': customer_id,
            'churn_probability': churn_probability,
            'is_at_risk': is_at_risk,
            'confidence': prediction['confidence'],
            'risk_level': risk_level,
            'risk_factors': prediction['risk_factors'],
            'protective_factors': prediction['protective_factors'],
            'recommendation': recommendation,
            'model_version': 'ml_v1',
            'model_threshold': prediction['threshold']
        }


    def _predict_churn_rules(self, customer_id: str) -> Dict[str, Any]:
        """
        Fallback rules-based churn prediction.

        This is the OLD implementation that will be replaced by ML.
        Kept for backward compatibility.

        Args:
            customer_id: Customer identifier

        Returns:
            Churn prediction using rules
        """
        # Import here to avoid circular dependency
        from mcp_server.segmentation_server import data_store

        if not data_store.loaded:
            return {"error": "Data not loaded"}

        if customer_id not in data_store.customers:
            return {"error": f"Customer {customer_id} not found"}

        profile = data_store.customers[customer_id]
        risk_score = 0.0
        risk_factors = []

        # Rule 1: Check purchase frequency strength
        if profile['membership_strengths'].get('purchase_frequency') == 'weak':
            risk_score += 0.3
            risk_factors.append({
                'feature': 'purchase_frequency',
                'value': 'weak',
                'importance': 0.3
            })

        # Rule 2: Check days since last purchase
        days_since = profile.get('days_since_last_purchase', 0)
        if days_since > 90:
            risk_score += 0.3
            risk_factors.append({
                'feature': 'days_since_last_purchase',
                'value': days_since,
                'importance': 0.3
            })

        # Rule 3: Check if occasional buyer
        freq_segment = profile['dominant_segments'].get('purchase_frequency', '')
        if 'occasional' in freq_segment or 'one_time' in freq_segment:
            risk_score += 0.2
            risk_factors.append({
                'feature': 'purchase_pattern',
                'value': freq_segment,
                'importance': 0.2
            })

        # Rule 4: Check shopping maturity
        if 'new' in profile['dominant_segments'].get('shopping_maturity', ''):
            risk_score += 0.2
            risk_factors.append({
                'feature': 'customer_maturity',
                'value': 'new',
                'importance': 0.2
            })

        risk_score = min(risk_score, 1.0)

        # Map to risk level
        if risk_score > 0.7:
            risk_level = "critical"
        elif risk_score > 0.5:
            risk_level = "high"
        elif risk_score > 0.3:
            risk_level = "medium"
        else:
            risk_level = "low"

        recommendation = self._generate_retention_recommendation(risk_level, risk_factors)

        return {
            'customer_id': customer_id,
            'churn_probability': risk_score,
            'is_at_risk': risk_score > 0.5,
            'confidence': 'low',  # Rules always have low confidence
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'protective_factors': [],
            'recommendation': recommendation,
            'model_version': 'rules_v1'
        }


    def _generate_retention_recommendation(
        self,
        risk_level: str,
        risk_factors: list
    ) -> str:
        """
        Generate retention recommendation based on risk level and factors.

        Args:
            risk_level: Low, medium, high, or critical
            risk_factors: List of risk factor dicts

        Returns:
            Retention recommendation string
        """
        if risk_level == 'critical':
            return (
                "🚨 URGENT: Customer at critical churn risk. "
                "Send personalized re-engagement offer immediately. "
                "Consider VIP treatment or exclusive discount."
            )
        elif risk_level == 'high':
            return (
                "⚠️ HIGH RISK: Schedule immediate outreach. "
                "Send targeted campaign based on purchase history. "
                "Offer incentive to return."
            )
        elif risk_level == 'medium':
            return (
                "📧 Monitor closely. Send reminder email in next 7 days. "
                "Highlight new products or seasonal offers."
            )
        else:
            return (
                "✅ Low risk. Continue regular engagement. "
                "No immediate action needed."
            )


    async def predict_ltv(
        self,
        customer_id: str,
        reference_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Predict customer lifetime value.

        Args:
            customer_id: Customer identifier
            reference_date: Date to use as "now" (default: datetime.now())

        Returns:
            {
                'customer_id': '12345',
                'predicted_ltv': 450.75,
                'confidence_interval': {'low': 350.0, 'high': 550.0},
                'value_segment': 'medium',
                'prediction_window_months': 12,
                'key_drivers': [...]
            }
        """
        if self.ltv_model is None:
            return {
                'error': 'LTV model not loaded',
                'customer_id': customer_id
            }

        if reference_date is None:
            reference_date = datetime.now()

        try:
            # Prepare features (reuse churn pipeline for now)
            if self.churn_pipeline is None:
                from backend.ml.churn_data_pipeline import ChurnDataPipeline
                self.churn_pipeline = ChurnDataPipeline()

            features = await self.churn_pipeline.prepare_inference_features(
                customer_id=customer_id,
                reference_date=reference_date
            )

            if features is None:
                return {
                    'error': f'Could not prepare features for customer {customer_id}',
                    'customer_id': customer_id
                }

            # Get prediction
            prediction = self.ltv_model.predict_customer(features)
            prediction['customer_id'] = customer_id

            return prediction

        except Exception as e:
            logger.error(f"LTV prediction failed for {customer_id}: {e}")
            return {
                'error': str(e),
                'customer_id': customer_id
            }


# Global singleton instance
_model_service = MLModelService()


def get_model_service() -> MLModelService:
    """Get the global MLModelService instance."""
    return _model_service
