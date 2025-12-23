"""
Behavioral Drift Analysis API Endpoints

Provides API access to customer behavioral drift tracking and analysis.
Feature-flagged - requires ENABLE_TEMPORAL_SNAPSHOTS=true

Endpoints:
- GET /api/drift/customer/{customer_id}/history - Get snapshot history
- GET /api/drift/customer/{customer_id}/analysis - Get drift analysis
- POST /api/drift/snapshot/create - Manually trigger snapshot
- POST /api/drift/snapshot/batch - Batch create snapshots for all customers
- GET /api/drift/trends - Get drift trends across customer base
"""

import os
from datetime import date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.services.snapshot_service import (
    CustomerSnapshotService,
    SnapshotConfig,
    SnapshotType,
    CustomerSnapshot,
)
from backend.services.drift_analysis_service import (
    DriftAnalysisService,
    DriftAnalysis,
    DriftSeverity,
)

router = APIRouter(prefix="/api/drift", tags=["Behavioral Drift Analysis"])


# Pydantic models for API responses
class SnapshotResponse(BaseModel):
    """API response for a customer snapshot"""
    snapshot_id: str
    customer_id: int
    snapshot_date: str
    snapshot_type: str
    archetype_name: Optional[str]
    dominant_segments: dict
    churn_risk_score: Optional[float]
    predicted_ltv: Optional[float]
    orders_at_snapshot: int
    total_value_at_snapshot: float


class AxisDriftResponse(BaseModel):
    """API response for axis-level drift"""
    axis_name: str
    drift_score: float
    old_dominant_segment: str
    new_dominant_segment: str
    segment_changed: bool


class DriftAnalysisResponse(BaseModel):
    """API response for drift analysis"""
    customer_id: int
    start_date: str
    end_date: str
    days_elapsed: int
    overall_drift_score: float
    drift_severity: str
    drift_velocity: float
    axis_drifts: List[AxisDriftResponse]
    segments_changed: List[str]
    transition_count: int
    churn_risk_delta: Optional[float]
    ltv_delta: Optional[float]
    is_anomaly: bool
    is_improving: bool
    is_declining: bool


class DriftSummaryResponse(BaseModel):
    """API response for drift summary statistics"""
    total_periods: int
    average_drift_score: float
    max_drift_score: float
    min_drift_score: float
    drift_volatility: float
    anomaly_count: int
    total_segment_transitions: int
    improving_periods: int
    declining_periods: int
    most_volatile_axes: List[tuple]
    overall_trend: str


class BatchSnapshotRequest(BaseModel):
    """Request body for batch snapshot creation"""
    store_id: str = Field(..., description="Store identifier")
    snapshot_type: str = Field(..., description="Snapshot type: daily, weekly, monthly, quarterly, yearly")
    snapshot_date: Optional[str] = Field(None, description="Date for snapshot (YYYY-MM-DD), defaults to today")


class BatchSnapshotResponse(BaseModel):
    """Response for batch snapshot creation"""
    successful: int
    failed: int
    store_id: str
    snapshot_type: str
    snapshot_date: str


def check_feature_enabled():
    """Dependency to check if temporal snapshots are enabled"""
    enabled = os.getenv("ENABLE_TEMPORAL_SNAPSHOTS", "false").lower() == "true"
    if not enabled:
        raise HTTPException(
            status_code=503,
            detail="Temporal snapshots feature is not enabled. Set ENABLE_TEMPORAL_SNAPSHOTS=true to enable."
        )


@router.get("/customer/{customer_id}/history", response_model=List[SnapshotResponse])
async def get_customer_snapshot_history(
    customer_id: int,
    store_id: str = Query(..., description="Store identifier"),
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    snapshot_type: Optional[str] = Query(None, description="Filter by type: daily, weekly, monthly, quarterly, yearly"),
    limit: int = Query(100, le=1000, description="Maximum snapshots to return"),
    _: None = Depends(check_feature_enabled),
    db: AsyncSession = Depends(get_db),
):
    """
    Get snapshot history for a customer.

    Returns list of snapshots ordered by date (newest first).
    """
    service = CustomerSnapshotService(db)

    # Parse dates
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None

    # Parse snapshot type
    snap_type = SnapshotType(snapshot_type) if snapshot_type else None

    snapshots = await service.get_customer_snapshots(
        customer_id=customer_id,
        store_id=store_id,
        start_date=start,
        end_date=end,
        snapshot_type=snap_type,
        limit=limit
    )

    # Convert to API response format
    return [
        SnapshotResponse(
            snapshot_id=str(s.snapshot_id),
            customer_id=s.customer_id,
            snapshot_date=s.snapshot_date.isoformat(),
            snapshot_type=s.snapshot_type.value,
            archetype_name=s.archetype_name,
            dominant_segments=s.dominant_segments,
            churn_risk_score=s.churn_risk_score,
            predicted_ltv=s.predicted_ltv,
            orders_at_snapshot=s.orders_at_snapshot,
            total_value_at_snapshot=s.total_value_at_snapshot,
        )
        for s in snapshots
    ]


