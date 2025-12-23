"""
Platform Intelligence Router

Provides AI-powered customer intelligence APIs for external applications:
- Customer behavioral analysis
- Churn prediction
- LTV forecasting
- Segment statistics
- Archetype information

These APIs are designed to be consumed by Customer Support frontends, CRMs,
Marketing automation tools, and other external applications.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import text
import logging

from backend.core.database import get_db_session
from backend.api.dependencies import require_api_key

router = APIRouter(
    prefix="/api/intelligence",
    tags=["Platform Intelligence"],
    dependencies=[Depends(require_api_key)]
)

logger = logging.getLogger(__name__)


# ==================== Request/Response Models ====================

class AnalyzeRequest(BaseModel):
    """Request model for customer intelligence analysis."""
    customer_id: str = Field(..., description="Customer ID to analyze")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context (recent orders, current issue, etc.)")

    model_config = {"json_schema_extra": {"example": {
        "customer_id": "6043504148735",
        "context": {
            "recent_orders": ["order_123"],
            "current_issue": "shipping_delay"
        }
    }}}


class ChurnPredictionRequest(BaseModel):
    """Request model for churn prediction."""
    customer_id: str = Field(..., description="Customer ID")
    prediction_window_days: int = Field(90, description="Prediction window in days", ge=30, le=365)

    model_config = {"json_schema_extra": {"example": {
        "customer_id": "6043504148735",
        "prediction_window_days": 90
    }}}


class LTVPredictionRequest(BaseModel):
    """Request model for LTV prediction."""
    customer_id: str = Field(..., description="Customer ID")
    time_horizon_months: int = Field(12, description="Time horizon in months", ge=1, le=36)

    model_config = {"json_schema_extra": {"example": {
        "customer_id": "6043504148735",
        "time_horizon_months": 12
    }}}


# ==================== Endpoints ====================

@router.post("/analyze")
async def analyze_customer(request: AnalyzeRequest):
    """
    Analyze customer behavioral intelligence.

    Returns comprehensive customer intelligence including:
    - Churn risk score and factors
    - Lifetime value (current and predicted)
    - Behavioral segments across multiple axes
    - Archetype classification
    - Communication style recommendations

    This endpoint is designed to enrich customer views in support tools,
    CRMs, and other applications with AI-powered insights.
    """
    try:
        async with get_db_session() as session:
            # Query customer profile with archetype details
            result = await session.execute(
                text("""
                    SELECT
                        cp.customer_id,
                        cp.archetype_id,
                        cp.archetype_level,
                        cp.segment_memberships,
                        cp.dominant_segments,
                        cp.lifetime_value,
                        cp.total_orders,
                        cp.avg_order_value,
                        cp.churn_risk_score,
                        cp.days_since_last_purchase,
                        cp.customer_tenure_days,
                        ad.dominant_segments as archetype_segments,
                        ad.behavioral_traits
                    FROM platform.customer_profiles cp
                    LEFT JOIN platform.archetype_definitions ad ON cp.archetype_id = ad.archetype_id
                    WHERE cp.customer_id = :customer_id
                    LIMIT 1
                """),
                {"customer_id": request.customer_id}
            )

            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Customer {request.customer_id} not found"
                )

            # Parse customer data
            customer_id = row[0]
            archetype_id = row[1]
            archetype_level = row[2]
            segment_memberships = row[3] or {}
            dominant_segments = row[4] or {}
            lifetime_value = float(row[5]) if row[5] else 0.0
            total_orders = row[6] or 0
            avg_order_value = float(row[7]) if row[7] else 0.0
            churn_risk_score = float(row[8]) if row[8] else 0.0
            days_since_last_purchase = row[9]
            customer_tenure_days = row[10]
            archetype_segments = row[11] or {}
            behavioral_traits = row[12] or {}

            # Determine churn risk level
            if churn_risk_score < 0.3:
                risk_level = "low"
            elif churn_risk_score < 0.6:
                risk_level = "medium"
            else:
                risk_level = "high"

            # Identify churn factors
            churn_factors = []
            if days_since_last_purchase and days_since_last_purchase > 90:
                churn_factors.append({
                    "factor": "days_since_purchase",
                    "value": days_since_last_purchase,
                    "impact": 0.15
                })
            if total_orders < 2:
                churn_factors.append({
                    "factor": "low_order_count",
                    "value": total_orders,
                    "impact": 0.10
                })

            # Recommended actions based on churn risk
            recommended_actions = []
            if churn_risk_score > 0.5:
                recommended_actions.append({
                    "action": "send_winback_email",
                    "priority": "high",
                    "expected_impact": 0.12,
                    "timing": "within_7_days"
                })
            if churn_risk_score > 0.7 and lifetime_value > 200:
                recommended_actions.append({
                    "action": "offer_discount",
                    "priority": "urgent",
                    "expected_impact": 0.18,
                    "timing": "immediate"
                })

            # Determine LTV tier
            if lifetime_value < 100:
                ltv_tier = "low-value"
            elif lifetime_value < 500:
                ltv_tier = "mid-value"
            elif lifetime_value < 2000:
                ltv_tier = "high-value"
            else:
                ltv_tier = "vip"

            # Calculate predicted LTV (simple model - could be enhanced with ML)
            # Basic formula: current LTV + (avg order value * expected orders in next 12 months)
            expected_orders_12m = (365 / max(days_since_last_purchase, 30)) * total_orders if days_since_last_purchase else total_orders
            predicted_ltv_12m = lifetime_value + (avg_order_value * min(expected_orders_12m, 12))

            # Build communication style recommendations
            communication_style = {
                "tone": "friendly_professional",
                "emphasis": [],
                "avoid": []
            }

            if archetype_segments:
                price_sens = archetype_segments.get('price_sensitivity', '')
                if 'deal_hunter' in price_sens.lower():
                    communication_style["emphasis"].append("value")
                    communication_style["emphasis"].append("savings")
                elif 'full_price' in price_sens.lower():
                    communication_style["emphasis"].append("quality")
                    communication_style["avoid"].append("discounting")

                freq = archetype_segments.get('purchase_frequency', '')
                if 'power_buyer' in freq.lower():
                    communication_style["tone"] = "efficient_professional"
                elif 'occasional' in freq.lower():
                    communication_style["emphasis"].append("product education")

            # Build response
            response = {
                "customer_id": customer_id,
                "churn_risk": {
                    "score": churn_risk_score,
                    "risk_level": risk_level,
                    "factors": churn_factors,
                    "recommended_actions": recommended_actions
                },
                "lifetime_value": {
                    "current": lifetime_value,
                    "predicted_12m": round(predicted_ltv_12m, 2),
                    "tier": ltv_tier,
                    "total_orders": total_orders,
                    "avg_order_value": avg_order_value
                },
                "segments": segment_memberships,
                "dominant_segments": dominant_segments,
                "archetype": {
                    "id": archetype_id,
                    "level": archetype_level,
                    "traits": behavioral_traits
                },
                "customer_tenure": {
                    "days": customer_tenure_days,
                    "days_since_last_purchase": days_since_last_purchase
                },
                "communication_style": communication_style,
                "context": request.context
            }

            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing customer {request.customer_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze customer: {str(e)}"
        )


@router.post("/predict/churn")
async def predict_churn(request: ChurnPredictionRequest):
    """
    Predict customer churn risk.

    Returns churn probability for the specified time window along with
    factors contributing to churn risk and recommended interventions.
    """
    try:
        async with get_db_session() as session:
            # Query customer profile
            result = await session.execute(
                text("""
                    SELECT
                        customer_id,
                        churn_risk_score,
                        days_since_last_purchase,
                        total_orders,
                        lifetime_value,
                        customer_tenure_days
                    FROM platform.customer_profiles
                    WHERE customer_id = :customer_id
                    LIMIT 1
                """),
                {"customer_id": request.customer_id}
            )

            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Customer {request.customer_id} not found"
                )

            churn_score = float(row[1]) if row[1] else 0.0
            days_since_purchase = row[2]
            total_orders = row[3] or 0
            ltv = float(row[4]) if row[4] else 0.0
            tenure_days = row[5]

            # Determine risk level
            if churn_score < 0.3:
                risk_level = "low"
            elif churn_score < 0.6:
                risk_level = "medium"
            else:
                risk_level = "high"

            # Identify factors
            factors = []
            if days_since_purchase and days_since_purchase > 60:
                factors.append({
                    "factor": "days_since_purchase",
                    "impact": min(0.15 * (days_since_purchase / 90), 0.25)
                })
            if total_orders < 2:
                factors.append({
                    "factor": "low_engagement",
                    "impact": 0.10
                })
            if tenure_days and tenure_days < 90:
                factors.append({
                    "factor": "new_customer",
                    "impact": 0.08
                })

            # Recommended interventions
            interventions = []
            if churn_score > 0.5:
                interventions.append({
                    "action": "send_winback_email",
                    "expected_impact": 0.12,
                    "timing": "within_7_days",
                    "estimated_cost": 0.0
                })
            if churn_score > 0.7 and ltv > 200:
                interventions.append({
                    "action": "offer_discount_10_percent",
                    "expected_impact": 0.18,
                    "timing": "immediate",
                    "estimated_cost": ltv * 0.1
                })

            return {
                "customer_id": request.customer_id,
                "churn_probability": churn_score,
                "risk_level": risk_level,
                "prediction_window_days": request.prediction_window_days,
                "factors": factors,
                "recommended_interventions": interventions
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting churn for {request.customer_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to predict churn: {str(e)}"
        )


@router.post("/predict/ltv")
async def predict_ltv(request: LTVPredictionRequest):
    """
    Predict customer lifetime value.

    Returns predicted LTV for the specified time horizon along with
    confidence intervals and contributing factors.
    """
    try:
        async with get_db_session() as session:
            # Query customer profile
            result = await session.execute(
                text("""
                    SELECT
                        customer_id,
                        lifetime_value,
                        total_orders,
                        avg_order_value,
                        days_since_last_purchase,
                        customer_tenure_days
                    FROM platform.customer_profiles
                    WHERE customer_id = :customer_id
                    LIMIT 1
                """),
                {"customer_id": request.customer_id}
            )

            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Customer {request.customer_id} not found"
                )

            current_ltv = float(row[1]) if row[1] else 0.0
            total_orders = row[2] or 0
            avg_order_value = float(row[3]) if row[3] else 0.0
            days_since_purchase = row[4] or 365
            tenure_days = row[5] or 30

            # Simple LTV prediction model
            # (In production, this would use ML model)
            months = request.time_horizon_months
            expected_orders_per_month = (total_orders / max(tenure_days, 30)) * 30
            predicted_orders = expected_orders_per_month * months * 0.8  # 80% retention assumption
            predicted_ltv = current_ltv + (avg_order_value * predicted_orders)

            # Confidence interval (±20%)
            confidence_low = predicted_ltv * 0.8
            confidence_high = predicted_ltv * 1.2

            # Contributing factors
            factors = [
                {
                    "factor": "purchase_frequency",
                    "weight": 0.35,
                    "value": expected_orders_per_month
                },
                {
                    "factor": "avg_order_value",
                    "weight": 0.28,
                    "value": avg_order_value
                },
                {
                    "factor": "customer_tenure",
                    "weight": 0.20,
                    "value": tenure_days
                },
                {
                    "factor": "recency",
                    "weight": 0.17,
                    "value": days_since_purchase
                }
            ]

            return {
                "customer_id": request.customer_id,
                "current_ltv": current_ltv,
                "predicted_ltv": round(predicted_ltv, 2),
                "time_horizon_months": months,
                "confidence_interval": [round(confidence_low, 2), round(confidence_high, 2)],
                "factors": factors,
                "assumptions": {
                    "retention_rate": 0.8,
                    "expected_orders_per_month": round(expected_orders_per_month, 2)
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting LTV for {request.customer_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to predict LTV: {str(e)}"
        )


@router.get("/segments/stats")
async def get_segment_stats():
    """
    Get segment distribution statistics.

    Returns statistics about customer segments including total customers,
    number of active segments, and distribution across segment axes.
    """
    try:
        async with get_db_session() as session:
            # Count total customers and those with segments
            count_result = await session.execute(
                text("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(CASE WHEN segment_memberships <> '{}' THEN 1 END) as with_segments
                    FROM platform.customer_profiles
                """)
            )
            counts = count_result.fetchone()

            # Get segment distribution by axis
            dist_result = await session.execute(
                text("""
                    SELECT
                        jsonb_object_keys(segment_memberships) as axis,
                        segment_memberships->>jsonb_object_keys(segment_memberships) as segment,
                        COUNT(*) as customer_count
                    FROM platform.customer_profiles
                    WHERE segment_memberships <> '{}'
                    GROUP BY axis, segment
                    ORDER BY axis, customer_count DESC
                """)
            )
            distributions = dist_result.fetchall()

            # Format distribution data
            axes = {}
            for row in distributions:
                axis = row[0]
                segment = row[1]
                count = row[2]

                if axis not in axes:
                    axes[axis] = {
                        "name": axis,
                        "segments": [],
                        "distribution": {}
                    }

                if segment not in axes[axis]["segments"]:
                    axes[axis]["segments"].append(segment)
                axes[axis]["distribution"][segment] = count

            return {
                "total_customers": counts[0],
                "customers_with_segments": counts[1],
                "segments_active": len(axes),
                "axes": list(axes.values())
            }

    except Exception as e:
        logger.error(f"Error getting segment stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get segment stats: {str(e)}"
        )


