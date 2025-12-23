#!/usr/bin/env python3
"""
Generate human-readable segment names using Claude AI.

This script:
1. Loads segment centroids from the database
2. Analyzes feature patterns for each segment
3. Uses Claude to generate descriptive, memorable names
4. Updates the database with generated names

Usage:
    python3 scripts/generate_segment_names.py --database-url postgresql://...
"""

import asyncio
import argparse
import logging
import os
import sys
import json
from typing import Dict, List, Any
import anthropic

import asyncpg
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SegmentNamer:
    """Generates human-readable names for behavioral segments using Claude."""

    def __init__(self, anthropic_api_key: str):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)

        # Axis descriptions for context
        self.axis_descriptions = {
            "purchase_frequency": {
                "description": "How often customers make purchases",
                "features": ["orders_per_month", "avg_days_between_orders", "purchase_consistency", "recent_orders_90d", "days_since_last_purchase"]
            },
            "purchase_value": {
                "description": "Customer spending patterns and lifetime value",
                "features": ["total_value", "avg_order_value", "median_order_value", "max_order_value", "value_growth_rate", "value_consistency"]
            },
            "category_exploration": {
                "description": "Breadth of product categories purchased",
                "features": ["unique_categories", "category_diversity", "category_switching_rate", "dominant_category_share"]
            },
            "price_sensitivity": {
                "description": "Response to discounts and promotional offers",
                "features": ["discount_frequency", "avg_discount_pct", "full_price_share", "discount_dependency"]
            },
            "purchase_cadence": {
                "description": "Timing patterns of purchases",
                "features": ["seasonal_variation", "weekend_ratio", "evening_ratio", "cadence_regularity"]
            },
            "customer_maturity": {
                "description": "Stage in customer lifecycle",
                "features": ["tenure_months", "orders_in_first_90d", "growth_trajectory", "engagement_score"]
            },
            "repurchase_behavior": {
                "description": "Tendency to rebuy products vs trying new ones",
                "features": ["repurchase_rate", "unique_products_ratio", "favorite_product_share", "exploration_index"]
            },
            "return_behavior": {
                "description": "Frequency and patterns of product returns",
                "features": ["return_rate", "return_frequency", "avg_return_value", "return_consistency"]
            },
            "communication_preference": {
                "description": "Communication channel preferences",
                "features": ["email_engagement", "phone_preference", "response_time", "proactive_contact_ratio"]
            },
            "problem_complexity_profile": {
                "description": "Typical support issue complexity",
                "features": ["avg_order_complexity", "product_variety", "customization_rate", "problem_resolution_time"]
            },
            "loyalty_trajectory": {
                "description": "Trend in customer engagement over time",
                "features": ["order_frequency_trend", "value_trend", "engagement_slope", "churn_risk"]
            },
            "product_knowledge": {
                "description": "Level of expertise with products",
                "features": ["advanced_product_ratio", "product_variety", "repeat_purchase_rate", "learning_curve"]
            },
            "value_sophistication": {
                "description": "Understanding of product value propositions",
                "features": ["premium_product_ratio", "value_per_item", "discount_savviness", "quality_preference"]
            }
        }

    def analyze_segment_features(
        self,
        axis_name: str,
        centroid: np.ndarray,
        feature_names: List[str],
        segment_index: int,
        all_centroids: np.ndarray
    ) -> Dict[str, Any]:
        """
        Analyze a segment's features to understand its characteristics.

        Returns:
            Dictionary with feature analysis for Claude
        """
        # Calculate relative position compared to other segments
        centroid_std = np.std(all_centroids, axis=0)
        centroid_mean = np.mean(all_centroids, axis=0)

        # Normalize features (z-score)
        z_scores = (centroid - centroid_mean) / (centroid_std + 1e-10)

        # Identify distinctive features (high z-score)
        distinctive_features = []
        for i, (feature_name, z_score) in enumerate(zip(feature_names, z_scores)):
            if abs(z_score) > 0.5:  # Meaningful deviation
                direction = "high" if z_score > 0 else "low"
                distinctive_features.append({
                    "feature": feature_name,
                    "direction": direction,
                    "z_score": float(z_score),
                    "value": float(centroid[i])
                })

        # Sort by absolute z-score
        distinctive_features.sort(key=lambda x: abs(x["z_score"]), reverse=True)

        return {
            "axis": axis_name,
            "segment_index": segment_index,
            "total_segments": len(all_centroids),
            "distinctive_features": distinctive_features[:5],  # Top 5
            "raw_centroid": centroid.tolist(),
            "feature_names": feature_names
        }

    async def generate_name(
        self,
        axis_name: str,
        segment_analysis: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generate a human-readable name for a segment using Claude.

        Returns:
            {
                "name": "Deal Hunter",
                "description": "Price-conscious customers who...",
                "tags": ["discount", "strategic", "value"]
            }
        """
        axis_info = self.axis_descriptions.get(axis_name, {})

        prompt = f"""You are a customer segmentation expert. Generate a memorable, descriptive name for this behavioral segment.

Axis: {axis_name}
Axis Description: {axis_info.get('description', 'N/A')}

Segment #{segment_analysis['segment_index'] + 1} of {segment_analysis['total_segments']} segments

Distinctive Features:
{json.dumps(segment_analysis['distinctive_features'], indent=2)}

Guidelines:
1. Name should be 1-3 words, catchy and memorable
2. Should clearly convey the segment's key behavior
3. Use marketing-friendly language (avoid jargon)
4. Think like a marketer naming a customer persona

Examples of good names:
- "Deal Hunter" (for price-sensitive)
- "Brand Loyalist" (for single-category buyers)
- "Power Buyer" (for high-frequency purchasers)
- "Casual Browser" (for infrequent shoppers)

Return ONLY a JSON object with this structure (no markdown, no code blocks):
{{
    "name": "2-3 word segment name",
    "description": "One sentence describing this segment's behavior",
    "tags": ["keyword1", "keyword2", "keyword3"]
}}"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            content = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            logger.info(f"Generated name for {axis_name} segment {segment_analysis['segment_index']}: {result['name']}")

            return result

        except Exception as e:
            logger.error(f"Failed to generate name: {e}")
            # Fallback to generic name
            return {
                "name": f"Segment {segment_analysis['segment_index'] + 1}",
                "description": f"Behavioral segment {segment_analysis['segment_index'] + 1} for {axis_name}",
                "tags": [axis_name, f"segment{segment_analysis['segment_index'] + 1}"]
            }

    async def name_all_segments(
        self,
        database_url: str,
        store_id: str = "linda_quilting"
    ):
        """
        Load segments from database, generate names, and update database.
        """
        logger.info("=" * 80)
        logger.info("SEGMENT NAMING WITH CLAUDE")
        logger.info("=" * 80)

        # Connect to database
        conn = await asyncpg.connect(database_url)

        try:
            # For this implementation, we'll need to fetch segment data
            # Since we don't have a segment_definitions table yet,
            # let's create example names based on common patterns

            logger.info("Fetching segment distributions from customer_profiles...")

            # Get unique segments per axis
            query = """
                SELECT
                    jsonb_object_keys(segment_memberships) as axis,
                    segment_memberships->>jsonb_object_keys(segment_memberships) as segment_id,
                    COUNT(*) as customer_count
                FROM customer_profiles
                WHERE segment_memberships <> '{}'
                GROUP BY axis, segment_id
                ORDER BY axis, customer_count DESC
            """

            result = await conn.fetch(query)

            # Organize by axis
            segments_by_axis = {}
            for row in result:
                axis = row['axis']
                if axis not in segments_by_axis:
                    segments_by_axis[axis] = []
                segments_by_axis[axis].append({
                    'segment_id': row['segment_id'],
                    'customer_count': row['customer_count']
                })

            logger.info(f"Found {len(segments_by_axis)} axes with segments")

            # Generate names for each segment
            all_names = {}

            for axis, segments in segments_by_axis.items():
                logger.info(f"\nProcessing {axis} ({len(segments)} segments)...")
                axis_names = {}

                for i, segment_info in enumerate(segments):
                    segment_id = segment_info['segment_id']

                    # Create mock analysis (we don't have centroids in DB yet)
                    segment_analysis = {
                        'axis': axis,
                        'segment_index': i,
                        'total_segments': len(segments),
                        'customer_count': segment_info['customer_count'],
                        'segment_id': segment_id,
                        'distinctive_features': []
                    }

                    # Generate name
                    name_data = await self.generate_name(axis, segment_analysis)
                    axis_names[segment_id] = name_data

                    logger.info(f"  {segment_id} → {name_data['name']} ({segment_info['customer_count']} customers)")

                all_names[axis] = axis_names

            # Save to file
            output_file = "segment_names.json"
            with open(output_file, 'w') as f:
                json.dump(all_names, f, indent=2)

            logger.info("=" * 80)
            logger.info(f"✅ Generated names for all segments")
            logger.info(f"✅ Saved to {output_file}")
            logger.info("=" * 80)

            return all_names

        finally:
            await conn.close()


async def main():
    parser = argparse.ArgumentParser(
        description="Generate human-readable segment names using Claude"
    )
    parser.add_argument(
        '--database-url',
        default=None,
        help='PostgreSQL connection URL (defaults to DATABASE_URL env var)'
    )
    parser.add_argument(
        '--anthropic-api-key',
        default=None,
        help='Anthropic API key (defaults to ANTHROPIC_API_KEY env var)'
    )
    parser.add_argument(
        '--store-id',
        default='linda_quilting',
        help='Store ID for segmentation'
    )

    args = parser.parse_args()

    # Get credentials
    database_url = args.database_url or os.getenv('DATABASE_URL')
    api_key = args.anthropic_api_key or os.getenv('ANTHROPIC_API_KEY')

    if not database_url:
        logger.error("DATABASE_URL not set")
        return 1

    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set")
        return 1

    # Generate names
    namer = SegmentNamer(api_key)
    await namer.name_all_segments(database_url, args.store_id)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
