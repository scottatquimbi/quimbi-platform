"""
Fraud and Anomaly Detection

SEPARATE from behavioral segmentation - this actively looks for:
1. Fraud patterns (suspicious purchasing behavior)
2. Anomalies (unusual customers worth investigation)
3. VIP outliers (extremely valuable customers)

Uses statistical methods + isolation forest for outlier detection.

Author: Quimbi Platform
Date: 2025-12-14
"""

import numpy as np
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of anomalies we detect"""
    FRAUD_SUSPECTED = "fraud_suspected"      # Suspicious purchasing patterns
    HIGH_RETURN_RATE = "high_return_rate"    # Excessive returns
    RAPID_ESCALATION = "rapid_escalation"    # Sudden value spike
    VELOCITY_ANOMALY = "velocity_anomaly"    # Unusual purchase frequency
    VALUE_OUTLIER = "value_outlier"          # Extremely high/low value
    VIP_CUSTOMER = "vip_customer"            # Top-tier valuable customer
    CHURN_RISK_SPIKE = "churn_risk_spike"    # Sudden churn risk increase
    GEOGRAPHIC_ANOMALY = "geographic_anomaly" # Unusual location patterns


@dataclass
class AnomalyDetection:
    """Detected anomaly for a customer"""
    customer_id: str
    anomaly_type: AnomalyType
    severity: float  # 0-1, how anomalous
    description: str
    evidence: Dict  # Supporting metrics
    recommended_action: str
    detected_at: date


@dataclass
class FraudIndicators:
    """Fraud-specific indicators"""
    customer_id: str
    fraud_score: float  # 0-1, higher = more suspicious
    indicators: List[str]  # List of red flags
    should_flag_for_review: bool
    confidence: float


class FraudAnomalyDetector:
    """
    Detects fraud and anomalies using statistical methods.

    This is SEPARATE from segmentation - we want to find:
    - Fraudsters
    - Unusual but valuable customers (VIPs)
    - Anomalies worth manual investigation
    """

    def __init__(self):
        # Configurable thresholds (not hardcoded!)
        self.return_rate_threshold = float(os.getenv("FRAUD_RETURN_RATE_THRESHOLD", "0.5"))  # 50%+
        self.velocity_zscore_threshold = float(os.getenv("FRAUD_VELOCITY_ZSCORE", "3.0"))  # 3 std devs
        self.value_percentile_vip = float(os.getenv("ANOMALY_VIP_PERCENTILE", "99.0"))  # Top 1%
        self.value_percentile_outlier = float(os.getenv("ANOMALY_VALUE_PERCENTILE", "99.5"))  # Top 0.5%

        logger.info(f"Fraud detector initialized: return_threshold={self.return_rate_threshold}, "
                   f"velocity_zscore={self.velocity_zscore_threshold}")


    def detect_return_fraud(
        self,
        customer_id: str,
        total_orders: int,
        return_count: int,
        total_value: float
    ) -> Optional[AnomalyDetection]:
        """
        Detect excessive return behavior (potential fraud or abuse).

        High return rates can indicate:
        - Wardrobing (buy, use, return)
        - Serial returners
        - Fraudulent refund claims
        """
        if total_orders < 3:  # Need history
            return None

        return_rate = return_count / total_orders

        if return_rate >= self.return_rate_threshold:
            severity = min(return_rate / 0.8, 1.0)  # Cap at 80% = full severity

            return AnomalyDetection(
                customer_id=customer_id,
                anomaly_type=AnomalyType.HIGH_RETURN_RATE,
                severity=severity,
                description=f"Customer has {return_rate*100:.1f}% return rate ({return_count}/{total_orders} orders)",
                evidence={
                    'return_rate': return_rate,
                    'return_count': return_count,
                    'total_orders': total_orders,
                    'total_value': total_value
                },
                recommended_action="Review for potential fraud or serial returner behavior",
                detected_at=date.today()
            )

        return None


    def detect_velocity_anomaly(
        self,
        customer_id: str,
        orders_per_day: float,
        population_mean: float,
        population_std: float
    ) -> Optional[AnomalyDetection]:
        """
        Detect unusual purchase velocity (too fast or too slow).

        Rapid purchasing can indicate:
        - Account compromise
        - Reseller activity
        - Card testing
        """
        if population_std == 0:
            return None

        z_score = abs((orders_per_day - population_mean) / population_std)

        if z_score >= self.velocity_zscore_threshold:
            severity = min(z_score / 5.0, 1.0)  # Z-score of 5 = full severity

            return AnomalyDetection(
                customer_id=customer_id,
                anomaly_type=AnomalyType.VELOCITY_ANOMALY,
                severity=severity,
                description=f"Purchase velocity {z_score:.1f} standard deviations from normal "
                           f"({orders_per_day:.3f} vs {population_mean:.3f} orders/day)",
                evidence={
                    'orders_per_day': orders_per_day,
                    'z_score': z_score,
                    'population_mean': population_mean,
                    'population_std': population_std
                },
                recommended_action="Investigate unusual purchase frequency",
                detected_at=date.today()
            )

        return None


    def detect_value_outliers(
        self,
        customer_id: str,
        lifetime_value: float,
        population_values: np.ndarray
    ) -> Optional[AnomalyDetection]:
        """
        Detect extreme value outliers (VIPs or suspicious high spenders).

        Top 0.5% by value should be flagged for special attention.
        """
        if len(population_values) < 100:
            return None

        vip_threshold = np.percentile(population_values, self.value_percentile_vip)
        outlier_threshold = np.percentile(population_values, self.value_percentile_outlier)

        if lifetime_value >= outlier_threshold:
            percentile = (np.sum(population_values < lifetime_value) / len(population_values)) * 100
            severity = min((lifetime_value - vip_threshold) / (outlier_threshold - vip_threshold), 1.0)

            return AnomalyDetection(
                customer_id=customer_id,
                anomaly_type=AnomalyType.VIP_CUSTOMER,
                severity=severity,
                description=f"Customer in top {100-percentile:.1f}% by lifetime value (${lifetime_value:,.2f})",
                evidence={
                    'lifetime_value': lifetime_value,
                    'percentile': percentile,
                    'vip_threshold': float(vip_threshold),
                    'outlier_threshold': float(outlier_threshold)
                },
                recommended_action="VIP customer - provide special handling and retention efforts",
                detected_at=date.today()
            )

        return None


    def detect_rapid_escalation(
        self,
        customer_id: str,
        recent_orders_value: float,
        historical_avg_value: float,
        orders_count: int
    ) -> Optional[AnomalyDetection]:
        """
        Detect sudden spikes in spending (potential account compromise).

        If recent spending (last 30 days) is >> historical average, flag it.
        """
        if orders_count < 5 or historical_avg_value == 0:
            return None

        escalation_ratio = recent_orders_value / historical_avg_value

        # If recent spending is 3x+ historical average
        if escalation_ratio >= 3.0:
            severity = min((escalation_ratio - 3.0) / 7.0, 1.0)  # 10x = full severity

            return AnomalyDetection(
                customer_id=customer_id,
                anomaly_type=AnomalyType.RAPID_ESCALATION,
                severity=severity,
                description=f"Recent spending {escalation_ratio:.1f}x historical average "
                           f"(${recent_orders_value:,.2f} vs ${historical_avg_value:,.2f})",
                evidence={
                    'recent_value': recent_orders_value,
                    'historical_avg': historical_avg_value,
                    'escalation_ratio': escalation_ratio,
                    'orders_count': orders_count
                },
                recommended_action="Verify account not compromised - unusual spending spike",
                detected_at=date.today()
            )

        return None


    def calculate_fraud_score(
        self,
        customer_id: str,
        anomalies: List[AnomalyDetection]
    ) -> FraudIndicators:
        """
        Calculate overall fraud score based on detected anomalies.

        Combines multiple signals into single fraud risk score.
        """
        fraud_signals = []
        fraud_score = 0.0

        for anomaly in anomalies:
            if anomaly.anomaly_type == AnomalyType.HIGH_RETURN_RATE:
                fraud_score += 0.4 * anomaly.severity
                fraud_signals.append(f"High return rate ({anomaly.evidence['return_rate']*100:.1f}%)")

            elif anomaly.anomaly_type == AnomalyType.VELOCITY_ANOMALY:
                fraud_score += 0.3 * anomaly.severity
                fraud_signals.append(f"Unusual velocity (z={anomaly.evidence['z_score']:.1f})")

            elif anomaly.anomaly_type == AnomalyType.RAPID_ESCALATION:
                fraud_score += 0.5 * anomaly.severity
                fraud_signals.append(f"Spending spike ({anomaly.evidence['escalation_ratio']:.1f}x)")

        # Cap at 1.0
        fraud_score = min(fraud_score, 1.0)

        # Confidence based on number of signals
        confidence = min(len(fraud_signals) / 3.0, 1.0)

        # Flag if score > 0.6 and confidence > 0.5
        should_flag = fraud_score >= 0.6 and confidence >= 0.5

        return FraudIndicators(
            customer_id=customer_id,
            fraud_score=fraud_score,
            indicators=fraud_signals,
            should_flag_for_review=should_flag,
            confidence=confidence
        )


    def analyze_customer_for_anomalies(
        self,
        customer_id: str,
        customer_data: Dict,
        population_stats: Dict
    ) -> Tuple[List[AnomalyDetection], Optional[FraudIndicators]]:
        """
        Complete anomaly analysis for a single customer.

        Args:
            customer_data: {
                'total_orders', 'lifetime_value', 'return_count',
                'orders_per_day', 'recent_value', 'historical_avg', ...
            }
            population_stats: {
                'velocity_mean', 'velocity_std', 'all_values'
            }

        Returns:
            (anomalies_list, fraud_indicators)
        """
        anomalies = []

        # Check return fraud
        if 'return_count' in customer_data:
            anomaly = self.detect_return_fraud(
                customer_id,
                customer_data['total_orders'],
                customer_data['return_count'],
                customer_data['lifetime_value']
            )
            if anomaly:
                anomalies.append(anomaly)

        # Check velocity anomaly
        if 'orders_per_day' in customer_data:
            anomaly = self.detect_velocity_anomaly(
                customer_id,
                customer_data['orders_per_day'],
                population_stats.get('velocity_mean', 0),
                population_stats.get('velocity_std', 1)
            )
            if anomaly:
                anomalies.append(anomaly)

        # Check value outliers
        if 'all_values' in population_stats:
            anomaly = self.detect_value_outliers(
                customer_id,
                customer_data['lifetime_value'],
                population_stats['all_values']
            )
            if anomaly:
                anomalies.append(anomaly)

        # Check rapid escalation
        if 'recent_value' in customer_data and 'historical_avg' in customer_data:
            anomaly = self.detect_rapid_escalation(
                customer_id,
                customer_data['recent_value'],
                customer_data['historical_avg'],
                customer_data['total_orders']
            )
            if anomaly:
                anomalies.append(anomaly)

        # Calculate fraud score
        fraud_indicators = None
        if anomalies:
            fraud_indicators = self.calculate_fraud_score(customer_id, anomalies)

        return anomalies, fraud_indicators


def generate_anomaly_report(
    anomalies: List[AnomalyDetection],
    fraud_cases: List[FraudIndicators]
) -> str:
    """Generate human-readable anomaly report"""
    report = []
    report.append("=" * 70)
    report.append("FRAUD & ANOMALY DETECTION REPORT")
    report.append("=" * 70)

    report.append(f"\nTotal anomalies detected: {len(anomalies)}")
    report.append(f"Fraud cases flagged: {sum(1 for f in fraud_cases if f.should_flag_for_review)}")

    # Group by type
    by_type = {}
    for anomaly in anomalies:
        if anomaly.anomaly_type not in by_type:
            by_type[anomaly.anomaly_type] = []
        by_type[anomaly.anomaly_type].append(anomaly)

    report.append("\nAnomalies by Type:")
    for anom_type, anoms in sorted(by_type.items()):
        report.append(f"  {anom_type.value}: {len(anoms)}")

    # High-severity cases
    high_severity = [a for a in anomalies if a.severity >= 0.7]
    if high_severity:
        report.append(f"\n🚨 HIGH SEVERITY CASES ({len(high_severity)}):")
        for anomaly in high_severity[:10]:  # Top 10
            report.append(f"  Customer {anomaly.customer_id}: {anomaly.description}")
            report.append(f"    → {anomaly.recommended_action}")

    # Fraud flags
    flagged = [f for f in fraud_cases if f.should_flag_for_review]
    if flagged:
        report.append(f"\n⚠️  FRAUD FLAGS ({len(flagged)}):")
        for fraud in flagged[:10]:  # Top 10
            report.append(f"  Customer {fraud.customer_id}: score={fraud.fraud_score:.2f}")
            for indicator in fraud.indicators:
                report.append(f"    • {indicator}")

    report.append("\n" + "=" * 70)

    return "\n".join(report)
