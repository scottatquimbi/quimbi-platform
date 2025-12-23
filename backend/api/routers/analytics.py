"""
Analytics & Aggregation Endpoints Router

Provides:
- Aggregate churn risk analysis
- Customer base growth projections
- Top archetypes ranking
- Archetype growth projections
- Revenue forecasting

All endpoints require API key authentication.
"""

from fastapi import APIRouter, HTTPException, Depends
import random
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

# Import MCP server
from mcp_server.segmentation_server import data_store

# Import authentication
from backend.api.dependencies import require_api_key

# Import logging
from backend.middleware.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/mcp",
    tags=["analytics"],
    dependencies=[Depends(require_api_key)],
    responses={404: {"description": "Not found"}},
)


# ==================== Aggregate Analysis Endpoints ====================

@router.get("/churn/aggregate")
async def get_aggregate_churn():
    """Get aggregate churn risk analysis across all customers."""
    try:
        if not data_store.customers:
            raise HTTPException(status_code=503, detail="No customers loaded")

        # Sample customers for aggregate analysis
        sample_size = min(1000, len(data_store.customers))
        sample_ids = random.sample(list(data_store.customers.keys()), sample_size)

        churn_risks = []
        risk_distribution = {"low": 0, "medium": 0, "high": 0, "critical": 0}

        for customer_id in sample_ids:
            customer = data_store.customers[customer_id]
            churn_risk = customer.get("churn_risk", 0)
            churn_risks.append(churn_risk)

            # Categorize risk
            if churn_risk < 0.2:
                risk_distribution["low"] += 1
            elif churn_risk < 0.5:
                risk_distribution["medium"] += 1
            elif churn_risk < 0.75:
                risk_distribution["high"] += 1
            else:
                risk_distribution["critical"] += 1

        # Calculate percentages
        for category in risk_distribution:
            risk_distribution[category] = round((risk_distribution[category] / sample_size) * 100, 1)

        return {
            "sample_size": sample_size,
            "average_churn_risk": round(statistics.mean(churn_risks), 3),
            "median_churn_risk": round(statistics.median(churn_risks), 3),
            "risk_distribution": risk_distribution,
            "at_risk_customers_pct": risk_distribution["high"] + risk_distribution["critical"],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get aggregate churn: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/growth/projection")
async def get_growth_projection(months: int = 12):
    """Project customer base growth over time based on churn and acquisition."""
    try:
        if not data_store.customers:
            raise HTTPException(status_code=503, detail="No customers loaded")

        # Sample for efficiency
        sample_size = min(1000, len(data_store.customers))
        sample_ids = random.sample(list(data_store.customers.keys()), sample_size)

        # Calculate average churn rate
        churn_risks = [data_store.customers[cid].get("churn_risk", 0) for cid in sample_ids]
        avg_monthly_churn = statistics.mean(churn_risks) / 12  # Convert annual to monthly

        # Estimate acquisition rate from recent growth
        # (In production, this would come from actual acquisition data)
        estimated_monthly_acquisition_rate = 0.03  # 3% monthly growth assumption

        # Project month by month
        current_customers = len(data_store.customers)
        projections = []

        for month in range(1, months + 1):
            # Calculate churn
            churned = int(current_customers * avg_monthly_churn)

            # Calculate new acquisitions
            acquired = int(current_customers * estimated_monthly_acquisition_rate)

            # Net change
            net_growth = acquired - churned
            current_customers += net_growth

            projections.append({
                "month": month,
                "total_customers": current_customers,
                "churned": churned,
                "acquired": acquired,
                "net_growth": net_growth,
                "growth_rate_pct": round((net_growth / (current_customers - net_growth)) * 100, 2)
            })

        return {
            "starting_customers": len(data_store.customers),
            "projected_customers_month_" + str(months): current_customers,
            "total_projected_growth": current_customers - len(data_store.customers),
            "avg_monthly_churn_rate": round(avg_monthly_churn * 100, 2),
            "assumed_acquisition_rate": round(estimated_monthly_acquisition_rate * 100, 2),
            "monthly_projections": projections
        }
    except Exception as e:
        logger.error(f"Failed to get growth projection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/archetypes/top")
async def get_top_archetypes(metric: str = "total_ltv", limit: int = 10):
    """Get top archetypes ranked by specified metric.

    Args:
        metric: Ranking metric - "total_ltv", "avg_ltv", "member_count"
        limit: Number of top archetypes to return (default: 10)
    """
    try:
        if not data_store.customers:
            raise HTTPException(status_code=503, detail="No customers loaded")

        # Aggregate by archetypes
        archetype_stats = defaultdict(lambda: {"members": [], "total_ltv": 0})

        for customer_id, customer in data_store.customers.items():
            # Get primary archetypes
            archetypes = customer.get("archetypes", {})

            for dimension, archetype_value in archetypes.items():
                archetype_id = f"{dimension}:{archetype_value}"
                archetype_stats[archetype_id]["members"].append(customer_id)
                archetype_stats[archetype_id]["total_ltv"] += customer.get("total_value", 0)

        # Calculate aggregates and sort
        ranked_archetypes = []
        for archetype_id, stats in archetype_stats.items():
            member_count = len(stats["members"])
            total_ltv = stats["total_ltv"]
            avg_ltv = total_ltv / member_count if member_count > 0 else 0

            ranked_archetypes.append({
                "archetype_id": archetype_id,
                "member_count": member_count,
                "total_ltv": round(total_ltv, 2),
                "avg_ltv": round(avg_ltv, 2)
            })

        # Sort by requested metric
        if metric == "total_ltv":
            ranked_archetypes.sort(key=lambda x: x["total_ltv"], reverse=True)
        elif metric == "avg_ltv":
            ranked_archetypes.sort(key=lambda x: x["avg_ltv"], reverse=True)
        elif metric == "member_count":
            ranked_archetypes.sort(key=lambda x: x["member_count"], reverse=True)
        else:
            raise HTTPException(status_code=400, detail=f"Invalid metric: {metric}")

        return {
            "metric": metric,
            "top_archetypes": ranked_archetypes[:limit],
            "total_archetypes_analyzed": len(archetype_stats)
        }
    except Exception as e:
        logger.error(f"Failed to get top archetypes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/archetypes/growth-projection")
async def get_archetype_growth_projection(months: int = 12, top_n: int = 10):
    """Project growth/churn for top archetypes over time.

    Args:
        months: Number of months to project (default: 12)
        top_n: Number of top archetypes to analyze (default: 10)
    """
    try:
        if not data_store.customers:
            raise HTTPException(status_code=503, detail="No customers loaded")

        # Get top archetypes by member count
        archetype_members = defaultdict(list)
        for customer_id, customer in data_store.customers.items():
            archetypes = customer.get("archetypes", {})
            for dimension, archetype_value in archetypes.items():
                archetype_id = f"{dimension}:{archetype_value}"
                archetype_members[archetype_id].append(customer_id)

        # Sort by member count
        top_archetypes = sorted(
            archetype_members.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:top_n]

        # Project growth for each
        projections = []
        for archetype_id, member_ids in top_archetypes:
            # Calculate average churn for this archetype
            churn_risks = [
                data_store.customers[cid].get("churn_risk", 0)
                for cid in member_ids
            ]
            avg_monthly_churn = statistics.mean(churn_risks) / 12

            # Project month by month
            current_members = len(member_ids)
            monthly_data = []

            for month in range(1, months + 1):
                churned = int(current_members * avg_monthly_churn)
                # Assume 2% monthly acquisition for this archetype
                acquired = int(current_members * 0.02)
                current_members = current_members - churned + acquired

                monthly_data.append({
                    "month": month,
                    "members": current_members,
                    "churned": churned,
                    "acquired": acquired
                })

            projections.append({
                "archetype_id": archetype_id,
                "starting_members": len(member_ids),
                "projected_members_month_" + str(months): current_members,
                "avg_churn_risk": round(statistics.mean(churn_risks), 3),
                "monthly_projection": monthly_data
            })

        return {
            "months": months,
            "archetypes_analyzed": top_n,
            "projections": projections
        }
    except Exception as e:
        logger.error(f"Failed to get archetype growth projection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/revenue/forecast")
async def forecast_revenue(months: int = 12):
    """Forecast total revenue over specified period."""
    try:
        if not data_store.customers:
            raise HTTPException(status_code=503, detail="No customers loaded")

        # Sample for efficiency
        sample_size = min(1000, len(data_store.customers))
        sample_ids = random.sample(list(data_store.customers.keys()), sample_size)

        # Calculate average order metrics
        total_values = []
        order_counts = []

        for customer_id in sample_ids:
            customer = data_store.customers[customer_id]
            total_values.append(customer.get("total_value", 0))
            order_counts.append(customer.get("order_count", 0))

        avg_customer_value = statistics.mean(total_values)
        avg_orders_per_customer = statistics.mean(order_counts)

        # Estimate monthly order rate
        # Assuming average customer lifetime is 24 months
        avg_monthly_orders_per_customer = avg_orders_per_customer / 24

        # Get churn rate
        churn_risks = [data_store.customers[cid].get("churn_risk", 0) for cid in sample_ids]
        avg_monthly_churn = statistics.mean(churn_risks) / 12

        # Project revenue month by month
        current_customers = len(data_store.customers)
        monthly_forecasts = []
        cumulative_revenue = 0

        for month in range(1, months + 1):
            # Account for churn
            churned = int(current_customers * avg_monthly_churn)

            # Assume 3% acquisition rate
            acquired = int(current_customers * 0.03)

            current_customers = current_customers - churned + acquired

            # Calculate revenue for this month
            monthly_orders = current_customers * avg_monthly_orders_per_customer
            avg_order_value = avg_customer_value / avg_orders_per_customer if avg_orders_per_customer > 0 else 0
            monthly_revenue = monthly_orders * avg_order_value
            cumulative_revenue += monthly_revenue

            monthly_forecasts.append({
                "month": month,
                "active_customers": current_customers,
                "estimated_orders": int(monthly_orders),
                "monthly_revenue": round(monthly_revenue, 2),
                "cumulative_revenue": round(cumulative_revenue, 2)
            })

        return {
            "forecast_months": months,
            "starting_customers": len(data_store.customers),
            "projected_total_revenue": round(cumulative_revenue, 2),
            "avg_monthly_revenue": round(cumulative_revenue / months, 2),
            "monthly_forecasts": monthly_forecasts
        }
    except Exception as e:
        logger.error(f"Failed to forecast revenue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
