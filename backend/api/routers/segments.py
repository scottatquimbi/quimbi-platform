"""
Segmentation API endpoints.

Provides real-time segment assignment for customers using pre-computed centroids.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional
import numpy as np
import logging

from backend.core.database import get_db_session
from backend.segmentation.ecommerce_feature_extraction import EcommerceFeatureExtractor
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

router = APIRouter(prefix="/segments", tags=["segments"])
logger = logging.getLogger(__name__)


class CustomerSegmentRequest(BaseModel):
    """Request to assign segments to a customer."""
    customer_id: str
    orders: List[Dict]
    items: List[Dict]


class CustomerSegmentResponse(BaseModel):
    """Response with customer segment assignments."""
    customer_id: str
    segment_memberships: Dict[str, str]
    dominant_segments: Dict[str, str]
    membership_strengths: Dict[str, float]
    confidence: float


class SegmentStatsResponse(BaseModel):
    """Response with segment statistics."""
    total_customers: int
    customers_with_segments: int
    axes_count: int
    segments_per_axis: Dict[str, int]
    segment_distribution: Dict[str, Dict[str, int]]


@router.post("/assign", response_model=CustomerSegmentResponse)
async def assign_customer_to_segments(
    request: CustomerSegmentRequest
):
    """
    Assign a customer to behavioral segments in real-time.

    This endpoint:
    1. Extracts behavioral features from customer orders/items
    2. Assigns customer to nearest segment centroids (pre-computed)
    3. Returns segment memberships across all axes

    Use case: Instantly segment new customers or re-segment existing ones
    based on updated purchase history.
    """
    try:
        # Load segment centroids from database
        # TODO: Cache these in memory for performance
        async with get_db_session() as db:
            query = text("""
                SELECT axis_name, centroids, segment_names
                FROM segment_definitions
                WHERE store_id = :store_id
            """)

            result = await db.execute(query, {"store_id": "linda_quilting"})
            centroids_data = result.fetchall()

        if not centroids_data:
            raise HTTPException(
                status_code=404,
                detail="No segment centroids found. Run clustering first."
            )

        # Extract features for this customer
        feature_extractor = EcommerceFeatureExtractor()
        features = feature_extractor.extract_all_features(
            request.customer_id,
            request.orders,
            request.items
        )

        # Assign to segments for each axis
        segment_memberships = {}
        membership_strengths = {}

        for row in centroids_data:
            axis_name = row.axis_name
            centroids = np.array(row.centroids)
            segment_names = row.segment_names

            # Get features for this axis
            axis_features = features.get(axis_name, {})
            if not axis_features:
                continue

            # Convert to numpy array
            feature_vector = np.array(list(axis_features.values()))

            # Find nearest centroid (Euclidean distance)
            distances = np.linalg.norm(centroids - feature_vector, axis=1)
            nearest_idx = np.argmin(distances)

            # Calculate confidence (inverse of distance, normalized)
            confidence = 1.0 / (1.0 + distances[nearest_idx])

            segment_memberships[axis_name] = segment_names[nearest_idx]
            membership_strengths[axis_name] = float(confidence)

        # Calculate overall confidence
        avg_confidence = np.mean(list(membership_strengths.values()))

        return CustomerSegmentResponse(
            customer_id=request.customer_id,
            segment_memberships=segment_memberships,
            dominant_segments=segment_memberships,  # Same for hard clustering
            membership_strengths=membership_strengths,
            confidence=float(avg_confidence)
        )

    except Exception as e:
        logger.error(f"Failed to assign segments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=SegmentStatsResponse)
async def get_segment_statistics():
    """
    Get overall segment statistics.

    Returns:
    - Total customers in database
    - Customers with segments assigned
    - Number of axes
    - Segments per axis
    - Distribution of customers across segments
    """
    try:
        async with get_db_session() as db:
            # Count total customers and those with segments
            count_query = text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN segment_memberships <> '{}' THEN 1 END) as with_segments
                FROM platform.customer_profiles
            """)

            result = await db.execute(count_query)
            counts = result.fetchone()

            # Get segment distribution
            dist_query = text("""
                SELECT
                    jsonb_object_keys(segment_memberships) as axis,
                    segment_memberships->>jsonb_object_keys(segment_memberships) as segment,
                    COUNT(*) as customer_count
                FROM platform.customer_profiles
                WHERE segment_memberships <> '{}'
                GROUP BY axis, segment
                ORDER BY axis, customer_count DESC
            """)

            result = await db.execute(dist_query)
            distributions = result.fetchall()

            # Format distribution data
            segment_distribution = {}
            segments_per_axis = {}

            for row in distributions:
                axis = row.axis
                segment = row.segment
                count = row.customer_count

                if axis not in segment_distribution:
                    segment_distribution[axis] = {}
                    segments_per_axis[axis] = 0

                segment_distribution[axis][segment] = count
                segments_per_axis[axis] += 1

            return SegmentStatsResponse(
                total_customers=counts.total,
                customers_with_segments=counts.with_segments,
                axes_count=len(segment_distribution),
                segments_per_axis=segments_per_axis,
                segment_distribution=segment_distribution
            )

    except Exception as e:
        logger.error(f"Failed to get segment stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}", response_model=CustomerSegmentResponse)