@router.get("/customer/{customer_id}/analysis", response_model=DriftAnalysisResponse)
async def get_customer_drift_analysis(
    customer_id: int,
    store_id: str = Query(..., description="Store identifier"),
    comparison_days: int = Query(30, ge=1, le=365, description="Compare current vs N days ago"),
    _: None = Depends(check_feature_enabled),
    db: AsyncSession = Depends(get_db),
):
    """
    Get drift analysis comparing current state vs N days ago.

    Returns drift metrics showing how customer behavior has changed.
    """
    service = CustomerSnapshotService(db)
    drift_service = DriftAnalysisService()

    # Get snapshots
    end_date = date.today()
    start_date = end_date - timedelta(days=comparison_days)

    snapshots = await service.get_customer_snapshots(
        customer_id=customer_id,
        store_id=store_id,
        start_date=start_date,
        end_date=end_date,
        limit=100
    )

    if len(snapshots) < 2:
        raise HTTPException(
            status_code=404,
            detail=f"Not enough snapshots found for drift analysis (need 2+, found {len(snapshots)})"
        )

    # Sort by date (oldest first)
    snapshots.sort(key=lambda s: s.snapshot_date)

    # Compare first and last
    old_snapshot = snapshots[0]
    new_snapshot = snapshots[-1]

    # Analyze drift
    analysis = drift_service.analyze_drift(old_snapshot, new_snapshot)

    # Convert to API response
    return DriftAnalysisResponse(
        customer_id=analysis.customer_id,
        start_date=analysis.start_date.isoformat(),
        end_date=analysis.end_date.isoformat(),
        days_elapsed=analysis.days_elapsed,
        overall_drift_score=analysis.overall_drift_score,
        drift_severity=analysis.drift_severity.value,
        drift_velocity=analysis.drift_velocity,
        axis_drifts=[
            AxisDriftResponse(
                axis_name=drift.axis_name,
                drift_score=drift.drift_score,
                old_dominant_segment=drift.old_dominant_segment,
                new_dominant_segment=drift.new_dominant_segment,
                segment_changed=drift.segment_changed,
            )
            for drift in analysis.axis_drifts.values()
        ],
        segments_changed=analysis.segments_changed,
        transition_count=analysis.transition_count,
        churn_risk_delta=analysis.churn_risk_delta,
        ltv_delta=analysis.ltv_delta,
        is_anomaly=analysis.is_anomaly,
        is_improving=analysis.is_improving,
        is_declining=analysis.is_declining,
    )


@router.get("/customer/{customer_id}/timeline")
async def get_customer_drift_timeline(
    customer_id: int,
    store_id: str = Query(..., description="Store identifier"),
    days_back: int = Query(90, ge=1, le=730, description="Look back N days"),
    _: None = Depends(check_feature_enabled),
    db: AsyncSession = Depends(get_db),
):
    """
    Get drift analysis timeline showing changes over time.

    Returns drift analysis for each consecutive snapshot pair.
    """
    service = CustomerSnapshotService(db)
    drift_service = DriftAnalysisService()

    # Get snapshots
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    snapshots = await service.get_customer_snapshots(
        customer_id=customer_id,
        store_id=store_id,
        start_date=start_date,
        end_date=end_date,
        limit=365  # Max 1 year of daily snapshots
    )

    if len(snapshots) < 2:
        raise HTTPException(
            status_code=404,
            detail=f"Not enough snapshots found for timeline (need 2+, found {len(snapshots)})"
        )

    # Analyze drift timeline
    drift_analyses = drift_service.analyze_drift_timeline(snapshots)

    # Get summary and patterns
    summary = drift_service.get_drift_summary(drift_analyses)
    patterns = drift_service.detect_drift_patterns(drift_analyses)

    # Convert to API response
    timeline = [
        {
            "period_start": a.start_date.isoformat(),
            "period_end": a.end_date.isoformat(),
            "drift_score": a.overall_drift_score,
            "drift_severity": a.drift_severity.value,
            "segments_changed": a.segments_changed,
            "is_anomaly": a.is_anomaly,
            "is_improving": a.is_improving,
        }
        for a in drift_analyses
    ]

    return {
        "customer_id": customer_id,
        "total_snapshots": len(snapshots),
        "date_range": {
            "start": snapshots[0].snapshot_date.isoformat(),
            "end": snapshots[-1].snapshot_date.isoformat(),
        },
        "timeline": timeline,
        "summary": summary,
        "patterns": patterns,
    }


