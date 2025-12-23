#!/usr/bin/env python3
"""
Demo: Segment Naming Transformation

Demonstrates what the segment naming script does:
1. Analyzes current segments (generic IDs like "segment_0")
2. Shows how Claude AI would transform them into human-readable names
3. Displays before/after comparison

This is a DEMO using pre-defined names. The actual script uses Claude AI
to analyze segment characteristics and generate contextual names.
"""

import os
import sys
import asyncio
import asyncpg
import json
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Example segment names that Claude AI would generate based on behavioral patterns
EXAMPLE_SEGMENT_NAMES = {
    'purchase_frequency': {
        'segment_0': {
            'name': 'Steady Shopper',
            'description': 'Regular purchase pattern with consistent engagement',
            'tags': ['reliable', 'engaged', 'predictable']
        },
        'segment_1': {
            'name': 'Occasional Visitor',
            'description': 'Infrequent purchases, needs re-engagement',
            'tags': ['low-frequency', 'at-risk', 'needs-nurturing']
        },
    },
    'purchase_value': {
        'segment_0': {
            'name': 'Value Seeker',
            'description': 'Moderate spending with focus on essential purchases',
            'tags': ['mid-tier', 'practical', 'consistent']
        },
        'segment_1': {
            'name': 'Budget Conscious',
            'description': 'Lower average order value, price-sensitive',
            'tags': ['economical', 'deal-oriented', 'careful-spender']
        },
    },
    'category_exploration': {
        'segment_0': {
            'name': 'Category Specialist',
            'description': 'Focuses deeply on specific product categories',
            'tags': ['focused', 'expert', 'niche']
        },
        'segment_1': {
            'name': 'Curious Browser',
            'description': 'Explores moderately across categories',
            'tags': ['explorative', 'diverse', 'open-minded']
        },
        'segment_2': {
            'name': 'Power Explorer',
            'description': 'Actively discovers new product categories',
            'tags': ['adventurous', 'diverse', 'early-adopter']
        },
        'segment_3': {
            'name': 'Moderate Mixer',
            'description': 'Balanced exploration across familiar categories',
            'tags': ['balanced', 'versatile', 'stable']
        },
        'segment_4': {
            'name': 'Deep Diver',
            'description': 'Intensive focus on few select categories',
            'tags': ['specialized', 'committed', 'expert']
        },
    },
    'customer_maturity': {
        'segment_0': {
            'name': 'Fresh Face',
            'description': 'New customer building relationship with brand',
            'tags': ['new', 'onboarding', 'learning']
        },
        'segment_1': {
            'name': 'Established Regular',
            'description': 'Familiar with brand, consistent engagement',
            'tags': ['established', 'reliable', 'familiar']
        },
        'segment_2': {
            'name': 'Brand Veteran',
            'description': 'Long-term customer with deep brand knowledge',
            'tags': ['loyal', 'experienced', 'advocate']
        },
    },
    'price_sensitivity': {
        'segment_0': {
            'name': 'Strategic Waiter',
            'description': 'Waits for sales and promotional opportunities',
            'tags': ['deal-hunter', 'patient', 'value-focused']
        },
        'segment_1': {
            'name': 'Value Balancer',
            'description': 'Balances price with quality considerations',
            'tags': ['strategic', 'thoughtful', 'balanced']
        },
    },
    'communication_preference': {
        'segment_0': {
            'name': 'Channel Preferred',
            'description': 'Strong preference for specific communication channel',
            'tags': ['consistent', 'predictable', 'channel-loyal']
        },
        'segment_1': {
            'name': 'Multi-Channel Engager',
            'description': 'Engages across multiple communication channels',
            'tags': ['flexible', 'omnichannel', 'adaptive']
        },
    },
    'problem_complexity_profile': {
        'segment_0': {
            'name': 'Self-Sufficient Solver',
            'description': 'Handles issues independently, minimal support needs',
            'tags': ['independent', 'capable', 'low-touch']
        },
        'segment_1': {
            'name': 'Guided Learner',
            'description': 'Appreciates step-by-step guidance',
            'tags': ['collaborative', 'learning', 'engaged']
        },
        'segment_3': {
            'name': 'Solution Seeker',
            'description': 'Proactive in finding solutions with moderate support',
            'tags': ['proactive', 'resourceful', 'moderate-touch']
        },
    },
    'product_knowledge': {
        'segment_0': {
            'name': 'Product Explorer',
            'description': 'Building knowledge through experimentation',
            'tags': ['learning', 'experimental', 'curious']
        },
        'segment_3': {
            'name': 'Informed Buyer',
            'description': 'Well-researched, knows product specifications',
            'tags': ['knowledgeable', 'informed', 'confident']
        },
    },
    'purchase_cadence': {
        'segment_0': {
            'name': 'Weekday Regular',
            'description': 'Consistent weekday shopping pattern',
            'tags': ['routine', 'weekday', 'predictable']
        },
        'segment_1': {
            'name': 'Weekend Warrior',
            'description': 'Prefers weekend shopping sessions',
            'tags': ['weekend', 'leisure-shopper', 'project-oriented']
        },
    },
    'repurchase_behavior': {
        'segment_0': {
            'name': 'Variety Explorer',
            'description': 'Prefers trying new products over repurchasing',
            'tags': ['novelty-seeking', 'experimental', 'diverse']
        },
    },
    'return_behavior': {
        'segment_0': {
            'name': 'Confident Keeper',
            'description': 'Low return rate, satisfied with purchases',
            'tags': ['satisfied', 'decisive', 'low-maintenance']
        },
    },
    'loyalty_trajectory': {
        'segment_0': {
            'name': 'Committed Loyalist',
            'description': 'Strong loyalty with consistent engagement',
            'tags': ['loyal', 'committed', 'brand-advocate']
        },
    },
    'value_sophistication': {
        'segment_1': {
            'name': 'Value Optimizer',
            'description': 'Sophisticated approach to maximizing value',
            'tags': ['strategic', 'analytical', 'value-focused']
        },
    },
}