@router.get("/archetypes")
async def get_archetypes(level: str = "l2"):
    """
    Get available customer archetypes.

    Returns list of archetypes with member counts, average metrics,
    and dominant segment characteristics.

    Args:
        level: Archetype level (l1, l2, or l3). Default: l2
    """
    try:
        async with get_db_session() as session:
            # Aggregate customer profiles by archetype
            result = await session.execute(
                text("""
                    SELECT
                        cp.archetype_id,
                        cp.archetype_level,
                        COUNT(*) as member_count,
                        AVG(cp.lifetime_value) as avg_ltv,
                        AVG(cp.churn_risk_score) as avg_churn_risk,
                        AVG(cp.total_orders) as avg_orders,
                        ad.dominant_segments,
                        ad.behavioral_traits
                    FROM platform.customer_profiles cp
                    LEFT JOIN platform.archetype_definitions ad ON cp.archetype_id = ad.archetype_id
                    WHERE cp.archetype_id IS NOT NULL
                      AND cp.archetype_level = :level
                    GROUP BY cp.archetype_id, cp.archetype_level, ad.dominant_segments, ad.behavioral_traits
                    ORDER BY member_count DESC
                """),
                {"level": level}
            )

            archetypes = []
            total_customers = 0

            for row in result:
                member_count = row[2]
                total_customers += member_count

                archetypes.append({
                    "archetype_id": row[0],
                    "level": row[1],
                    "member_count": member_count,
                    "avg_ltv": round(float(row[3]), 2) if row[3] else 0.0,
                    "avg_churn_risk": round(float(row[4]), 3) if row[4] else 0.0,
                    "avg_orders": round(float(row[5]), 1) if row[5] else 0.0,
                    "dominant_segments": row[6] or {},
                    "behavioral_traits": row[7] or {}
                })

            # Calculate population percentages
            for archetype in archetypes:
                archetype["population_percentage"] = round(
                    (archetype["member_count"] / total_customers * 100) if total_customers > 0 else 0,
                    2
                )

            return {
                "level": level,
                "total_archetypes": len(archetypes),
                "total_customers": total_customers,
                "archetypes": archetypes
            }

    except Exception as e:
        logger.error(f"Error getting archetypes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get archetypes: {str(e)}"
        )
