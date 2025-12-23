"""
Load customer data from customer_profiles table into MCP in-memory data store.

This module provides functions to query the Railway PostgreSQL customer_profiles table
and populate the MCP server's in-memory data structures for fast querying.
"""
import logging
from typing import Dict, List, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def load_customers_from_star_schema(
    archetype_level: str = "l2",
    limit: int = None
) -> Dict[str, Dict[str, Any]]:
    """
    Load customer profiles from customer_profiles table.

    Args:
        archetype_level: Which archetype level to load ("l1", "l2", or "l3") - ignored for now
        limit: Optional limit on number of customers to load

    Returns:
        Dict mapping customer_id to customer profile data
    """
    logger.info(f"Loading customers from customer_profiles table...")

    customers = {}

    async with AsyncSessionLocal() as session:
        # Query customer_profiles table (where the actual data is stored)
        query = """
            SELECT
                customer_id,
                archetype_id,
                lifetime_value,
                total_orders,
                avg_order_value,
                days_since_last_purchase,
                customer_tenure_days,
                churn_risk_score,
                segment_memberships,
                dominant_segments
            FROM platform.customer_profiles
        """

        if limit:
            query += f" LIMIT {limit}"

        result = await session.execute(text(query))

        for row in result:
            # Convert customer_id to string for consistency
            customer_id_str = str(row.customer_id)

            # Load segment data from JSONB columns (if available)
            segment_memberships = row.segment_memberships if hasattr(row, 'segment_memberships') and row.segment_memberships else {}
            dominant_segments = row.dominant_segments if hasattr(row, 'dominant_segments') and row.dominant_segments else {}

            customers[customer_id_str] = {
                'customer_id': customer_id_str,
                'archetype_id': row.archetype_id,  # Using archetype_id column
                'lifetime_value': float(row.lifetime_value) if row.lifetime_value else 0.0,
                'total_orders': row.total_orders or 0,
                'avg_order_value': float(row.avg_order_value) if row.avg_order_value else 0.0,
                'days_since_last_purchase': row.days_since_last_purchase,
                'customer_tenure_days': row.customer_tenure_days,
                'churn_risk_score': float(row.churn_risk_score) if row.churn_risk_score else 0.0,
                'segment_memberships': segment_memberships,  # Loaded from database
                'dominant_segments': dominant_segments,       # Loaded from database
                'membership_strengths': {},  # For L2 only (can be derived from segment_memberships)
            }

    logger.info(f"✅ Loaded {len(customers)} customers from customer_profiles table")
    return customers


async def load_archetypes_from_star_schema(
    archetype_level: str = "l2"
) -> Dict[str, Dict[str, Any]]:
    """
    Load archetype definitions by aggregating customer_profiles data.

    Args:
        archetype_level: Which level to load ("l1", "l2", or "l3") - ignored for now

    Returns:
        Dict mapping archetype_id to archetype data
    """
    logger.info(f"Loading archetypes from customer_profiles (aggregating by archetype)...")

    archetypes = {}

    async with AsyncSessionLocal() as session:
        # Aggregate customer_profiles by archetype to build archetype stats
        query = """
            SELECT
                archetype_id,
                COUNT(*) as member_count,
                AVG(lifetime_value) as avg_lifetime_value,
                AVG(total_orders) as avg_order_frequency,
                AVG(churn_risk_score) as avg_churn_risk
            FROM platform.customer_profiles
            WHERE archetype_id IS NOT NULL
            GROUP BY archetype_id
        """

        result = await session.execute(text(query))

        total_customers = 0
        archetype_counts = {}

        # First pass: count members
        for row in result:
            archetype_counts[row.archetype_id] = row.member_count
            total_customers += row.member_count

        # Second pass: build archetype data with population percentages
        result = await session.execute(text(query))

        for row in result:
            population_pct = (row.member_count / total_customers * 100) if total_customers > 0 else 0

            archetype_data = {
                'archetype_id': row.archetype_id,
                'member_count': row.member_count,
                'population_percentage': population_pct,
                'avg_lifetime_value': float(row.avg_lifetime_value) if row.avg_lifetime_value else 0.0,
                'avg_order_frequency': float(row.avg_order_frequency) if row.avg_order_frequency else 0.0,
                'avg_churn_risk': float(row.avg_churn_risk) if row.avg_churn_risk else 0.0,
                # Placeholder for behavioral data (would need more complex query)
                'dominant_segments': {},
                'behavioral_traits': {},
            }

            archetypes[row.archetype_id] = archetype_data

    logger.info(f"✅ Loaded {len(archetypes)} archetypes from customer_profiles (aggregated)")
    return archetypes


async def load_all_data_from_star_schema(
    archetype_level: str = "l2",
    customer_limit: int = None
) -> tuple[Dict, Dict]:
    """
    Load both customers and archetypes from customer_profiles table.

    Args:
        archetype_level: Which archetype level to use ("l1", "l2", or "l3")
        customer_limit: Optional limit on customers to load

    Returns:
        Tuple of (customers_dict, archetypes_dict)
    """
    logger.info(f"Loading all data from customer_profiles table...")

    customers = await load_customers_from_star_schema(archetype_level, customer_limit)
    archetypes = await load_archetypes_from_star_schema(archetype_level)

    # Enrich customer data with archetype dominant segments
    for customer_id, customer_data in customers.items():
        archetype_id = customer_data['archetype_id']
        if archetype_id in archetypes:
            archetype = archetypes[archetype_id]
            customer_data['dominant_segments'] = archetype['dominant_segments']

            if archetype_level == "l2" and 'membership_strengths' in archetype:
                customer_data['membership_strengths'] = archetype['membership_strengths']
            elif archetype_level == "l3" and 'fuzzy_memberships' in archetype:
                customer_data['segment_memberships'] = archetype['fuzzy_memberships']

    logger.info(f"✅ Loaded {len(customers)} customers and {len(archetypes)} archetypes")
    return customers, archetypes
