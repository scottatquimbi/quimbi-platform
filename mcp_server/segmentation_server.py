"""
MCP Server for Customer Segmentation

Provides tools for AI agents to query customer behavioral data.

Tools provided:
- get_customer_profile: Get full profile for a customer
- search_customers: Find customers by segment/archetype
- get_archetype_stats: Get statistics for an archetype
- calculate_segment_trends: Analyze segment growth/decline
- query_similar_customers: Find customers similar to target
- predict_churn_risk: Calculate churn probability
- recommend_segments: Suggest segments for campaign targeting

Usage:
    python mcp_server/segmentation_server.py
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import pickle
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import ML service for churn and LTV predictions
try:
    from backend.ml.model_service import get_model_service
    ML_SERVICE_AVAILABLE = True
    ml_service = get_model_service()
    logger.info("ML service available - will use ML models for predictions")
except ImportError:
    ML_SERVICE_AVAILABLE = False
    ml_service = None
    logger.warning("ML service not available - using rules-based fallback only")


class SegmentationDataStore:
    """In-memory data store for customer profiles and segments."""

    def __init__(self):
        self.customers: Dict[str, Dict] = {}  # customer_id -> profile
        self.archetypes: Dict[str, Dict] = {}  # archetype_id -> archetype info
        self.segments: Dict[str, List[Dict]] = {}  # axis_name -> segments
        self.loaded = False

    def load_from_discovery_results(self, profiles: List, archetypes_dict: Dict, segments: Dict):
        """Load data from discovery results."""
        logger.info(f"Loading {len(profiles)} profiles...")

        # Store profiles
        for profile in profiles:
            customer_data = {
                'customer_id': profile.player_id,
                'archetype_id': None,  # Will be set below
                'segment_memberships': profile.fuzzy_memberships,
                'dominant_segments': profile.dominant_segments,
                'membership_strengths': profile.membership_strength,
                'feature_vectors': {
                    axis: ap.features
                    for axis, ap in profile.axis_profiles.items()
                }
            }

            # Extract business metrics from features
            if 'purchase_value' in customer_data['feature_vectors']:
                pv = customer_data['feature_vectors']['purchase_value']
                customer_data['lifetime_value'] = pv.get('total_lifetime_value')
                customer_data['avg_order_value'] = pv.get('avg_order_value')

            if 'purchase_frequency' in customer_data['feature_vectors']:
                pf = customer_data['feature_vectors']['purchase_frequency']
                customer_data['total_orders'] = pf.get('total_purchases')
                customer_data['days_since_last_purchase'] = pf.get('days_since_last_purchase')

            if 'shopping_maturity' in customer_data['feature_vectors']:
                sm = customer_data['feature_vectors']['shopping_maturity']
                customer_data['customer_tenure_days'] = sm.get('account_age_days')

            self.customers[profile.player_id] = customer_data

        # Store archetypes
        for arch_sig, archetype in archetypes_dict.items():
            archetype_data = {
                'archetype_id': archetype.archetype_id,
                'member_count': archetype.player_count,
                'population_percentage': archetype.population_percentage,
                'dominant_segments': dict(archetype.signature.dominant_tuple),
                'strength_signature': [
                    {'axis': item[0], 'segment': item[1], 'strength': item[2]}
                    for item in archetype.signature.strength_tuple
                    if len(item) == 3
                ]
            }

            self.archetypes[archetype.archetype_id] = archetype_data

            # Link customers to archetype
            for profile in profiles:
                from backend.core.archetype_analyzer import ArchetypeAnalyzer
                profile_sig = ArchetypeAnalyzer.create_strength_signature(profile)
                if profile_sig == arch_sig:
                    self.customers[profile.player_id]['archetype_id'] = archetype.archetype_id

        # Store segments
        self.segments = segments

        self.loaded = True
        logger.info(f"✅ Loaded {len(self.customers)} customers, {len(self.archetypes)} archetypes")


# Global data store
data_store = SegmentationDataStore()


# MCP Tool Functions

def get_customer_profile(customer_id: str) -> Dict[str, Any]:
    """
    Get complete behavioral profile for a customer.

    Args:
        customer_id: Customer identifier

    Returns:
        Dict with customer's archetype, segments, metrics, and behavioral traits
    """
    if not data_store.loaded:
        return {"error": "Data not loaded"}

    if customer_id not in data_store.customers:
        return {"error": f"Customer {customer_id} not found"}

    profile = data_store.customers[customer_id]
    archetype_id = profile.get('archetype_id')

    result = {
        "customer_id": customer_id,
        "archetype": data_store.archetypes.get(archetype_id, {}) if archetype_id else None,
        "dominant_segments": profile['dominant_segments'],
        "membership_strengths": profile['membership_strengths'],
        "business_metrics": {
            "lifetime_value": profile.get('lifetime_value'),
            "total_orders": profile.get('total_orders'),
            "avg_order_value": profile.get('avg_order_value'),
            "days_since_last_purchase": profile.get('days_since_last_purchase'),
            "customer_tenure_days": profile.get('customer_tenure_days')
        }
    }

    return result


def search_customers(
    archetype_id: Optional[str] = None,
    segment_filter: Optional[Dict[str, str]] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Search for customers matching criteria.

    Args:
        archetype_id: Filter by archetype
        segment_filter: Filter by segments, e.g. {"purchase_frequency": "regular"}
        limit: Max results

    Returns:
        List of matching customer profiles
    """
    if not data_store.loaded:
        return []

    results = []

    for cust_id, profile in data_store.customers.items():
        # Filter by archetype
        if archetype_id and profile.get('archetype_id') != archetype_id:
            continue

        # Filter by segments
        if segment_filter:
            match = True
            for axis, segment in segment_filter.items():
                if profile['dominant_segments'].get(axis) != segment:
                    match = False
                    break
            if not match:
                continue

        results.append({
            "customer_id": cust_id,
            "archetype_id": profile.get('archetype_id'),
            "dominant_segments": profile['dominant_segments'],
            "lifetime_value": profile.get('lifetime_value')
        })

        if len(results) >= limit:
            break

    return results


