#!/usr/bin/env python3
"""
Validate and visualize segment quality.

This script:
1. Analyzes segment distributions across all axes
2. Calculates quality metrics (silhouette scores, balance, etc.)
3. Generates visualization reports
4. Identifies anomalies or quality issues

Usage:
    python3 scripts/validate_segments.py --database-url postgresql://...
"""

import asyncio
import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Any
from collections import Counter

import asyncpg
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SegmentValidator:
    """Validates segment quality and generates reports."""

    def __init__(self, database_url: str, store_id: str = "linda_quilting"):
        self.database_url = database_url
        self.store_id = store_id
        self.conn = None

    async def connect(self):
        """Connect to database."""
        self.conn = await asyncpg.connect(self.database_url)

    async def close(self):
        """Close database connection."""
        if self.conn:
            await self.conn.close()

    async def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall segmentation statistics."""
        query = """
            SELECT
                COUNT(*) as total_customers,
                COUNT(CASE WHEN segment_memberships <> '{}' THEN 1 END) as segmented_customers,
                COUNT(CASE WHEN segment_memberships = '{}' THEN 1 END) as unsegmented_customers
            FROM customer_profiles
        """

        result = await self.conn.fetchrow(query)

        return {
            'total_customers': result['total_customers'],
            'segmented_customers': result['segmented_customers'],
            'unsegmented_customers': result['unsegmented_customers'],
            'segmentation_rate': result['segmented_customers'] / result['total_customers'] if result['total_customers'] > 0 else 0
        }

    async def get_axis_distributions(self) -> Dict[str, Dict[str, int]]:
        """Get segment distributions for each axis."""
        query = """
            SELECT
                jsonb_object_keys(segment_memberships) as axis,
                segment_memberships->>jsonb_object_keys(segment_memberships) as segment,
                COUNT(*) as customer_count
            FROM customer_profiles
            WHERE segment_memberships <> '{}'
            GROUP BY axis, segment
            ORDER BY axis, customer_count DESC
        """

        result = await self.conn.fetch(query)

        distributions = {}
        for row in result:
            axis = row['axis']
            if axis not in distributions:
                distributions[axis] = {}
            distributions[axis][row['segment']] = row['customer_count']

        return distributions

    def calculate_balance_metrics(self, distributions: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
        """Calculate balance metrics for each axis."""
        metrics = {}

        for axis, segments in distributions.items():
            total_customers = sum(segments.values())
            num_segments = len(segments)

            # Calculate expected even distribution
            expected_per_segment = total_customers / num_segments if num_segments > 0 else 0

            # Calculate imbalance (coefficient of variation)
            counts = list(segments.values())
            mean_count = sum(counts) / len(counts) if counts else 0
            variance = sum((c - mean_count) ** 2 for c in counts) / len(counts) if counts else 0
            std_dev = variance ** 0.5

            cv = std_dev / mean_count if mean_count > 0 else 0

            # Calculate Gini coefficient (measure of inequality)
            sorted_counts = sorted(counts)
            n = len(sorted_counts)
            gini = 0
            for i, count in enumerate(sorted_counts):
                gini += (2 * (i + 1) - n - 1) * count
            gini = gini / (n * sum(sorted_counts)) if sum(sorted_counts) > 0 else 0

            # Determine balance quality
            if cv < 0.3:
                balance_quality = "Excellent"
            elif cv < 0.5:
                balance_quality = "Good"
            elif cv < 0.7:
                balance_quality = "Fair"
            else:
                balance_quality = "Poor"

            metrics[axis] = {
                'num_segments': num_segments,
                'total_customers': total_customers,
                'expected_per_segment': expected_per_segment,
                'coefficient_of_variation': cv,
                'gini_coefficient': gini,
                'balance_quality': balance_quality,
                'largest_segment': max(counts) if counts else 0,
                'smallest_segment': min(counts) if counts else 0,
                'size_ratio': max(counts) / min(counts) if counts and min(counts) > 0 else 0
            }

        return metrics

    async def identify_anomalies(self, distributions: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
        """Identify potential anomalies in segmentation."""
        anomalies = []

        for axis, segments in distributions.items():
            total_customers = sum(segments.values())

            for segment_name, count in segments.items():
                percentage = (count / total_customers * 100) if total_customers > 0 else 0

                # Flag very small segments (< 1%)
                if percentage < 1.0:
                    anomalies.append({
                        'axis': axis,
                        'segment': segment_name,
                        'issue': 'Very small segment',
                        'severity': 'warning',
                        'customer_count': count,
                        'percentage': percentage,
                        'recommendation': 'Consider merging with similar segments'
                    })

                # Flag dominant segments (> 80%)
                if percentage > 80.0:
                    anomalies.append({
                        'axis': axis,
                        'segment': segment_name,
                        'issue': 'Dominant segment',
                        'severity': 'warning',
                        'customer_count': count,
                        'percentage': percentage,
                        'recommendation': 'Consider re-clustering with different K'
                    })

        return anomalies

    def generate_report(
        self,
        overall_stats: Dict[str, Any],
        distributions: Dict[str, Dict[str, int]],
        balance_metrics: Dict[str, Any],
        anomalies: List[Dict[str, Any]]
    ) -> str:
        """Generate a text report of validation results."""
        report = []
        report.append("=" * 80)
        report.append("SEGMENTATION VALIDATION REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        report.append("")

        # Overall Statistics
        report.append("OVERALL STATISTICS")
        report.append("-" * 80)
        report.append(f"Total Customers:      {overall_stats['total_customers']:,}")
        report.append(f"Segmented Customers:  {overall_stats['segmented_customers']:,}")
        report.append(f"Unsegmented:          {overall_stats['unsegmented_customers']:,}")
        report.append(f"Segmentation Rate:    {overall_stats['segmentation_rate']:.1%}")
        report.append("")

        # Axis Summary
        report.append("AXIS SUMMARY")
        report.append("-" * 80)
        report.append(f"{'Axis':<35} {'Segments':<10} {'Balance':<15} {'CV':<10}")
        report.append("-" * 80)

        for axis in sorted(distributions.keys()):
            metrics = balance_metrics[axis]
            report.append(
                f"{axis:<35} {metrics['num_segments']:<10} "
                f"{metrics['balance_quality']:<15} {metrics['coefficient_of_variation']:<10.3f}"
            )

        report.append("")

        # Detailed Distributions
        report.append("SEGMENT DISTRIBUTIONS")
        report.append("-" * 80)

        for axis in sorted(distributions.keys()):
            segments = distributions[axis]
            total = sum(segments.values())
            report.append(f"\n{axis.upper()} ({len(segments)} segments, {total:,} customers)")
            report.append("-" * 40)

            for segment_name, count in sorted(segments.items(), key=lambda x: x[1], reverse=True):
                pct = (count / total * 100) if total > 0 else 0
                bar_length = int(pct / 2)  # Scale to 50 chars max
                bar = "█" * bar_length
                report.append(f"  {segment_name:<30} {count:>8,} ({pct:>5.1f}%) {bar}")

        # Balance Metrics
        report.append("\n")
        report.append("BALANCE METRICS")
        report.append("-" * 80)

        for axis in sorted(distributions.keys()):
            metrics = balance_metrics[axis]
            report.append(f"\n{axis}")
            report.append(f"  Quality:        {metrics['balance_quality']}")
            report.append(f"  CV:             {metrics['coefficient_of_variation']:.3f}")
            report.append(f"  Gini:           {metrics['gini_coefficient']:.3f}")
            report.append(f"  Size Ratio:     {metrics['size_ratio']:.1f}x")
            report.append(f"  Largest:        {metrics['largest_segment']:,} customers")
            report.append(f"  Smallest:       {metrics['smallest_segment']:,} customers")

        # Anomalies
        if anomalies:
            report.append("\n")
            report.append("ANOMALIES & WARNINGS")
            report.append("-" * 80)

            for anomaly in anomalies:
                report.append(f"\n⚠️  {anomaly['axis']} / {anomaly['segment']}")
                report.append(f"    Issue:          {anomaly['issue']}")
                report.append(f"    Customer Count: {anomaly['customer_count']:,} ({anomaly['percentage']:.1f}%)")
                report.append(f"    Recommendation: {anomaly['recommendation']}")
        else:
            report.append("\n")
            report.append("✅ No anomalies detected - all segments within normal ranges")

        # Summary
        report.append("\n")
        report.append("=" * 80)
        report.append("SUMMARY")
        report.append("=" * 80)

        excellent_count = sum(1 for m in balance_metrics.values() if m['balance_quality'] == 'Excellent')
        good_count = sum(1 for m in balance_metrics.values() if m['balance_quality'] == 'Good')
        fair_count = sum(1 for m in balance_metrics.values() if m['balance_quality'] == 'Fair')
        poor_count = sum(1 for m in balance_metrics.values() if m['balance_quality'] == 'Poor')

        report.append(f"Axes: {len(distributions)}")
        report.append(f"  Excellent Balance: {excellent_count}")
        report.append(f"  Good Balance:      {good_count}")
        report.append(f"  Fair Balance:      {fair_count}")
        report.append(f"  Poor Balance:      {poor_count}")
        report.append(f"Anomalies:           {len(anomalies)}")
        report.append("")

        overall_quality = "EXCELLENT" if excellent_count >= len(distributions) * 0.7 else \
                         "GOOD" if (excellent_count + good_count) >= len(distributions) * 0.7 else \
                         "FAIR" if fair_count + poor_count < len(distributions) * 0.5 else "NEEDS IMPROVEMENT"

        report.append(f"Overall Quality: {overall_quality}")
        report.append("=" * 80)

        return "\n".join(report)

    async def run_validation(self) -> Dict[str, Any]:
        """Run complete validation suite."""
        logger.info("=" * 80)
        logger.info("SEGMENT VALIDATION")
        logger.info("=" * 80)

        # Gather data
        logger.info("Gathering segmentation data...")
        overall_stats = await self.get_overall_stats()
        distributions = await self.get_axis_distributions()

        logger.info(f"Found {len(distributions)} axes")

        # Calculate metrics
        logger.info("Calculating balance metrics...")
        balance_metrics = self.calculate_balance_metrics(distributions)

        # Identify anomalies
        logger.info("Identifying anomalies...")
        anomalies = await self.identify_anomalies(distributions)

        # Generate report
        report_text = self.generate_report(
            overall_stats,
            distributions,
            balance_metrics,
            anomalies
        )

        # Save report
        output_file = f"segment_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(output_file, 'w') as f:
            f.write(report_text)

        logger.info(f"✅ Validation complete - report saved to {output_file}")

        # Print report
        print("\n" + report_text)

        return {
            'overall_stats': overall_stats,
            'distributions': distributions,
            'balance_metrics': balance_metrics,
            'anomalies': anomalies,
            'report_file': output_file
        }


async def main():
    parser = argparse.ArgumentParser(
        description="Validate segment quality and generate reports"
    )
    parser.add_argument(
        '--database-url',
        default=None,
        help='PostgreSQL connection URL (defaults to DATABASE_URL env var)'
    )
    parser.add_argument(
        '--store-id',
        default='linda_quilting',
        help='Store ID for segmentation'
    )

    args = parser.parse_args()

    # Get database URL
    database_url = args.database_url or os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not set")
        return 1

    # Run validation
    validator = SegmentValidator(database_url, args.store_id)

    try:
        await validator.connect()
        results = await validator.run_validation()
        return 0

    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        return 1

    finally:
        await validator.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