class SegmentNamingDemo:
    """Demonstrates segment naming transformation"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None

    async def connect(self):
        self.conn = await asyncpg.connect(self.database_url)
        print("✅ Connected to database\n")

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def get_segment_distribution(self):
        """Get current segment distribution"""
        result = await self.conn.fetch("""
            SELECT
                jsonb_object_keys(dominant_segments) as axis,
                dominant_segments->>jsonb_object_keys(dominant_segments) as segment_id,
                COUNT(*) as customer_count
            FROM customer_profiles
            WHERE dominant_segments <> '{}'
            GROUP BY axis, segment_id
            ORDER BY axis, customer_count DESC
        """)

        # Group by axis
        distribution = defaultdict(list)
        for row in result:
            distribution[row['axis']].append({
                'segment_id': row['segment_id'],
                'count': row['customer_count']
            })

        return distribution

    def get_generated_name(self, axis: str, segment_id: str):
        """Get example generated name for demonstration"""
        if axis in EXAMPLE_SEGMENT_NAMES:
            if segment_id in EXAMPLE_SEGMENT_NAMES[axis]:
                return EXAMPLE_SEGMENT_NAMES[axis][segment_id]

        # Default generic naming
        return {
            'name': segment_id.replace('_', ' ').title(),
            'description': f'Behavioral segment in {axis}',
            'tags': ['auto-generated']
        }

    async def demonstrate(self):
        """Run demonstration"""
        print("="*80)
        print("SEGMENT NAMING DEMONSTRATION")
        print("="*80)
        print()
        print("This script uses Claude AI to transform generic segment IDs like")
        print("'segment_0' into meaningful, human-readable names like 'Power Explorer'")
        print()
        print("="*80)
        print()

        # Get current distribution
        print("📊 Analyzing current segments in database...\n")
        distribution = await self.get_segment_distribution()

        total_segments = sum(len(segments) for segments in distribution.values())
        total_customers = 0

        for axis, segments in distribution.items():
            total_customers += sum(s['count'] for s in segments)

        print(f"Found {len(distribution)} axes with {total_segments} unique segments")
        print(f"Covering {total_customers:,} customer profiles\n")
        print("="*80)
        print()

        # Show transformations
        transformations = []

        for axis, segments in sorted(distribution.items()):
            print(f"\n{'='*80}")
            print(f"AXIS: {axis.upper()}")
            print(f"{'='*80}\n")

            for segment in segments[:5]:  # Show top 5 per axis
                segment_id = segment['segment_id']
                count = segment['count']

                # Skip if already has a good name
                if not segment_id.startswith('segment_'):
                    print(f"  ✓ {segment_id}: {count:,} customers")
                    print(f"    Already has descriptive name - no change needed\n")
                    continue

                # Show transformation
                generated = self.get_generated_name(axis, segment_id)

                print(f"  BEFORE: {segment_id}")
                print(f"  AFTER:  {generated['name']}")
                print(f"  📝 Description: {generated['description']}")
                print(f"  🏷️  Tags: {', '.join(generated['tags'])}")
                print(f"  👥 Customers: {count:,}")
                print()

                transformations.append({
                    'axis': axis,
                    'old_id': segment_id,
                    'new_name': generated['name'],
                    'count': count
                })

        # Summary
        print("\n" + "="*80)
        print("TRANSFORMATION SUMMARY")
        print("="*80)
        print()
        print(f"Segments analyzed: {len(transformations)}")
        print(f"Generic IDs transformed: {len([t for t in transformations if t['old_id'].startswith('segment_')])}")
        print()

        if transformations:
            print("Example transformations:")
            for t in transformations[:10]:
                print(f"  • {t['axis']}: '{t['old_id']}' → '{t['new_name']}' ({t['count']:,} customers)")

        print()
        print("="*80)
        print("HOW THIS WORKS IN PRODUCTION")
        print("="*80)
        print()
        print("The actual script (generate_segment_names.py) does the following:")
        print()
        print("1. 📊 Analyzes segment centroids and feature distributions")
        print("   - Examines statistical patterns for each segment")
        print("   - Identifies distinguishing characteristics")
        print()
        print("2. 🤖 Sends data to Claude AI with context:")
        print("   - Axis description (e.g., 'Purchase Frequency')")
        print("   - Segment features and patterns")
        print("   - Relative position to other segments")
        print()
        print("3. 💡 Claude generates contextual names:")
        print("   - Memorable, marketing-friendly names")
        print("   - Business-relevant descriptions")
        print("   - Actionable tags for segmentation")
        print()
        print("4. 💾 Saves to segment_names.json for reference")
        print()
        print("="*80)
        print("BUSINESS VALUE")
        print("="*80)
        print()
        print("✓ Marketing teams understand segments instantly")
        print("✓ Support reps see personality summaries, not IDs")
        print("✓ Campaign managers can target 'Power Explorers' vs 'segment_2'")
        print("✓ Executives get meaningful reports, not technical jargon")
        print("✓ Cross-functional teams speak the same language")
        print()
        print("="*80)
        print("TO RUN WITH REAL CLAUDE AI:")
        print("="*80)
        print()
        print("  export ANTHROPIC_API_KEY='your-api-key'")
        print("  python3 scripts/generate_segment_names.py")
        print()
        print("This will generate actual context-aware names based on your data.")
        print("="*80)


async def main():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return

    demo = SegmentNamingDemo(database_url)
    try:
        await demo.connect()
        await demo.demonstrate()
    finally:
        await demo.close()


if __name__ == "__main__":
    asyncio.run(main())