def get_archetype_stats(archetype_id: str) -> Dict[str, Any]:
    """
    Get detailed statistics for an archetype.

    Args:
        archetype_id: Archetype identifier

    Returns:
        Statistics including member count, LTV, retention, behavioral traits
    """
    if not data_store.loaded:
        return {"error": "Data not loaded"}

    if archetype_id not in data_store.archetypes:
        return {"error": f"Archetype {archetype_id} not found"}

    archetype = data_store.archetypes[archetype_id]

    # Calculate aggregate metrics from members
    members = [
        cust for cust in data_store.customers.values()
        if cust.get('archetype_id') == archetype_id
    ]

    ltvs = [m.get('lifetime_value') for m in members if m.get('lifetime_value')]
    orders = [m.get('total_orders') for m in members if m.get('total_orders')]

    stats = {
        "archetype_id": archetype_id,
        "member_count": len(members),
        "population_percentage": archetype['population_percentage'],
        "dominant_segments": archetype['dominant_segments'],
        "strength_signature": archetype['strength_signature'],
        "average_ltv": sum(ltvs) / len(ltvs) if ltvs else 0,
        "total_revenue": sum(ltvs) if ltvs else 0,
        "average_orders": sum(orders) / len(orders) if orders else 0
    }

    return stats


def calculate_segment_trends(
    axis_name: str,
    segment_name: str
) -> Dict[str, Any]:
    """
    Analyze growth/decline trends for a segment.

    Note: Currently returns current state. Will use historical data once available.

    Args:
        axis_name: Behavioral axis
        segment_name: Segment within axis

    Returns:
        Trend analysis with growth rate, member count, projections
    """
    if not data_store.loaded:
        return {"error": "Data not loaded"}

    # Count current members
    current_members = [
        cust for cust in data_store.customers.values()
        if cust['dominant_segments'].get(axis_name) == segment_name
    ]

    # TODO: Compare with historical snapshots for actual trend
    # For now, return current state
    return {
        "axis": axis_name,
        "segment": segment_name,
        "current_members": len(current_members),
        "growth_rate": "N/A - need historical data",
        "note": "Historical snapshots needed for trend analysis"
    }


