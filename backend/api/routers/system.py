"""
System Configuration Router

Provides system-level configuration endpoints for the frontend.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
from backend.api.routers.swagger_examples import SYSTEM_CONFIG_EXAMPLE

router = APIRouter(prefix="/api/system", tags=["system"])


class SegmentConfig(BaseModel):
    """Configuration for a single segment within an axis"""
    name: str
    display_name: str
    description: str
    order: int

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "weekly_shopper",
                "display_name": "Weekly Shopper",
                "description": "Makes 13+ purchases per year",
                "order": 1
            }
        }
    }


class AxisConfig(BaseModel):
    """Configuration for a behavioral axis"""
    name: str
    display_name: str
    description: str
    category: str  # "purchase" or "support"
    segments: List[SegmentConfig]

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "purchase_frequency",
                "display_name": "Purchase Frequency",
                "description": "How often the customer makes purchases",
                "category": "purchase",
                "segments": [
                    {
                        "name": "weekly_shopper",
                        "display_name": "Weekly Shopper",
                        "description": "Makes 13+ purchases per year",
                        "order": 1
                    }
                ]
            }
        }
    }


class SystemConfiguration(BaseModel):
    """Full system configuration"""
    version: str
    axis_count: int
    axes: List[AxisConfig]

    model_config = {"json_schema_extra": {"example": SYSTEM_CONFIG_EXAMPLE}}


# Static configuration for the 13 behavioral axes
# This would ideally come from a database, but for now it's hardcoded
SYSTEM_CONFIG = SystemConfiguration(
    version="1.0.0",
    axis_count=13,
    axes=[
        # Purchase Behavior Axes (8)
        AxisConfig(
            name="purchase_frequency",
            display_name="Purchase Frequency",
            description="How often the customer makes purchases",
            category="purchase",
            segments=[
                SegmentConfig(
                    name="weekly_shopper",
                    display_name="Weekly Shopper",
                    description="Makes 13+ purchases per year",
                    order=1
                ),
                SegmentConfig(
                    name="monthly_shopper",
                    display_name="Monthly Shopper",
                    description="Makes 6-12 purchases per year",
                    order=2
                ),
                SegmentConfig(
                    name="occasional_buyer",
                    display_name="Occasional Buyer",
                    description="Makes 2-5 purchases per year",
                    order=3
                ),
                SegmentConfig(
                    name="one_time_buyer",
                    display_name="One-Time Buyer",
                    description="Single purchase only",
                    order=4
                )
            ]
        ),
        AxisConfig(
            name="purchase_value",
            display_name="Purchase Value",
            description="Average order value tier",
            category="purchase",
            segments=[
                SegmentConfig(
                    name="high_value",
                    display_name="High Value",
                    description="AOV > $150",
                    order=1
                ),
                SegmentConfig(
                    name="medium_value",
                    display_name="Medium Value",
                    description="AOV $50-$150",
                    order=2
                ),
                SegmentConfig(
                    name="low_value",
                    display_name="Low Value",
                    description="AOV < $50",
                    order=3
                )
            ]
        ),
        AxisConfig(
            name="category_exploration",
            display_name="Category Exploration",
            description="Product variety seeking behavior",
            category="purchase",
            segments=[
                SegmentConfig(
                    name="explorer",
                    display_name="Category Explorer",
                    description="Purchases across 4+ categories",
                    order=1
                ),
                SegmentConfig(
                    name="variety_seeker",
                    display_name="Variety Seeker",
                    description="Purchases across 2-3 categories",
                    order=2
                ),
                SegmentConfig(
                    name="focused_buyer",
                    display_name="Focused Buyer",
                    description="Purchases from single category",
                    order=3
                )
            ]
        ),
        AxisConfig(
            name="price_sensitivity",
            display_name="Price Sensitivity",
            description="Discount dependency and price awareness",
            category="purchase",
            segments=[
                SegmentConfig(
                    name="full_price_buyer",
                    display_name="Full Price Buyer",
                    description="Rarely uses discounts",
                    order=1
                ),
                SegmentConfig(
                    name="value_seeker",
                    display_name="Value Seeker",
                    description="Moderate discount usage",
                    order=2
                ),
                SegmentConfig(
                    name="deal_hunter",
                    display_name="Deal Hunter",
                    description="Primarily purchases on sale",
                    order=3
                )
            ]
        ),
        AxisConfig(
            name="purchase_cadence",
            display_name="Purchase Cadence",
            description="Shopping rhythm and timing patterns",
            category="purchase",
            segments=[
                SegmentConfig(
                    name="routine_buyer",
                    display_name="Routine Buyer",
                    description="Consistent purchase intervals",
                    order=1
                ),
                SegmentConfig(
                    name="seasonal_shopper",
                    display_name="Seasonal Shopper",
                    description="Seasonal purchase patterns",
                    order=2
                ),
                SegmentConfig(
                    name="irregular",
                    display_name="Irregular",
                    description="No predictable pattern",
                    order=3
                )
            ]
        ),
        AxisConfig(
            name="customer_maturity",
            display_name="Customer Maturity",
            description="Customer lifecycle stage and tenure",
            category="purchase",
            segments=[
                SegmentConfig(
                    name="long_term_loyal",
                    display_name="Long-Term Loyal",
                    description="Customer for 2+ years",
                    order=1
                ),
                SegmentConfig(
                    name="established",
                    display_name="Established",
                    description="Customer for 6-24 months",
                    order=2
                ),
                SegmentConfig(
                    name="new_customer",
                    display_name="New Customer",
                    description="Customer for < 6 months",
                    order=3
                )
            ]
        ),
        AxisConfig(
            name="repurchase_behavior",
            display_name="Repurchase Behavior",
            description="Loyalty and repeat buying patterns",
            category="purchase",
            segments=[
                SegmentConfig(
                    name="highly_loyal",
                    display_name="Highly Loyal",
                    description="80%+ repeat purchase rate",
                    order=1
                ),
                SegmentConfig(
                    name="moderate_repeater",
                    display_name="Moderate Repeater",
                    description="40-80% repeat purchase rate",
                    order=2
                ),
                SegmentConfig(
                    name="low_loyalty",
                    display_name="Low Loyalty",
                    description="< 40% repeat purchase rate",
                    order=3
                )
            ]
        ),
        AxisConfig(
            name="return_behavior",
            display_name="Return Behavior",
            description="Product return patterns",
            category="purchase",
            segments=[
                SegmentConfig(
                    name="never_returns",
                    display_name="Never Returns",
                    description="No returns in history",
                    order=1
                ),
                SegmentConfig(
                    name="occasional_returner",
                    display_name="Occasional Returner",
                    description="1-2 returns",
                    order=2
                ),
                SegmentConfig(
                    name="frequent_returner",
                    display_name="Frequent Returner",
                    description="3+ returns",
                    order=3
                )
            ]
        ),

        # Support Behavior Axes (5)
        AxisConfig(
            name="communication_preference",
            display_name="Communication Preference",
            description="Preferred support channel",
            category="support",
            segments=[
                SegmentConfig(
                    name="self_service",
                    display_name="Self-Service",
                    description="Rarely contacts support",
                    order=1
                ),
                SegmentConfig(
                    name="email_preferred",
                    display_name="Email Preferred",
                    description="Prefers email communication",
                    order=2
                ),
                SegmentConfig(
                    name="phone_caller",
                    display_name="Phone Caller",
                    description="Prefers phone support",
                    order=3
                )
            ]
        ),
        AxisConfig(
            name="problem_complexity_profile",
            display_name="Problem Complexity",
            description="Typical support issue complexity",
            category="support",
            segments=[
                SegmentConfig(
                    name="simple_questions",
                    display_name="Simple Questions",
                    description="Basic inquiries",
                    order=1
                ),
                SegmentConfig(
                    name="moderate_issues",
                    display_name="Moderate Issues",
                    description="Standard problem resolution",
                    order=2
                ),
                SegmentConfig(
                    name="complex_problems",
                    display_name="Complex Problems",
                    description="Technical or multi-step issues",
                    order=3
                )
            ]
        ),
        AxisConfig(
            name="loyalty_trajectory",
            display_name="Loyalty Trajectory",
            description="Engagement trend over time",
            category="support",
            segments=[
                SegmentConfig(
                    name="growing_engagement",
                    display_name="Growing Engagement",
                    description="Increasing purchase frequency",
                    order=1
                ),
                SegmentConfig(
                    name="stable",
                    display_name="Stable",
                    description="Consistent engagement",
                    order=2
                ),
                SegmentConfig(
                    name="declining",
                    display_name="Declining",
                    description="Decreasing engagement",
                    order=3
                )
            ]
        ),
        AxisConfig(
            name="product_knowledge",
            display_name="Product Knowledge",
            description="Customer expertise level",
            category="support",
            segments=[
                SegmentConfig(
                    name="expert",
                    display_name="Expert User",
                    description="Deep product knowledge",
                    order=1
                ),
                SegmentConfig(
                    name="intermediate",
                    display_name="Intermediate",
                    description="Moderate familiarity",
                    order=2
                ),
                SegmentConfig(
                    name="beginner",
                    display_name="Beginner",
                    description="New to products",
                    order=3
                )
            ]
        ),
        AxisConfig(
            name="value_sophistication",
            display_name="Value Sophistication",
            description="Understanding of product value and quality",
            category="support",
            segments=[
                SegmentConfig(
                    name="value_aware",
                    display_name="Value Aware",
                    description="Understands quality/price relationship",
                    order=1
                ),
                SegmentConfig(
                    name="feature_focused",
                    display_name="Feature Focused",
                    description="Focuses on specific features",
                    order=2
                ),
                SegmentConfig(
                    name="price_focused",
                    display_name="Price Focused",
                    description="Primarily price-driven",
                    order=3
                )
            ]
        )
    ]
)


@router.get("/configuration", response_model=SystemConfiguration)
async def get_system_configuration():
    """
    Get dynamic system configuration including all behavioral axes and segments.

    This endpoint provides the frontend with the current system configuration,
    allowing it to dynamically render segment names, descriptions, and categories
    without hardcoding them.

    Returns:
        SystemConfiguration: Complete system configuration with all 13 axes
    """
    return SYSTEM_CONFIG
