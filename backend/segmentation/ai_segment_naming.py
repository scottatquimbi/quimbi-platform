"""
AI-Powered Segment Naming

Uses Claude API to generate human-readable segment names and interpretations
after clustering discovers behavioral patterns.

This ensures segment names reflect actual customer data rather than
hardcoded assumptions.

Author: Quimbi Platform
Version: 1.0.0
Date: November 6, 2025
"""

import logging
import json
import os
from typing import Tuple, Dict, List
import numpy as np
from anthropic import Anthropic

logger = logging.getLogger(__name__)


async def name_segment_with_ai(
    axis_name: str,
    cluster_center: np.ndarray,
    feature_names: List[str],
    population_X: np.ndarray,
    anthropic_api_key: str
) -> Tuple[str, str]:
    """
    Generate segment name and interpretation using Claude API.

    Args:
        axis_name: Behavioral axis (e.g., 'purchase_frequency')
        cluster_center: Cluster centroid in original feature space
        feature_names: Names of features
        population_X: Full population feature matrix (for statistics)
        anthropic_api_key: Anthropic API key

    Returns:
        (segment_name, interpretation)
    """
    try:
        # Calculate population statistics
        population_stats = _calculate_population_stats(population_X, feature_names)

        # Format cluster features with percentiles
        cluster_features_formatted = _format_cluster_features(
            cluster_center,
            feature_names,
            population_stats
        )

        # Build prompt
        prompt = _build_naming_prompt(axis_name, cluster_features_formatted, population_stats)

        # Call Claude API
        client = Anthropic(api_key=anthropic_api_key)

        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=500,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Parse response
        response_text = response.content[0].text
        result = json.loads(response_text)

        segment_name = result['segment_name']
        interpretation = result['interpretation']

        # Validate format
        segment_name = _validate_segment_name(segment_name)

        logger.info(f"AI named segment: {segment_name} - {interpretation}")

        return segment_name, interpretation

    except Exception as e:
        logger.error(f"AI naming failed: {e}", exc_info=True)
        # Fallback to generic naming
        return _generate_fallback_name(axis_name, cluster_center, feature_names)


def _calculate_population_stats(
    population_X: np.ndarray,
    feature_names: List[str]
) -> Dict[str, Dict[str, float]]:
    """
    Calculate population statistics for each feature.

    Returns:
        {
            feature_name: {
                'min': float,
                'max': float,
                'mean': float,
                'median': float,
                'p25': float,
                'p75': float
            }
        }
    """
    stats = {}

    for i, feature_name in enumerate(feature_names):
        feature_values = population_X[:, i]

        stats[feature_name] = {
            'min': float(np.min(feature_values)),
            'max': float(np.max(feature_values)),
            'mean': float(np.mean(feature_values)),
            'median': float(np.median(feature_values)),
            'p25': float(np.percentile(feature_values, 25)),
            'p75': float(np.percentile(feature_values, 75))
        }

    return stats


def _format_cluster_features(
    cluster_center: np.ndarray,
    feature_names: List[str],
    population_stats: Dict[str, Dict[str, float]]
) -> str:
    """Format cluster features with percentile context"""
    lines = []

    for i, feature_name in enumerate(feature_names):
        value = cluster_center[i]
        stats = population_stats[feature_name]

        # Calculate percentile
        if value <= stats['p25']:
            percentile_label = "VERY LOW (bottom 25%)"
        elif value <= stats['median']:
            percentile_label = "LOW (25th-50th percentile)"
        elif value <= stats['p75']:
            percentile_label = "HIGH (50th-75th percentile)"
        else:
            percentile_label = "VERY HIGH (top 25%)"

        lines.append(
            f"  - {feature_name}: {value:.2f} [{percentile_label}]\n"
            f"    Population: min={stats['min']:.2f}, median={stats['median']:.2f}, max={stats['max']:.2f}"
        )

    return "\n".join(lines)