def predict_churn_risk(customer_id: str) -> Dict[str, Any]:
    """
    Predict churn probability for a customer.

    Uses ML model if available, otherwise falls back to rules-based logic.

    Args:
        customer_id: Customer identifier

    Returns:
        Churn risk score (0-1) with reasoning and risk factors
    """
    if not data_store.loaded:
        return {"error": "Data not loaded"}

    if customer_id not in data_store.customers:
        return {"error": f"Customer {customer_id} not found"}

    # Try ML model first
    if ML_SERVICE_AVAILABLE and ml_service is not None:
        try:
            # Run async prediction in sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, use fallback
                logger.warning("Event loop already running, using rules-based fallback")
            else:
                result = loop.run_until_complete(ml_service.predict_churn(customer_id))
                if 'error' not in result:
                    return result
                else:
                    logger.warning(f"ML prediction error: {result['error']}, falling back to rules")
        except Exception as e:
            logger.error(f"ML prediction failed: {e}, falling back to rules")

    # Fallback to rules-based logic (OLD IMPLEMENTATION)
    profile = data_store.customers[customer_id]
    risk_score = 0.0
    risk_factors = []

    # Check purchase frequency strength
    if profile['membership_strengths'].get('purchase_frequency') == 'weak':
        risk_score += 0.3
        risk_factors.append("Weak purchase frequency")

    # Check days since last purchase
    days_since = profile.get('days_since_last_purchase', 0)
    if days_since > 90:
        risk_score += 0.3
        risk_factors.append(f"{days_since} days since last purchase")

    # Check if occasional buyer
    freq_segment = profile['dominant_segments'].get('purchase_frequency', '')
    if 'occasional' in freq_segment or 'one_time' in freq_segment:
        risk_score += 0.2
        risk_factors.append(f"Purchase pattern: {freq_segment}")

    # Check shopping maturity
    if 'new' in profile['dominant_segments'].get('shopping_maturity', ''):
        risk_score += 0.2
        risk_factors.append("New customer (higher churn risk)")

    risk_score = min(risk_score, 1.0)

    risk_level = "low"
    if risk_score > 0.7:
        risk_level = "critical"
    elif risk_score > 0.5:
        risk_level = "high"
    elif risk_score > 0.3:
        risk_level = "medium"

    return {
        "customer_id": customer_id,
        "churn_risk_score": risk_score,
        "churn_probability": risk_score,  # Alias for consistency
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "recommendation": _get_retention_recommendation(profile, risk_level),
        "model_version": "rules_v1"
    }


def _get_retention_recommendation(profile: Dict, risk_level: str) -> str:
    """Generate retention recommendation based on profile."""
    if risk_level in ['high', 'critical']:
        return "URGENT: Send re-engagement campaign immediately"
    elif risk_level == 'medium':
        return "Schedule reminder email in next 7 days"
    else:
        return "Monitor regularly, no immediate action needed"


