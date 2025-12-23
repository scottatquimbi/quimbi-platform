"""
Customer Lifetime Value (LTV) Prediction Model

Predicts future customer spend using Gamma regression.

Model Architecture:
- Algorithm: Gamma Regression (GLM with log link)
- Target: 12-month future LTV (positive continuous value)
- Features: RFM metrics, behavioral features, fuzzy memberships

Why Gamma Regression?
1. LTV is positive and right-skewed (most customers low, few high)
2. Gamma distribution models positive continuous values
3. Log link function handles skewness naturally
4. Better than linear regression for monetary predictions
5. More interpretable than neural networks

Target Performance:
- MAE: $50-100 (Mean Absolute Error)
- RMSE: $150-250 (Root Mean Squared Error)
- R²: 0.60-0.75 (proportion of variance explained)

Author: Quimbi ML Team
Version: 1.0.0
Date: November 12, 2025
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pickle
import json
import logging
from pathlib import Path

from sklearn.linear_model import GammaRegressor
from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = logging.getLogger(__name__)


class LTVModel:
    """
    Predicts 12-month customer lifetime value using Gamma regression.

    Workflow:
    1. Train on historical purchase data
    2. Predict future 12-month spend
    3. Evaluate with MAE, RMSE, R²
    4. Deploy for inference
    """

    def __init__(
        self,
        prediction_window_months: int = 12,
        model_path: Optional[str] = None
    ):
        """
        Args:
            prediction_window_months: Months into future to predict (default 12)
            model_path: Path to saved model (for loading)
        """
        self.prediction_window = prediction_window_months
        self.model = None
        self.feature_names = None
        self.training_metadata = {}

        # Gamma regression hyperparameters
        # Alpha = regularization strength (higher = more regularization)
        self.alpha = 1.0
        self.max_iter = 100

        # Load existing model if path provided
        if model_path:
            self.load(model_path)


    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """
        Train Gamma regression model.

        Args:
            X_train: Training features
            y_train: Training targets (future LTV in dollars)
            X_val: Validation features (optional)
            y_val: Validation targets (optional)

        Returns:
            Training metrics
        """
        logger.info(f"Training LTV model on {len(X_train)} samples...")
        logger.info(f"Mean LTV: ${y_train.mean():.2f}, Median: ${y_train.median():.2f}")

        # Store feature names
        self.feature_names = list(X_train.columns)

        # Handle zero/negative values (Gamma requires positive targets)
        # Add small epsilon to ensure all values > 0
        epsilon = 0.01
        y_train_positive = y_train.clip(lower=epsilon)

        if (y_train_positive != y_train).any():
            n_adjusted = (y_train_positive != y_train).sum()
            logger.warning(
                f"Adjusted {n_adjusted} zero/negative LTV values to {epsilon}"
            )

        # Train Gamma regression
        self.model = GammaRegressor(
            alpha=self.alpha,
            max_iter=self.max_iter,
            verbose=1
        )

        self.model.fit(X_train, y_train_positive)

        # Evaluate on training set
        train_metrics = self.evaluate(X_train, y_train, dataset_name="train")

        # Evaluate on validation set if provided
        val_metrics = {}
        if X_val is not None and y_val is not None:
            val_metrics = self.evaluate(X_val, y_val, dataset_name="validation")

        # Store training metadata
        self.training_metadata = {
            'trained_at': datetime.now().isoformat(),
            'n_train_samples': len(X_train),
            'n_val_samples': len(X_val) if X_val is not None else 0,
            'train_mean_ltv': float(y_train.mean()),
            'train_median_ltv': float(y_train.median()),
            'num_features': len(self.feature_names),
            'feature_names': self.feature_names,
            'alpha': self.alpha,
            'prediction_window_months': self.prediction_window,
            'train_metrics': train_metrics,
            'val_metrics': val_metrics
        }

        logger.info(f"✅ Model trained")
        logger.info(f"   Train MAE: ${train_metrics['mae']:.2f}")
        logger.info(f"   Train R²: {train_metrics['r2']:.4f}")
        if val_metrics:
            logger.info(f"   Val MAE: ${val_metrics['mae']:.2f}")
            logger.info(f"   Val R²: {val_metrics['r2']:.4f}")

        return self.training_metadata


    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict future LTV.

        Args:
            X: Feature matrix

        Returns:
            Array of predicted LTV values (in dollars)
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() or load() first.")

        # Ensure columns match training features
        if self.feature_names:
            missing_cols = set(self.feature_names) - set(X.columns)
            if missing_cols:
                raise ValueError(f"Missing features: {missing_cols}")

            # Reorder columns to match training
            X = X[self.feature_names]

        predictions = self.model.predict(X)
        return predictions


    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        dataset_name: str = "test"
    ) -> Dict[str, float]:
        """
        Evaluate model performance.

        Args:
            X: Feature matrix
            y: True LTV values
            dataset_name: Name for logging

        Returns:
            Dictionary of metrics
        """
        # Get predictions
        y_pred = self.predict(X)

        # Calculate metrics
        mae = mean_absolute_error(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        r2 = r2_score(y, y_pred)

        # Calculate percentage errors
        mape = np.mean(np.abs((y - y_pred) / (y + 1e-10))) * 100  # Mean Absolute Percentage Error

        # Calculate error distribution
        errors = y - y_pred
        median_error = np.median(errors)
        error_std = np.std(errors)

        metrics = {
            'mae': float(mae),
            'rmse': float(rmse),
            'r2': float(r2),
            'mape': float(mape),
            'median_error': float(median_error),
            'error_std': float(error_std),
            'mean_actual': float(y.mean()),
            'mean_predicted': float(y_pred.mean())
        }

        logger.info(f"\n{dataset_name.upper()} METRICS:")
        logger.info(f"  MAE: ${metrics['mae']:.2f}")
        logger.info(f"  RMSE: ${metrics['rmse']:.2f}")
        logger.info(f"  R²: {metrics['r2']:.4f}")
        logger.info(f"  MAPE: {metrics['mape']:.1f}%")
        logger.info(f"  Mean Actual: ${metrics['mean_actual']:.2f}")
        logger.info(f"  Mean Predicted: ${metrics['mean_predicted']:.2f}")

        return metrics


    def get_feature_importance(self) -> pd.DataFrame:
        """
        Get feature coefficients (importance) from trained model.

        For Gamma regression with log link:
        - Positive coefficient = feature increases LTV
        - Negative coefficient = feature decreases LTV
        - Magnitude = strength of effect

        Returns:
            DataFrame with features and coefficients
        """
        if self.model is None:
            raise ValueError("Model not trained")

        coefficients = self.model.coef_

        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'coefficient': coefficients,
            'abs_coefficient': np.abs(coefficients)
        }).sort_values('abs_coefficient', ascending=False)

        return importance_df


    def predict_customer(
        self,
        features: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Predict LTV for a single customer with detailed output.

        Args:
            features: Single-row DataFrame with customer features

        Returns:
            {
                'predicted_ltv': 450.75,
                'confidence_interval_low': 350.0,
                'confidence_interval_high': 550.0,
                'value_segment': 'medium',  # low, medium, high
                'key_drivers': [...]
            }
        """
        if len(features) != 1:
            raise ValueError("predict_customer expects single customer (1 row)")

        # Get prediction
        predicted_ltv = self.predict(features)[0]

        # Calculate confidence interval (rough approximation)
        # In production, use bootstrap or prediction intervals
        std_error = self.training_metadata.get('val_metrics', {}).get('error_std', 100)
        conf_low = max(0, predicted_ltv - 1.96 * std_error)
        conf_high = predicted_ltv + 1.96 * std_error

        # Determine value segment
        if predicted_ltv < 100:
            value_segment = 'low'
        elif predicted_ltv < 500:
            value_segment = 'medium'
        else:
            value_segment = 'high'

        # Get feature importance
        feature_importance = self.get_feature_importance()
        top_features = feature_importance.head(10)

        # Identify key drivers
        key_drivers = []
        for _, row in top_features.iterrows():
            feature_name = row['feature']
            if feature_name in features.columns:
                feature_value = features[feature_name].iloc[0]
                coefficient = row['coefficient']

                # Calculate contribution (simplified)
                contribution = feature_value * coefficient

                key_drivers.append({
                    'feature': feature_name,
                    'value': float(feature_value),
                    'coefficient': float(coefficient),
                    'effect': 'positive' if coefficient > 0 else 'negative'
                })

        return {
            'predicted_ltv': float(predicted_ltv),
            'confidence_interval': {
                'low': float(conf_low),
                'high': float(conf_high)
            },
            'value_segment': value_segment,
            'prediction_window_months': self.prediction_window,
            'key_drivers': key_drivers[:5]  # Top 5
        }


    def save(self, model_dir: str) -> None:
        """
        Save model and metadata to disk.

        Args:
            model_dir: Directory to save model files
        """
        if self.model is None:
            raise ValueError("No model to save")

        model_dir = Path(model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save scikit-learn model
        model_path = model_dir / "ltv_model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        logger.info(f"Model saved to {model_path}")

        # Save metadata
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(self.training_metadata, f, indent=2)
        logger.info(f"Metadata saved to {metadata_path}")

        # Save feature names
        config_path = model_dir / "config.json"
        with open(config_path, 'w') as f:
            json.dump({
                'feature_names': self.feature_names,
                'prediction_window_months': self.prediction_window,
                'alpha': self.alpha
            }, f, indent=2)
        logger.info(f"Config saved to {config_path}")


    def load(self, model_dir: str) -> None:
        """
        Load model and metadata from disk.

        Args:
            model_dir: Directory containing model files
        """
        model_dir = Path(model_dir)

        # Load scikit-learn model
        model_path = model_dir / "ltv_model.pkl"
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        logger.info(f"Model loaded from {model_path}")

        # Load config
        config_path = model_dir / "config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.feature_names = config['feature_names']
                self.prediction_window = config['prediction_window_months']
                self.alpha = config.get('alpha', 1.0)
            logger.info(f"Config loaded from {config_path}")

        # Load metadata
        metadata_path = model_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                self.training_metadata = json.load(f)
            logger.info(f"Metadata loaded from {metadata_path}")