def _build_naming_prompt(
    axis_name: str,
    cluster_features_formatted: str,
    population_stats: Dict[str, Dict[str, float]]
) -> str:
    """Build Claude API prompt"""

    # Axis-specific context
    axis_descriptions = {
        'purchase_frequency': "how often customers buy and their ordering rhythm",
        'purchase_value': "how much customers spend and their value trajectory",
        'category_exploration': "product variety seeking and exploration behavior",
        'price_sensitivity': "discount dependency and price consciousness",
        'purchase_cadence': "temporal patterns - when customers buy",
        'customer_maturity': "lifecycle stage and tenure",
        'repurchase_behavior': "loyalty and repeat purchase patterns",
        'return_behavior': "return and refund patterns",
        'communication_preference': "channel and timing preferences for interaction",
        'problem_complexity_profile': "issue proneness and support needs",
        'loyalty_trajectory': "engagement trend and churn risk",
        'product_knowledge': "expertise level and guidance needs",
        'value_sophistication': "price point preferences and value perception"
    }

    axis_description = axis_descriptions.get(axis_name, "customer behavior patterns")

    # Example segment names by axis
    examples = {
        'purchase_frequency': [
            "high_frequency_loyalists",
            "occasional_buyers",
            "one_time_customers"
        ],
        'purchase_value': [
            "premium_spenders",
            "value_conscious_buyers",
            "budget_shoppers"
        ],
        'category_exploration': [
            "diverse_explorers",
            "category_specialists",
            "single_focus_buyers"
        ],
        'price_sensitivity': [
            "discount_hunters",
            "price_indifferent",
            "full_price_buyers"
        ],
        'loyalty_trajectory': [
            "accelerating_loyalists",
            "declining_risk",
            "stable_regulars"
        ],
        'problem_complexity_profile': [
            "low_maintenance",
            "high_touch_shoppers",
            "frequent_returners"
        ]
    }

    example_names = examples.get(axis_name, [
        "high_segment",
        "medium_segment",
        "low_segment"
    ])

    prompt = f"""I've discovered a customer segment in the '{axis_name}' behavioral dimension ({axis_description}).

Cluster center features:
{cluster_features_formatted}

Generate:
1. A concise segment name (2-4 words, snake_case, descriptive)
2. A 1-sentence interpretation (20-30 words) explaining this segment's behavior

Guidelines:
- Name should reflect the ACTUAL feature values (not generic "high/low")
- Use e-commerce/retail terminology
- Be specific and actionable
- Focus on what makes this segment UNIQUE

Example segment names for this axis:
{', '.join(example_names)}

Respond in JSON format:
{{
  "segment_name": "descriptive_snake_case_name",
  "interpretation": "One sentence explaining this segment's behavior and characteristics."
}}
"""

    return prompt


def _validate_segment_name(segment_name: str) -> str:
    """Validate and clean segment name"""
    # Remove spaces, convert to snake_case
    segment_name = segment_name.lower().strip()
    segment_name = segment_name.replace(' ', '_')
    segment_name = segment_name.replace('-', '_')

    # Remove special characters
    segment_name = ''.join(c for c in segment_name if c.isalnum() or c == '_')

    # Limit length
    if len(segment_name) > 50:
        segment_name = segment_name[:50]

    # Ensure not empty
    if not segment_name:
        segment_name = "unnamed_segment"

    return segment_name


def _generate_fallback_name(
    axis_name: str,
    cluster_center: np.ndarray,
    feature_names: List[str]
) -> Tuple[str, str]:
    """Generate generic segment name without AI"""
    if len(cluster_center) == 0:
        return f"{axis_name}_segment_unknown", "Segment with insufficient data"

    # Use first feature value to classify
    primary_value = cluster_center[0]
    primary_feature = feature_names[0]

    # High/medium/low classification (assuming standardized features)
    if primary_value > 0.5:
        level = "high"
    elif primary_value > -0.5:
        level = "medium"
    else:
        level = "low"

    segment_name = f"{level}_{axis_name}"
    interpretation = f"Customers with {level} {primary_feature.replace('_', ' ')}"

    return segment_name, interpretation


# Synchronous wrapper if needed
def name_segment_with_ai_sync(
    axis_name: str,
    cluster_center: np.ndarray,
    feature_names: List[str],
    population_X: np.ndarray,
    anthropic_api_key: str
) -> Tuple[str, str]:
    """Synchronous version of name_segment_with_ai"""
    import asyncio

    return asyncio.run(name_segment_with_ai(
        axis_name,
        cluster_center,
        feature_names,
        population_X,
        anthropic_api_key
    ))