async def get_customer_segments(
    customer_id: str
):
    """
    Get existing segment assignments for a customer.

    Returns the pre-computed segment memberships from the database.
    """
    try:
        async with get_db_session() as db:
            query = text("""
                SELECT
                    customer_id,
                    segment_memberships,
                    dominant_segments,
                    membership_strengths
                FROM platform.customer_profiles
                WHERE customer_id = :customer_id
            """)

            result = await db.execute(query, {"customer_id": customer_id})
            customer = result.fetchone()

            if not customer:
                raise HTTPException(
                    status_code=404,
                    detail=f"Customer {customer_id} not found"
                )

            # Calculate average confidence
            strengths = customer.membership_strengths or {}
            avg_confidence = np.mean(list(strengths.values())) if strengths else 0.0

            return CustomerSegmentResponse(
                customer_id=customer.customer_id,
                segment_memberships=customer.segment_memberships or {},
                dominant_segments=customer.dominant_segments or {},
                membership_strengths=strengths,
                confidence=float(avg_confidence)
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get customer segments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/axes")
async def list_segmentation_axes():
    """
    List all segmentation axes and their descriptions.

    Returns metadata about each behavioral axis used for segmentation.
    """
    axes = {
        "purchase_frequency": {
            "name": "Purchase Frequency",
            "description": "How often customers buy and their ordering rhythm",
            "category": "marketing"
        },
        "purchase_value": {
            "name": "Purchase Value",
            "description": "Customer lifetime value and average order sizes",
            "category": "marketing"
        },
        "category_exploration": {
            "name": "Category Exploration",
            "description": "Breadth of product categories purchased",
            "category": "marketing"
        },
        "price_sensitivity": {
            "name": "Price Sensitivity",
            "description": "Response to discounts and promotional offers",
            "category": "marketing"
        },
        "purchase_cadence": {
            "name": "Purchase Cadence",
            "description": "Timing patterns of purchases (seasonal, weekend, etc.)",
            "category": "marketing"
        },
        "customer_maturity": {
            "name": "Customer Maturity",
            "description": "Stage in customer lifecycle (new, developing, established)",
            "category": "marketing"
        },
        "repurchase_behavior": {
            "name": "Repurchase Behavior",
            "description": "Tendency to rebuy same products vs. try new ones",
            "category": "marketing"
        },
        "return_behavior": {
            "name": "Return Behavior",
            "description": "Frequency and patterns of product returns",
            "category": "marketing"
        },
        "communication_preference": {
            "name": "Communication Preference",
            "description": "Preferred communication channels and responsiveness",
            "category": "support"
        },
        "problem_complexity_profile": {
            "name": "Problem Complexity",
            "description": "Complexity of typical support issues",
            "category": "support"
        },
        "loyalty_trajectory": {
            "name": "Loyalty Trajectory",
            "description": "Trend in customer engagement over time",
            "category": "support"
        },
        "product_knowledge": {
            "name": "Product Knowledge",
            "description": "Level of expertise with products",
            "category": "support"
        },
        "value_sophistication": {
            "name": "Value Sophistication",
            "description": "Understanding of product value propositions",
            "category": "support"
        }
    }

    return {"axes": axes, "total": len(axes)}
