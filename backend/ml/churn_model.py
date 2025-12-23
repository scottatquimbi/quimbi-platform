"""
Churn Prediction Model

LightGBM-based binary classification model for predicting customer churn.

Model Architecture:
- Algorithm: LightGBM (Gradient Boosting Decision Trees)
- Objective: Binary classification
- Target metric: AUC-ROC (Area Under ROC Curve)
- Regularization: L1/L2, max_depth, min_child_samples

Why LightGBM?
1. Fast training on medium datasets (1K-100K customers)
2. Handles missing values natively
3. Built-in feature importance (gain-based)
4. Excellent AUC performance (typically 0.80-0.90)
5. Interpretable with SHAP values

Target Performance:
- AUC: 0.85+ (vs 0.60-0.65 for current rules)
- Precision @ 70% threshold: 80%+ (vs 50% for rules)
- Recall @ 70% threshold: 70%+ (vs 40% for rules)

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

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logging.warning("LightGBM not installed. Install with: pip install lightgbm")

from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    roc_auc_score,
    precision_recall_curve,
    classification_report,
    confusion_matrix
)

logger = logging.getLogger(__name__)


class ChurnModel:
    """
    LightGBM-based churn prediction model.

    Workflow:
    1. Train on historical data with time-series cross-validation
    2. Optimize threshold for business objectives
    3. Save model and metadata
    4. Deploy for inference
    5. Monitor performance and retrain as needed
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        threshold: float = 0.7
    ):
        """
        Args:
            model_path: Path to saved model (for loading existing model)
            threshold: Probability threshold for classification (0-1)
        """
        if not LIGHTGBM_AVAILABLE:
            raise ImportError(
                "LightGBM is required for ChurnModel. "
                "Install with: pip install lightgbm"
            )

        self.model = None
        self.threshold = threshold
        self.feature_names = None
        self.training_metadata = {}

        # LightGBM hyperparameters (production-ready defaults)
        # These were tuned on e-commerce datasets
        self.params = {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'num_leaves': 31,           # Tree complexity (31 = balanced)
            'learning_rate': 0.05,       # Slower = better generalization
            'feature_fraction': 0.8,     # Random feature selection (prevents overfitting)
            'bagging_fraction': 0.8,     # Random row selection (prevents overfitting)
            'bagging_freq': 5,           # Bagging every 5 iterations
            'max_depth': 6,              # Limit tree depth
            'min_child_samples': 50,     # Min samples per leaf (prevents overfitting)
            'lambda_l1': 0.1,            # L1 regularization
            'lambda_l2': 0.1,            # L2 regularization
            'verbose': -1,
            'random_state': 42,
            'n_jobs': -1                 # Use all CPU cores
        }

        # Load existing model if path provided
        if model_path:
            self.load(model_path)


    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        num_boost_round: int = 500,
        early_stopping_rounds: int = 50,
        verbose_eval: int = 50
    ) -> Dict[str, Any]:
        """
        Train LightGBM model.

        Args:
            X_train: Training features
            y_train: Training labels (0 = retained, 1 = churned)
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            num_boost_round: Max boosting iterations
            early_stopping_rounds: Stop if no improvement for N rounds
            verbose_eval: Print metrics every N rounds

        Returns:
            Training metrics and history
        """
        logger.info(f"Training churn model on {len(X_train)} samples...")
        logger.info(f"Churn rate: {y_train.mean():.1%}")

        # Store feature names
        self.feature_names = list(X_train.columns)

        # Create LightGBM datasets
        train_data = lgb.Dataset(
            X_train,
            label=y_train,
            feature_name=self.feature_names
        )

        valid_sets = [train_data]
        valid_names = ['train']

        if X_val is not None and y_val is not None:
            val_data = lgb.Dataset(
                X_val,
                label=y_val,
                feature_name=self.feature_names,
                reference=train_data  # Use same categorical encoding as train
            )
            valid_sets.append(val_data)
            valid_names.append('valid')
            logger.info(f"Validation set: {len(X_val)} samples, churn_rate={y_val.mean():.1%}")

        # Train model
        evals_result = {}
        self.model = lgb.train(
            params=self.params,
            train_set=train_data,
            num_boost_round=num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=[
                lgb.early_stopping(stopping_rounds=early_stopping_rounds),
                lgb.log_evaluation(period=verbose_eval),
                lgb.record_evaluation(evals_result)
            ]
        )

        # Evaluate on training and validation sets
        train_metrics = self.evaluate(X_train, y_train, dataset_name="train")

        val_metrics = {}
        if X_val is not None and y_val is not None:
            val_metrics = self.evaluate(X_val, y_val, dataset_name="validation")

        # Store training metadata
        self.training_metadata = {
            'trained_at': datetime.now().isoformat(),
            'n_train_samples': len(X_train),
            'n_val_samples': len(X_val) if X_val is not None else 0,
            'train_churn_rate': float(y_train.mean()),
            'val_churn_rate': float(y_val.mean()) if y_val is not None else None,
            'num_features': len(self.feature_names),
            'feature_names': self.feature_names,
            'num_boost_round': self.model.num_trees(),
            'params': self.params,
            'threshold': self.threshold,
            'train_metrics': train_metrics,
            'val_metrics': val_metrics,
            'training_history': evals_result
        }

        logger.info(f"✅ Model trained with {self.model.num_trees()} trees")
        logger.info(f"   Train AUC: {train_metrics['auc']:.4f}")
        if val_metrics:
            logger.info(f"   Val AUC: {val_metrics['auc']:.4f}")

        return self.training_metadata


    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict churn probabilities.

        Args:
            X: Feature matrix

        Returns:
            Array of churn probabilities (0-1)
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

        probas = self.model.predict(X)
        return probas


    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict churn labels (0 or 1) using threshold.

        Args:
            X: Feature matrix

        Returns:
            Array of predictions (0 = retained, 1 = churned)
        """
        probas = self.predict_proba(X)
        predictions = (probas >= self.threshold).astype(int)
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
            y: True labels
            dataset_name: Name for logging

        Returns:
            Dictionary of metrics
        """
        # Get predictions
        y_proba = self.predict_proba(X)
        y_pred = (y_proba >= self.threshold).astype(int)

        # Calculate metrics
        auc = roc_auc_score(y, y_proba)

        # Precision-recall at different thresholds
        precisions, recalls, thresholds = precision_recall_curve(y, y_proba)

        # Find precision/recall at our threshold
        threshold_idx = np.argmin(np.abs(thresholds - self.threshold))
        precision_at_threshold = precisions[threshold_idx]
        recall_at_threshold = recalls[threshold_idx]

        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()

        metrics = {
            'auc': float(auc),
            'precision': float(precision_at_threshold),
            'recall': float(recall_at_threshold),
            'f1': float(2 * precision_at_threshold * recall_at_threshold /
                       (precision_at_threshold + recall_at_threshold + 1e-10)),
            'true_positives': int(tp),
            'true_negatives': int(tn),
            'false_positives': int(fp),
            'false_negatives': int(fn),
            'accuracy': float((tp + tn) / (tp + tn + fp + fn)),
            'threshold': float(self.threshold)
        }

        logger.info(f"\n{dataset_name.upper()} METRICS:")
        logger.info(f"  AUC: {metrics['auc']:.4f}")
        logger.info(f"  Precision @ {self.threshold}: {metrics['precision']:.4f}")
        logger.info(f"  Recall @ {self.threshold}: {metrics['recall']:.4f}")
        logger.info(f"  F1 Score: {metrics['f1']:.4f}")
        logger.info(f"  TP={tp}, TN={tn}, FP={fp}, FN={fn}")

        return metrics


    def optimize_threshold(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        metric: str = 'f1',
        min_precision: float = 0.7
    ) -> float:
        """
        Find optimal probability threshold for classification.

        Args:
            X: Feature matrix
            y: True labels
            metric: Metric to optimize ('f1', 'precision', 'recall')
            min_precision: Minimum precision constraint (default 0.7)

        Returns:
            Optimal threshold
        """
        y_proba = self.predict_proba(X)
        precisions, recalls, thresholds = precision_recall_curve(y, y_proba)

        # Calculate F1 for each threshold
        f1_scores = 2 * precisions * recalls / (precisions + recalls + 1e-10)

        if metric == 'f1':
            # Find threshold with highest F1 above min_precision
            valid_idx = precisions >= min_precision
            if not valid_idx.any():
                logger.warning(
                    f"No threshold achieves min_precision={min_precision}. "
                    f"Using best F1 threshold."
                )
                valid_idx = np.ones_like(f1_scores, dtype=bool)

            best_idx = np.argmax(f1_scores[valid_idx])
            optimal_threshold = thresholds[valid_idx][best_idx]

        elif metric == 'precision':
            # Find threshold with highest precision
            best_idx = np.argmax(precisions)
            optimal_threshold = thresholds[best_idx]

        elif metric == 'recall':
            # Find threshold with highest recall above min_precision
            valid_idx = precisions >= min_precision
            if not valid_idx.any():
                logger.warning(
                    f"No threshold achieves min_precision={min_precision}"
                )
                optimal_threshold = 0.5
            else:
                best_idx = np.argmax(recalls[valid_idx])
                optimal_threshold = thresholds[valid_idx][best_idx]

        else:
            raise ValueError(f"Unknown metric: {metric}")

        logger.info(
            f"Optimal threshold: {optimal_threshold:.3f} "
            f"(precision={precisions[best_idx]:.3f}, "
            f"recall={recalls[best_idx]:.3f}, "
            f"f1={f1_scores[best_idx]:.3f})"
        )

        self.threshold = optimal_threshold
        return optimal_threshold


    def get_feature_importance(self, importance_type: str = 'gain') -> pd.DataFrame:
        """
        Get feature importance from trained model.

        Args:
            importance_type: Type of importance ('gain', 'split', 'weight')

        Returns:
            DataFrame with features and importance scores
        """
        if self.model is None:
            raise ValueError("Model not trained")

        importance = self.model.feature_importance(importance_type=importance_type)

        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False)

        return importance_df


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

        # Save LightGBM model
        model_path = model_dir / "churn_model.txt"
        self.model.save_model(str(model_path))
        logger.info(f"Model saved to {model_path}")

        # Save metadata
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(self.training_metadata, f, indent=2)
        logger.info(f"Metadata saved to {metadata_path}")

        # Save threshold
        config_path = model_dir / "config.json"
        with open(config_path, 'w') as f:
            json.dump({
                'threshold': self.threshold,
                'feature_names': self.feature_names
            }, f, indent=2)
        logger.info(f"Config saved to {config_path}")


    def load(self, model_dir: str) -> None:
        """
        Load model and metadata from disk.

        Args:
            model_dir: Directory containing model files
        """
        model_dir = Path(model_dir)

        # Load LightGBM model
        model_path = model_dir / "churn_model.txt"
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.model = lgb.Booster(model_file=str(model_path))
        logger.info(f"Model loaded from {model_path}")

        # Load config
        config_path = model_dir / "config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.threshold = config['threshold']
                self.feature_names = config['feature_names']
            logger.info(f"Config loaded from {config_path}")

        # Load metadata
        metadata_path = model_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                self.training_metadata = json.load(f)
            logger.info(f"Metadata loaded from {metadata_path}")


    def predict_customer(
        self,
        features: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Predict churn for a single customer with detailed output.

        Args:
            features: Single-row DataFrame with customer features

        Returns:
            {
                'churn_probability': 0.85,
                'is_at_risk': True,
                'confidence': 'high',  # high, medium, low
                'risk_factors': [...],
                'protective_factors': [...]
            }
        """
        if len(features) != 1:
            raise ValueError("predict_customer expects single customer (1 row)")

        # Get prediction
        proba = self.predict_proba(features)[0]
        is_churned = proba >= self.threshold

        # Confidence level
        if proba < 0.3 or proba > 0.8:
            confidence = 'high'
        elif proba < 0.4 or proba > 0.7:
            confidence = 'medium'
        else:
            confidence = 'low'

        # Get feature importance
        feature_importance = self.get_feature_importance()
        top_features = feature_importance.head(10)

        # Identify risk and protective factors
        risk_factors = []
        protective_factors = []

        for _, row in top_features.iterrows():
            feature_name = row['feature']
            if feature_name in features.columns:
                feature_value = features[feature_name].iloc[0]

                # Simple heuristic: high values of important features = risk
                # (This is oversimplified - use SHAP for accurate explanations)
                if feature_value > 0:
                    risk_factors.append({
                        'feature': feature_name,
                        'value': float(feature_value),
                        'importance': float(row['importance'])
                    })
                else:
                    protective_factors.append({
                        'feature': feature_name,
                        'value': float(feature_value),
                        'importance': float(row['importance'])
                    })

        return {
            'churn_probability': float(proba),
            'is_at_risk': bool(is_churned),
            'confidence': confidence,
            'threshold': float(self.threshold),
            'risk_factors': risk_factors[:5],  # Top 5
            'protective_factors': protective_factors[:5]
        }
