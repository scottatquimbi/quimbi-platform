"""
Campaign & Marketing Endpoints Router

Provides:
- Campaign target recommendations
- Campaign recommendations by goal
- Segment-based targeting

All endpoints require API key authentication.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
import random

# Import MCP server
from mcp_server.segmentation_server import handle_mcp_call, data_store

# Import authentication
from backend.api.dependencies import require_api_key

# Import logging
from backend.middleware.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/mcp",
    tags=["campaigns", "marketing"],
    dependencies=[Depends(require_api_key)],
    responses={404: {"description": "Not found"}},
)


# ==================== Campaign Recommendation Endpoints ====================

@router.post("/campaigns/recommend")
async def recommend_campaign_targets(
    campaign_type: str = "retention",  # retention, growth, winback
    target_size: int = 100,
    min_ltv: float = 0
):
    """Recommend customers for campaign targeting."""
    try:
        if not data_store.customers:
            raise HTTPException(status_code=503, detail="No customers loaded")

        candidates = []

        if campaign_type == "retention":
            # Target customers with medium churn risk and high LTV
            for customer_id, customer in data_store.customers.items():
                churn_risk = customer.get("churn_risk", 0)
                total_value = customer.get("total_value", 0)

                if 0.3 <= churn_risk <= 0.7 and total_value >= min_ltv:
                    candidates.append({
                        "customer_id": customer_id,
                        "churn_risk": round(churn_risk, 3),
                        "ltv": round(total_value, 2),
                        "score": round((1 - churn_risk) * total_value, 2)
                    })

        elif campaign_type == "growth":
            # Target customers with high LTV and low churn risk
            for customer_id, customer in data_store.customers.items():
                churn_risk = customer.get("churn_risk", 0)
                total_value = customer.get("total_value", 0)

                if churn_risk < 0.3 and total_value >= min_ltv:
                    candidates.append({
                        "customer_id": customer_id,
                        "churn_risk": round(churn_risk, 3),
                        "ltv": round(total_value, 2),
                        "score": round(total_value * (1 - churn_risk), 2)
                    })

        elif campaign_type == "winback":
            # Target customers with high churn risk
            for customer_id, customer in data_store.customers.items():
                churn_risk = customer.get("churn_risk", 0)
                total_value = customer.get("total_value", 0)

                if churn_risk >= 0.7 and total_value >= min_ltv:
                    candidates.append({
                        "customer_id": customer_id,
                        "churn_risk": round(churn_risk, 3),
                        "ltv": round(total_value, 2),
                        "score": round(churn_risk * total_value, 2)
                    })

        else:
            raise HTTPException(status_code=400, detail=f"Invalid campaign type: {campaign_type}")

        # Sort by score and limit
        candidates.sort(key=lambda x: x["score"], reverse=True)
        recommendations = candidates[:target_size]

        # Calculate aggregate metrics
        if recommendations:
            total_ltv = sum(r["ltv"] for r in recommendations)
            avg_churn = sum(r["churn_risk"] for r in recommendations) / len(recommendations)
        else:
            total_ltv = 0
            avg_churn = 0

        return {
            "campaign_type": campaign_type,
            "target_size": target_size,
            "min_ltv_filter": min_ltv,
            "recommendations": recommendations,
            "total_potential_ltv": round(total_ltv, 2),
            "avg_churn_risk": round(avg_churn, 3),
            "candidates_found": len(candidates)
        }
    except Exception as e:
        logger.error(f"Failed to recommend campaign targets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaign/{goal}")
async def get_campaign_recommendations(goal: str, max_segments: int = 5):
    """
    Get segment recommendations for a campaign.

    Goals: subscription, retention, cross_sell
    """
    try:
        result = handle_mcp_call("recommend_segments_for_campaign", {
            "goal": goal,
            "max_segments": max_segments
        })
        return result
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Invalid campaign goal: {goal}")
    except Exception as e:
        logger.error(f"Failed to get campaign recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