@router.post("/snapshot/create")
async def create_snapshot(
    customer_id: int,
    store_id: str = Query(..., description="Store identifier"),
    snapshot_type: str = Query("daily", description="Snapshot type"),
    _: None = Depends(check_feature_enabled),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger snapshot creation for a customer.

    Useful for testing or on-demand snapshot creation.
    """
    service = CustomerSnapshotService(db)

    # Parse snapshot type
    try:
        snap_type = SnapshotType(snapshot_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid snapshot_type. Must be one of: {[t.value for t in SnapshotType]}"
        )

    snapshot = await service.create_snapshot(
        customer_id=customer_id,
        store_id=store_id,
        snapshot_type=snap_type,
        snapshot_date=date.today()
    )

    if not snapshot:
        raise HTTPException(
            status_code=500,
            detail="Failed to create snapshot (customer may not exist)"
        )

    return {
        "success": True,
        "snapshot_id": str(snapshot.snapshot_id),
        "customer_id": snapshot.customer_id,
        "snapshot_date": snapshot.snapshot_date.isoformat(),
        "snapshot_type": snapshot.snapshot_type.value,
    }


@router.post("/snapshot/batch", response_model=BatchSnapshotResponse)
async def create_batch_snapshots(
    request: BatchSnapshotRequest,
    _: None = Depends(check_feature_enabled),
    db: AsyncSession = Depends(get_db),
):
    """
    Create snapshots for all customers in a store.

    This is typically run as a nightly cron job, but can be triggered manually.
    """
    service = CustomerSnapshotService(db)

    # Parse snapshot type
    try:
        snap_type = SnapshotType(request.snapshot_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid snapshot_type. Must be one of: {[t.value for t in SnapshotType]}"
        )

    # Parse snapshot date
    snap_date = date.fromisoformat(request.snapshot_date) if request.snapshot_date else date.today()

    # Create batch snapshots
    successful, failed = await service.create_snapshots_for_all_customers(
        store_id=request.store_id,
        snapshot_type=snap_type,
        snapshot_date=snap_date
    )

    return BatchSnapshotResponse(
        successful=successful,
        failed=failed,
        store_id=request.store_id,
        snapshot_type=snap_type.value,
        snapshot_date=snap_date.isoformat(),
    )


@router.delete("/snapshot/cleanup")
async def cleanup_old_snapshots(
    store_id: str = Query(..., description="Store identifier"),
    _: None = Depends(check_feature_enabled),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete snapshots older than retention policy.

    Retention policies:
    - Daily: 7 days
    - Weekly: 60 days
    - Monthly: 1 year
    - Quarterly: 2 years
    - Yearly: 5 years
    """
    service = CustomerSnapshotService(db)

    deleted_counts = await service.cleanup_old_snapshots(store_id)

    total_deleted = sum(deleted_counts.values())

    return {
        "success": True,
        "total_deleted": total_deleted,
        "deleted_by_type": {k.value: v for k, v in deleted_counts.items()},
        "store_id": store_id,
    }


@router.get("/health")
async def drift_feature_health():
    """Health check for drift analysis feature"""
    config = SnapshotConfig.from_env()

    return {
        "feature_enabled": config.enabled,
        "configuration": {
            "daily_retention_days": config.daily_retention_days,
            "weekly_retention_days": config.weekly_retention_days,
            "monthly_retention_days": config.monthly_retention_days,
            "store_behavioral_features": config.store_behavioral_features,
            "store_ml_predictions": config.store_ml_predictions,
        },
        "status": "healthy" if config.enabled else "disabled",
    }
