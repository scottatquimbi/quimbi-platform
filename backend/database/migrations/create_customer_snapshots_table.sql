-- Customer Profile Snapshots Table
-- Phase 1: Temporal Snapshots for Behavioral Drift Tracking
-- Created: 2025-12-12
-- Purpose: Track customer behavioral changes over time

CREATE TABLE IF NOT EXISTS platform.customer_profile_snapshots (
    -- Primary Key
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Customer Identification
    customer_id BIGINT NOT NULL,
    store_id VARCHAR(100) NOT NULL,

    -- Snapshot Metadata
    snapshot_date DATE NOT NULL,
    snapshot_type VARCHAR(20) NOT NULL,  -- 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'

    -- Profile Data at Snapshot Time (Frozen Copy)
    archetype_id UUID,
    archetype_level INT,
    archetype_name VARCHAR(255),
    dominant_segments JSONB,              -- {axis: segment_name}
    fuzzy_memberships JSONB,              -- {axis: {segment: membership_score}}
    behavioral_features JSONB,            -- Raw feature values per axis

    -- ML Predictions at Snapshot Time
    churn_risk_score FLOAT,
    churn_risk_level VARCHAR(20),
    predicted_ltv FLOAT,

    -- Context Metadata
    orders_at_snapshot INT,
    total_value_at_snapshot NUMERIC(10,2),
    days_since_first_order INT,
    tenure_months FLOAT,

    -- Audit Fields
    created_at TIMESTAMP DEFAULT NOW(),
    data_version VARCHAR(20) DEFAULT 'v1.0',  -- Track schema evolution

    -- Constraints
    CONSTRAINT unique_customer_snapshot UNIQUE (customer_id, snapshot_date, snapshot_type)
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_snapshots_customer_date
    ON platform.customer_profile_snapshots(customer_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_date_type
    ON platform.customer_profile_snapshots(snapshot_date, snapshot_type);

CREATE INDEX IF NOT EXISTS idx_snapshots_store
    ON platform.customer_profile_snapshots(store_id);

CREATE INDEX IF NOT EXISTS idx_snapshots_archetype
    ON platform.customer_profile_snapshots(archetype_id);

CREATE INDEX IF NOT EXISTS idx_snapshots_created_at
    ON platform.customer_profile_snapshots(created_at DESC);

-- Comments for documentation
COMMENT ON TABLE platform.customer_profile_snapshots IS
'Temporal snapshots of customer behavioral profiles for drift analysis';

COMMENT ON COLUMN platform.customer_profile_snapshots.snapshot_type IS
'Retention policy: daily(7d), weekly(60d), monthly(1yr), quarterly(2yr), yearly(5yr)';

COMMENT ON COLUMN platform.customer_profile_snapshots.fuzzy_memberships IS
'Multi-axis fuzzy cluster memberships. Format: {axis_name: {segment_name: membership_score}}';

COMMENT ON COLUMN platform.customer_profile_snapshots.behavioral_features IS
'Raw feature values extracted for each behavioral axis at snapshot time';