def recommend_segments_for_campaign(
    goal: str,
    max_segments: int = 5
) -> List[Dict[str, Any]]:
    """
    Recommend customer segments for a marketing campaign.

    Args:
        goal: Campaign goal (e.g., "subscription", "cross_sell", "retention")
        max_segments: Max number of segments to return

    Returns:
        Ranked list of recommended archetypes with reasoning
    """
    if not data_store.loaded:
        return []

    recommendations = []

    if goal == "subscription":
        # Target routine/consumable buyers
        for arch_id, arch_data in data_store.archetypes.items():
            segments = arch_data['dominant_segments']
            if 'routine_buyer' in segments.get('repurchase_behavior', '') or \
               'consumable_buyer' in segments.get('repurchase_behavior', ''):
                recommendations.append({
                    "archetype_id": arch_id,
                    "member_count": arch_data['member_count'],
                    "reason": "High repurchase rate - good subscription candidate",
                    "segments": segments
                })

    elif goal == "retention":
        # Target at-risk customers
        for arch_id, arch_data in data_store.archetypes.items():
            strength_sig = arch_data['strength_signature']
            # Check if purchase_frequency is weak
            for sig_item in strength_sig:
                if sig_item['axis'] == 'purchase_frequency' and sig_item['strength'] == 'weak':
                    recommendations.append({
                        "archetype_id": arch_id,
                        "member_count": arch_data['member_count'],
                        "reason": "Declining purchase frequency - retention target",
                        "segments": arch_data['dominant_segments']
                    })
                    break

    elif goal == "cross_sell":
        # Target category-loyal customers (can introduce them to new categories)
        for arch_id, arch_data in data_store.archetypes.items():
            segments = arch_data['dominant_segments']
            if 'category_loyal' in segments.get('category_affinity', ''):
                recommendations.append({
                    "archetype_id": arch_id,
                    "member_count": arch_data['member_count'],
                    "reason": "Category-loyal - introduce complementary products",
                    "segments": segments
                })

    # Sort by member count (larger segments = more impact)
    recommendations.sort(key=lambda x: x['member_count'], reverse=True)

    return recommendations[:max_segments]


# MCP Server Interface

def handle_mcp_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle MCP tool call.

    Args:
        tool_name: Name of the tool to call
        arguments: Tool arguments

    Returns:
        Tool result
    """
    try:
        if tool_name == "get_customer_profile":
            return get_customer_profile(**arguments)
        elif tool_name == "search_customers":
            return search_customers(**arguments)
        elif tool_name == "get_archetype_stats":
            return get_archetype_stats(**arguments)
        elif tool_name == "calculate_segment_trends":
            return calculate_segment_trends(**arguments)
        elif tool_name == "predict_churn_risk":
            return predict_churn_risk(**arguments)
        elif tool_name == "recommend_segments_for_campaign":
            return recommend_segments_for_campaign(**arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        logger.error(f"Error in {tool_name}: {e}")
        return {"error": str(e)}


# Tool Manifest for AI
MCP_TOOLS = {
    "get_customer_profile": {
        "description": "Get complete behavioral profile for a customer including archetype, segments, and business metrics",
        "parameters": {
            "customer_id": {"type": "string", "description": "Customer identifier", "required": True}
        }
    },
    "search_customers": {
        "description": "Search for customers matching specific archetype or segment criteria",
        "parameters": {
            "archetype_id": {"type": "string", "description": "Filter by archetype ID", "required": False},
            "segment_filter": {"type": "object", "description": "Filter by segments, e.g. {'purchase_frequency': 'regular'}", "required": False},
            "limit": {"type": "integer", "description": "Max results (default 100)", "required": False}
        }
    },
    "get_archetype_stats": {
        "description": "Get detailed statistics for an archetype including member count, LTV, and behavioral traits",
        "parameters": {
            "archetype_id": {"type": "string", "description": "Archetype identifier", "required": True}
        }
    },
    "calculate_segment_trends": {
        "description": "Analyze growth/decline trends for a segment over time",
        "parameters": {
            "axis_name": {"type": "string", "description": "Behavioral axis", "required": True},
            "segment_name": {"type": "string", "description": "Segment name", "required": True}
        }
    },
    "predict_churn_risk": {
        "description": "Predict churn probability for a customer with risk factors and recommendations",
        "parameters": {
            "customer_id": {"type": "string", "description": "Customer identifier", "required": True}
        }
    },
    "recommend_segments_for_campaign": {
        "description": "Recommend customer segments for a marketing campaign based on goal",
        "parameters": {
            "goal": {"type": "string", "description": "Campaign goal: 'subscription', 'cross_sell', 'retention'", "required": True},
            "max_segments": {"type": "integer", "description": "Max segments to return (default 5)", "required": False}
        }
    }
}


if __name__ == "__main__":
    logger.info("MCP Segmentation Server")
    logger.info(f"Available tools: {list(MCP_TOOLS.keys())}")
    logger.info("\nTo use: Import and call handle_mcp_call(tool_name, arguments)")
