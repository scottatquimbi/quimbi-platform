-- ============================================================================
-- Temporal Snapshots Schema (Phase 2: Drift Analysis Infrastructure)
-- ============================================================================
-- Purpose: Track customer behavioral profiles over time for drift detection
-- Author: Quimbi Platform
-- Date: 2025-12-18
-- Phase: 2 (Temporal Intelligence)
--
-- Tables:
--   1. customer_profile_snapshots - Historical profile snapshots
--   2. archetype_transitions - Track archetype changes over time
--
-- Dependencies: Phase 1 (Enhanced Clustering) must be deployed
-- ============================================================================

-- Schema: platform (reuse existing schema)
-- Tables store temporal data for drift analysis

-- ============================================================================
-- Table 1: Customer Profile Snapshots
-- ============================================================================
-- Stores frozen snapshots of customer profiles at regular intervals
-- Enables drift detection by comparing snapshots over time

CREATE TABLE IF NOT EXISTS platform.customer_profile_snapshots (
    -- Primary key
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    customer_id BIGINT NOT NULL,
    store_id VARCHAR(100) NOT NULL,
    snapshot_date DATE NOT NULL,
    snapshot_type VARCHAR(20) NOT NULL,  -- 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'

    -- Profile data at snapshot time (frozen copy from customer_profiles)
    archetype_id UUID,
    archetype_level INT,
    archetype_name VARCHAR(255),
    dominant_segments JSONB,              -- {axis: segment_name}
    fuzzy_memberships JSONB,              -- {axis: {segment: membership_score}}
    behavioral_features JSONB,            -- Raw feature values per axis

    -- ML predictions at snapshot time
    churn_risk_score FLOAT,
    churn_risk_level VARCHAR(20),
    predicted_ltv FLOAT,

    -- Context metadata (for drift calculation)
    orders_at_snapshot INT,
    total_value_at_snapshot NUMERIC(12,2),
    days_since_first_order INT,
    tenure_months FLOAT,

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    data_version VARCHAR(20) DEFAULT 'v1.0',  -- Track schema changes

    -- Constraints
    CONSTRAINT unique_customer_snapshot UNIQUE (customer_id, snapshot_date, snapshot_type),
    CONSTRAINT valid_snapshot_type CHECK (snapshot_type IN ('daily', 'weekly', 'monthly', 'quarterly', 'yearly'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_snapshots_customer_date
    ON platform.customer_profile_snapshots(customer_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_date_type
    ON platform.customer_profile_snapshots(snapshot_date, snapshot_type);

CREATE INDEX IF NOT EXISTS idx_snapshots_store
    ON platform.customer_profile_snapshots(store_id);

CREATE INDEX IF NOT EXISTS idx_snapshots_archetype
    ON platform.customer_profile_snapshots(archetype_id);

CREATE INDEX IF NOT EXISTS idx_snapshots_created
    ON platform.customer_profile_snapshots(created_at DESC);

-- JSONB indexes for fast queries on membership data
CREATE INDEX IF NOT EXISTS idx_snapshots_fuzzy_memberships
    ON platform.customer_profile_snapshots USING GIN (fuzzy_memberships);

CREATE INDEX IF NOT EXISTS idx_snapshots_dominant_segments
    ON platform.customer_profile_snapshots USING GIN (dominant_segments);

-- Comment
COMMENT ON TABLE platform.customer_profile_snapshots IS
'Temporal snapshots of customer behavioral profiles for drift analysis';

COMMENT ON COLUMN platform.customer_profile_snapshots.snapshot_type IS
'Snapshot interval: daily (7d retention), weekly (60d), monthly (365d), quarterly (2y), yearly (5y)';

COMMENT ON COLUMN platform.customer_profile_snapshots.fuzzy_memberships IS
'Frozen fuzzy membership scores at snapshot time: {axis: {segment: score}}';

COMMENT ON COLUMN platform.customer_profile_snapshots.data_version IS
'Schema version for handling breaking changes in profile structure';


-- ============================================================================
-- Table 2: Archetype Transitions
-- ============================================================================
-- Tracks when customers transition between archetypes
-- Enables journey tracking and common path identification

CREATE TABLE IF NOT EXISTS platform.archetype_transitions (
    -- Primary key
    transition_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    customer_id BIGINT NOT NULL,
    store_id VARCHAR(100) NOT NULL,

    -- Transition details
    from_archetype_id UUID,
    from_archetype_name VARCHAR(255),
    to_archetype_id UUID NOT NULL,
    to_archetype_name VARCHAR(255) NOT NULL,

    -- Timing
    transition_date DATE NOT NULL,
    days_in_previous_archetype INT,  -- Duration in previous archetype

    -- Context
    trigger_event VARCHAR(100),  -- 'purchase', 'churn_risk_increase', 'manual_update', etc.
    orders_during_transition INT,
    value_during_transition NUMERIC(12,2),

    -- Drift metrics
    membership_drift FLOAT,  -- Overall drift magnitude (0-1)
    drift_velocity FLOAT,    -- Drift per day
    axes_changed JSONB,      -- {axis: {from_segment: X, to_segment: Y, drift: Z}}

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT different_archetypes CHECK (
        from_archetype_id IS NULL OR
        from_archetype_id != to_archetype_id
    )
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_transitions_customer
    ON platform.archetype_transitions(customer_id, transition_date DESC);

CREATE INDEX IF NOT EXISTS idx_transitions_archetype
    ON platform.archetype_transitions(from_archetype_id, to_archetype_id);

CREATE INDEX IF NOT EXISTS idx_transitions_date
    ON platform.archetype_transitions(transition_date DESC);

CREATE INDEX IF NOT EXISTS idx_transitions_store
    ON platform.archetype_transitions(store_id);

-- JSONB index for querying axis-level transitions
CREATE INDEX IF NOT EXISTS idx_transitions_axes_changed
    ON platform.archetype_transitions USING GIN (axes_changed);

-- Comment
COMMENT ON TABLE platform.archetype_transitions IS
'Tracks customer archetype transitions over time for journey analysis';

COMMENT ON COLUMN platform.archetype_transitions.membership_drift IS
'Euclidean distance in fuzzy membership space (0=no change, 1=complete change)';

COMMENT ON COLUMN platform.archetype_transitions.axes_changed IS
'Per-axis transition details: {axis: {from_segment, to_segment, drift_score}}';


-- ============================================================================
-- View 1: Recent Snapshots (Last 30 days)
-- ============================================================================
-- Fast access to recent snapshots for drift analysis

CREATE OR REPLACE VIEW platform.recent_snapshots AS
SELECT
    snapshot_id,
    customer_id,
    store_id,
    snapshot_date,
    snapshot_type,
    archetype_name,
    dominant_segments,
    fuzzy_memberships,
    churn_risk_score,
    churn_risk_level,
    created_at
FROM platform.customer_profile_snapshots
WHERE snapshot_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY customer_id, snapshot_date DESC;

COMMENT ON VIEW platform.recent_snapshots IS
'Recent customer profile snapshots (last 30 days) for drift analysis';


-- ============================================================================
-- View 2: Latest Snapshot Per Customer
-- ============================================================================
-- Quick access to most recent snapshot for each customer

CREATE OR REPLACE VIEW platform.latest_customer_snapshots AS
SELECT DISTINCT ON (customer_id, snapshot_type)
    snapshot_id,
    customer_id,
    store_id,
    snapshot_date,
    snapshot_type,
    archetype_name,
    dominant_segments,
    fuzzy_memberships,
    churn_risk_score,
    churn_risk_level,
    orders_at_snapshot,
    total_value_at_snapshot,
    created_at
FROM platform.customer_profile_snapshots
ORDER BY customer_id, snapshot_type, snapshot_date DESC;

COMMENT ON VIEW platform.latest_customer_snapshots IS
'Most recent snapshot per customer per snapshot type';


-- ============================================================================
-- View 3: Archetype Journey Summary
-- ============================================================================
-- Aggregates transition paths for pattern identification

CREATE OR REPLACE VIEW platform.archetype_journey_summary AS
SELECT
    from_archetype_name,
    to_archetype_name,
    COUNT(*) as transition_count,
    AVG(days_in_previous_archetype) as avg_days_before_transition,
    AVG(membership_drift) as avg_drift_magnitude,
    AVG(drift_velocity) as avg_drift_velocity,
    MIN(transition_date) as first_seen,
    MAX(transition_date) as last_seen
FROM platform.archetype_transitions
WHERE from_archetype_name IS NOT NULL
GROUP BY from_archetype_name, to_archetype_name
HAVING COUNT(*) >= 3  -- Only show paths with 3+ occurrences
ORDER BY transition_count DESC;

COMMENT ON VIEW platform.archetype_journey_summary IS
'Common archetype transition paths with statistics (min 3 occurrences)';


-- ============================================================================
-- Function: Calculate Drift Between Snapshots
-- ============================================================================
-- Utility function to calculate Euclidean drift in membership space

CREATE OR REPLACE FUNCTION platform.calculate_membership_drift(
    snapshot1_memberships JSONB,
    snapshot2_memberships JSONB
) RETURNS FLOAT AS $$
DECLARE
    axes TEXT[];
    axis TEXT;
    segments1 JSONB;
    segments2 JSONB;
    all_segments TEXT[];
    segment TEXT;
    m1 FLOAT;
    m2 FLOAT;
    distance_squared FLOAT := 0.0;
BEGIN
    -- Get all axes
    axes := ARRAY(SELECT jsonb_object_keys(snapshot1_memberships));

    -- For each axis, calculate squared differences
    FOREACH axis IN ARRAY axes LOOP
        segments1 := snapshot1_memberships -> axis;
        segments2 := snapshot2_memberships -> axis;

        IF segments1 IS NOT NULL AND segments2 IS NOT NULL THEN
            -- Get all segments in this axis
            all_segments := ARRAY(
                SELECT DISTINCT unnest(
                    ARRAY(SELECT jsonb_object_keys(segments1)) ||
                    ARRAY(SELECT jsonb_object_keys(segments2))
                )
            );

            -- Sum squared differences
            FOREACH segment IN ARRAY all_segments LOOP
                m1 := COALESCE((segments1 ->> segment)::FLOAT, 0.0);
                m2 := COALESCE((segments2 ->> segment)::FLOAT, 0.0);
                distance_squared := distance_squared + POWER(m2 - m1, 2);
            END LOOP;
        END IF;
    END LOOP;

    -- Return Euclidean distance (sqrt of sum of squared differences)
    RETURN SQRT(distance_squared);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION platform.calculate_membership_drift IS
'Calculate Euclidean drift between two fuzzy membership vectors';


-- ============================================================================
-- Sample Query: Customer Drift Analysis
-- ============================================================================
-- Example query to analyze customer drift over last 28 days

COMMENT ON TABLE platform.customer_profile_snapshots IS
'Temporal snapshots of customer behavioral profiles for drift analysis

Example drift analysis query:
WITH snapshot_pairs AS (
    SELECT
        customer_id,
        snapshot_date,
        fuzzy_memberships,
        archetype_name,
        LAG(fuzzy_memberships) OVER (PARTITION BY customer_id ORDER BY snapshot_date) as prev_memberships,
        LAG(snapshot_date) OVER (PARTITION BY customer_id ORDER BY snapshot_date) as prev_date,
        LAG(archetype_name) OVER (PARTITION BY customer_id ORDER BY snapshot_date) as prev_archetype
    FROM platform.customer_profile_snapshots
    WHERE snapshot_type = ''daily''
      AND snapshot_date >= CURRENT_DATE - INTERVAL ''28 days''
)
SELECT
    customer_id,
    snapshot_date,
    prev_date,
    archetype_name,
    prev_archetype,
    platform.calculate_membership_drift(prev_memberships, fuzzy_memberships) as drift_magnitude,
    platform.calculate_membership_drift(prev_memberships, fuzzy_memberships) /
        NULLIF(snapshot_date - prev_date, 0) as drift_velocity
FROM snapshot_pairs
WHERE prev_memberships IS NOT NULL
ORDER BY drift_velocity DESC NULLS LAST
LIMIT 20;
';


-- ============================================================================
-- Grant Permissions
-- ============================================================================
-- Adjust as needed for your environment

-- GRANT SELECT, INSERT, UPDATE ON platform.customer_profile_snapshots TO intelligence_app;
-- GRANT SELECT, INSERT ON platform.archetype_transitions TO intelligence_app;
-- GRANT SELECT ON platform.recent_snapshots TO intelligence_app;
-- GRANT SELECT ON platform.latest_customer_snapshots TO intelligence_app;
-- GRANT SELECT ON platform.archetype_journey_summary TO intelligence_app;


-- ============================================================================
-- Deployment Verification
-- ============================================================================
-- Run these queries to verify successful deployment

/*
-- Check tables exist
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'platform'
  AND table_name IN ('customer_profile_snapshots', 'archetype_transitions')
ORDER BY table_name;

-- Check indexes exist
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'platform'
  AND tablename IN ('customer_profile_snapshots', 'archetype_transitions')
ORDER BY tablename, indexname;

-- Check views exist
SELECT table_name
FROM information_schema.views
WHERE table_schema = 'platform'
  AND table_name LIKE '%snapshot%' OR table_name LIKE '%archetype%'
ORDER BY table_name;

-- Check function exists
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'platform'
  AND routine_name = 'calculate_membership_drift';

-- Test snapshot table is empty
SELECT COUNT(*) as row_count FROM platform.customer_profile_snapshots;

-- Test transition table is empty
SELECT COUNT(*) as row_count FROM platform.archetype_transitions;
*/

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
