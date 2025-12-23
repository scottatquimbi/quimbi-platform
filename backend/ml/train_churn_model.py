"""
Training Script for Churn Prediction Model

Orchestrates the complete training pipeline:
1. Load historical data
2. Create point-in-time correct training set
3. Train LightGBM model with time-series cross-validation
4. Evaluate performance
5. Optimize threshold
6. Save model artifacts

Usage:
    python -m backend.ml.train_churn_model \\
        --start-date 2024-01-01 \\
        --end-date 2025-01-01 \\
        --model-dir models/churn/v1

Author: Quimbi ML Team
Version: 1.0.0
Date: November 12, 2025
"""

import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
import pickle

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.ml.churn_data_pipeline import ChurnDataPipeline
from backend.ml.churn_model import ChurnModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChurnModelTrainer:
    """
    Orchestrates churn model training with time-series cross-validation.
    """

    def __init__(
        self,
        start_date: datetime,
        end_date: datetime,
        model_dir: str,
        observation_window_days: int = 180,
        prediction_window_days: int = 90,
        churn_definition_days: int = 90
    ):
        """
        Args:
            start_date: Start of training data period
            end_date: End of training data period
            model_dir: Directory to save trained model
            observation_window_days: Days of history for features
            prediction_window_days: Days into future to predict
            churn_definition_days: Days without purchase = churned
        """
        self.start_date = start_date
        self.end_date = end_date
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Initialize pipeline
        self.pipeline = ChurnDataPipeline(
            observation_window_days=observation_window_days,
            prediction_window_days=prediction_window_days,
            churn_definition_days=churn_definition_days
        )

        # Will be populated during training
        self.scaler = None
        self.model = None
        self.feature_names = None


    async def run(self) -> None:
        """
        Execute complete training pipeline.
        """
        logger.info("=" * 80)
        logger.info("CHURN MODEL TRAINING PIPELINE")
        logger.info("=" * 80)
        logger.info(f"Training period: {self.start_date.date()} to {self.end_date.date()}")
        logger.info(f"Model directory: {self.model_dir}")
        logger.info("")

        # Step 1: Create training dataset
        logger.info("STEP 1: Creating training dataset...")
        X, y = await self.pipeline.create_training_dataset(
            start_date=self.start_date,
            end_date=self.end_date,
            sampling_interval_days=30,  # Monthly snapshots
            min_orders_required=2,
            max_customers_per_snapshot=None  # Use all customers
        )

        logger.info(f"✅ Dataset created: {len(X)} samples, {len(X.columns)} features")
        logger.info(f"   Churn rate: {y.mean():.1%}")
        logger.info(f"   Features: {list(X.columns[:5])}... (showing first 5)")
        logger.info("")

        # Step 2: Feature preprocessing
        logger.info("STEP 2: Preprocessing features...")
        X_scaled, self.scaler = self._preprocess_features(X)
        logger.info(f"✅ Features scaled with StandardScaler")
        logger.info("")

        # Step 3: Time-series cross-validation
        logger.info("STEP 3: Time-series cross-validation...")
        cv_results = self._time_series_cross_validate(X_scaled, y, n_splits=5)
        logger.info(f"✅ Cross-validation complete:")
        logger.info(f"   Mean AUC: {cv_results['mean_auc']:.4f} ± {cv_results['std_auc']:.4f}")
        logger.info(f"   Mean Precision: {cv_results['mean_precision']:.4f}")
        logger.info(f"   Mean Recall: {cv_results['mean_recall']:.4f}")
        logger.info("")

        # Step 4: Train final model on all data
        logger.info("STEP 4: Training final model on full dataset...")
        self.model = self._train_final_model(X_scaled, y)
        logger.info(f"✅ Final model trained")
        logger.info("")

        # Step 5: Optimize threshold
        logger.info("STEP 5: Optimizing classification threshold...")
        optimal_threshold = self.model.optimize_threshold(
            X_scaled,
            y,
            metric='f1',
            min_precision=0.7  # Business requirement: 70%+ precision
        )
        logger.info(f"✅ Optimal threshold: {optimal_threshold:.3f}")
        logger.info("")

        # Step 6: Feature importance
        logger.info("STEP 6: Analyzing feature importance...")
        importance_df = self.model.get_feature_importance()
        logger.info(f"✅ Top 10 features:")
        for idx, row in importance_df.head(10).iterrows():
            logger.info(f"   {row['feature']:40s} {row['importance']:>10.0f}")
        logger.info("")

        # Step 7: Save artifacts
        logger.info("STEP 7: Saving model artifacts...")
        self._save_artifacts()
        logger.info(f"✅ Model saved to {self.model_dir}")
        logger.info("")

        logger.info("=" * 80)
        logger.info("TRAINING COMPLETE!")
        logger.info("=" * 80)


    def _preprocess_features(
        self,
        X: pd.DataFrame
    ) -> tuple[pd.DataFrame, StandardScaler]:
        """
        Preprocess features for training.

        Steps:
        1. Handle missing values (fill with 0 or median)
        2. Scale features with StandardScaler
        3. Remove features with zero variance

        Args:
            X: Raw feature matrix

        Returns:
            X_scaled: Preprocessed features
            scaler: Fitted StandardScaler
        """
        # Handle missing values
        X_clean = X.fillna(0)  # LightGBM handles NaN, but explicit is better

        # Remove zero-variance features
        variance = X_clean.var()
        zero_var_cols = variance[variance == 0].index
        if len(zero_var_cols) > 0:
            logger.warning(f"Removing {len(zero_var_cols)} zero-variance features")
            X_clean = X_clean.drop(columns=zero_var_cols)

        # Scale features (important for distance-based interpretability)
        scaler = StandardScaler()
        X_scaled = pd.DataFrame(
            scaler.fit_transform(X_clean),
            columns=X_clean.columns,
            index=X_clean.index
        )

        self.feature_names = list(X_scaled.columns)

        return X_scaled, scaler


    def _time_series_cross_validate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_splits: int = 5
    ) -> dict:
        """
        Perform time-series cross-validation.

        Uses TimeSeriesSplit to ensure:
        - Train on past data, validate on future data
        - No data leakage from future to past
        - Realistic evaluation of model performance

        Args:
            X: Feature matrix
            y: Target labels
            n_splits: Number of CV folds

        Returns:
            Dictionary of cross-validation metrics
        """
        tscv = TimeSeriesSplit(n_splits=n_splits)

        cv_aucs = []
        cv_precisions = []
        cv_recalls = []
        cv_f1s = []

        logger.info(f"Running {n_splits}-fold time-series cross-validation...")

        for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(X)):
            logger.info(f"\n  Fold {fold_idx + 1}/{n_splits}")
            logger.info(f"    Train: {len(train_idx)} samples")
            logger.info(f"    Val:   {len(val_idx)} samples")

            # Split data
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            # Train model
            model = ChurnModel()
            model.train(
                X_train, y_train,
                X_val, y_val,
                num_boost_round=500,
                early_stopping_rounds=50,
                verbose_eval=100
            )

            # Evaluate
            val_metrics = model.evaluate(X_val, y_val, dataset_name=f"fold_{fold_idx+1}")

            cv_aucs.append(val_metrics['auc'])
            cv_precisions.append(val_metrics['precision'])
            cv_recalls.append(val_metrics['recall'])
            cv_f1s.append(val_metrics['f1'])

        # Aggregate results
        results = {
            'mean_auc': np.mean(cv_aucs),
            'std_auc': np.std(cv_aucs),
            'mean_precision': np.mean(cv_precisions),
            'std_precision': np.std(cv_precisions),
            'mean_recall': np.mean(cv_recalls),
            'std_recall': np.std(cv_recalls),
            'mean_f1': np.mean(cv_f1s),
            'std_f1': np.std(cv_f1s),
            'fold_aucs': cv_aucs,
            'fold_precisions': cv_precisions,
            'fold_recalls': cv_recalls,
            'fold_f1s': cv_f1s
        }

        return results


    def _train_final_model(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> ChurnModel:
        """
        Train final model on full dataset.

        Args:
            X: Feature matrix
            y: Target labels

        Returns:
            Trained ChurnModel
        """
        # Use 80/20 train/val split for final model
        split_idx = int(len(X) * 0.8)

        X_train = X.iloc[:split_idx]
        y_train = y.iloc[:split_idx]
        X_val = X.iloc[split_idx:]
        y_val = y.iloc[split_idx:]

        logger.info(f"Training final model:")
        logger.info(f"  Train: {len(X_train)} samples")
        logger.info(f"  Val:   {len(X_val)} samples")

        model = ChurnModel()
        model.train(
            X_train, y_train,
            X_val, y_val,
            num_boost_round=1000,
            early_stopping_rounds=100,
            verbose_eval=100
        )

        return model


    def _save_artifacts(self) -> None:
        """
        Save all model artifacts to disk.

        Saves:
        - Trained model (LightGBM Booster)
        - Feature scaler (StandardScaler)
        - Feature names
        - Training metadata
        """
        # Save model
        self.model.save(str(self.model_dir))

        # Save scaler
        scaler_path = self.model_dir / "scaler.pkl"
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)
        logger.info(f"Scaler saved to {scaler_path}")

        # Save feature names
        features_path = self.model_dir / "feature_names.txt"
        with open(features_path, 'w') as f:
            for feature in self.feature_names:
                f.write(f"{feature}\n")
        logger.info(f"Feature names saved to {features_path}")


async def main():
    """Main entry point for training script."""
    parser = argparse.ArgumentParser(description="Train churn prediction model")

    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Start date for training data (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="End date for training data (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="models/churn/v1",
        help="Directory to save trained model"
    )
    parser.add_argument(
        "--observation-window",
        type=int,
        default=180,
        help="Observation window in days (default 180)"
    )
    parser.add_argument(
        "--prediction-window",
        type=int,
        default=90,
        help="Prediction window in days (default 90)"
    )
    parser.add_argument(
        "--churn-definition",
        type=int,
        default=90,
        help="Churn definition in days (default 90)"
    )

    args = parser.parse_args()

    # Parse dates
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d")

    # Create trainer
    trainer = ChurnModelTrainer(
        start_date=start_date,
        end_date=end_date,
        model_dir=args.model_dir,
        observation_window_days=args.observation_window,
        prediction_window_days=args.prediction_window,
        churn_definition_days=args.churn_definition
    )

    # Run training
    await trainer.run()


if __name__ == "__main__":
    asyncio.run(main())
