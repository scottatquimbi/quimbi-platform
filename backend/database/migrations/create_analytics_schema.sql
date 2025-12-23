-- ================================================================
-- PREDICTIVE ANALYTICS SCHEMA
-- Purpose: Ticket forecasting, product analytics, surge detection
-- Author: Quimbi Platform
-- Date: 2025-12-16
-- ================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

-- ================================================================
-- TIME SERIES & FORECASTING TABLES
-- ================================================================

-- Historical ticket volume (for training ML models)
CREATE TABLE analytics.ticket_volume_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Time granularity
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    granularity VARCHAR(20) NOT NULL CHECK (granularity IN ('hour', 'day', 'week', 'month')),

    -- Counts
    ticket_count INTEGER NOT NULL DEFAULT 0,

    -- Breakdowns
    tickets_by_channel JSONB DEFAULT '{}'::jsonb,
    tickets_by_priority JSONB DEFAULT '{}'::jsonb,
    tickets_by_category JSONB DEFAULT '{}'::jsonb,
    tickets_by_status JSONB DEFAULT '{}'::jsonb,

    -- Contextual data (for feature engineering)
    day_of_week INTEGER CHECK (day_of_week BETWEEN 0 AND 6),
    hour_of_day INTEGER CHECK (hour_of_day BETWEEN 0 AND 23),
    is_holiday BOOLEAN DEFAULT FALSE,
    is_weekend BOOLEAN DEFAULT FALSE,
    week_of_year INTEGER CHECK (week_of_year BETWEEN 1 AND 53),
    month_of_year INTEGER CHECK (month_of_year BETWEEN 1 AND 12),
    quarter INTEGER CHECK (quarter BETWEEN 1 AND 4),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(period_start, period_end, granularity)
);

CREATE INDEX idx_analytics_ticket_volume_period ON analytics.ticket_volume_history(period_start, period_end);
CREATE INDEX idx_analytics_ticket_volume_granularity ON analytics.ticket_volume_history(granularity);
CREATE INDEX idx_analytics_ticket_volume_dow ON analytics.ticket_volume_history(day_of_week);
CREATE INDEX idx_analytics_ticket_volume_created ON analytics.ticket_volume_history(created_at);


-- Ticket volume forecasts
CREATE TABLE analytics.ticket_volume_forecasts (
    forecast_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Forecast metadata
    forecast_created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    forecast_model VARCHAR(100) NOT NULL,
    forecast_version VARCHAR(50),

    -- Time period being forecasted
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    granularity VARCHAR(20) NOT NULL CHECK (granularity IN ('hour', 'day', 'week', 'month')),

    -- Predictions
    predicted_ticket_count INTEGER NOT NULL,
    confidence_interval_lower INTEGER,
    confidence_interval_upper INTEGER,
    confidence_score DECIMAL(5,2) CHECK (confidence_score BETWEEN 0 AND 100),

    -- Breakdowns (predicted)
    predicted_by_channel JSONB DEFAULT '{}'::jsonb,
    predicted_by_priority JSONB DEFAULT '{}'::jsonb,
    predicted_by_category JSONB DEFAULT '{}'::jsonb,

    -- Accuracy tracking (filled in after actual period)
    actual_ticket_count INTEGER,
    error_absolute INTEGER,
    error_percentage DECIMAL(7,2),

    -- Flags
    is_anomaly_expected BOOLEAN DEFAULT FALSE,
    anomaly_reason TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_analytics_forecast_period ON analytics.ticket_volume_forecasts(period_start, period_end);
CREATE INDEX idx_analytics_forecast_created ON analytics.ticket_volume_forecasts(forecast_created_at);
CREATE INDEX idx_analytics_forecast_model ON analytics.ticket_volume_forecasts(forecast_model, forecast_version);


-- ================================================================
-- PRODUCT ANALYTICS TABLES
-- ================================================================

-- Product-Ticket correlation
CREATE TABLE analytics.product_ticket_correlation (
    correlation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Product info
    product_id VARCHAR(100) NOT NULL,
    product_title VARCHAR(500),
    product_type VARCHAR(200),
    vendor VARCHAR(200),

    -- Time period
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Sales metrics
    units_sold INTEGER NOT NULL DEFAULT 0,
    revenue_generated DECIMAL(12,2) DEFAULT 0,
    unique_customers INTEGER DEFAULT 0,

    -- Support metrics
    tickets_generated INTEGER NOT NULL DEFAULT 0,
    ticket_rate DECIMAL(5,2),
    avg_ticket_rate_for_category DECIMAL(5,2),

    -- Ticket breakdown
    ticket_subjects JSONB DEFAULT '[]'::jsonb,
    ticket_categories JSONB DEFAULT '{}'::jsonb,
    avg_resolution_time_hours DECIMAL(8,2),

    -- Flags
    is_high_ticket_product BOOLEAN DEFAULT FALSE,
    is_trending_up BOOLEAN DEFAULT FALSE,

    -- Recommendations
    recommended_actions JSONB DEFAULT '[]'::jsonb,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(product_id, period_start, period_end)
);

CREATE INDEX idx_analytics_product_correlation_product ON analytics.product_ticket_correlation(product_id);
CREATE INDEX idx_analytics_product_correlation_period ON analytics.product_ticket_correlation(period_start, period_end);
CREATE INDEX idx_analytics_product_correlation_high_ticket ON analytics.product_ticket_correlation(is_high_ticket_product) WHERE is_high_ticket_product = TRUE;
CREATE INDEX idx_analytics_product_correlation_trending ON analytics.product_ticket_correlation(is_trending_up) WHERE is_trending_up = TRUE;


-- ================================================================
-- PATTERN DETECTION TABLES
-- ================================================================

-- Seasonal patterns
CREATE TABLE analytics.seasonal_patterns (
    pattern_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pattern metadata
    pattern_name VARCHAR(200) NOT NULL,
    pattern_type VARCHAR(50) CHECK (pattern_type IN ('annual', 'monthly', 'weekly', 'daily')),

    -- Time windows
    recurrence_rule TEXT,
    start_date DATE,
    end_date DATE,

    -- Pattern characteristics
    volume_multiplier DECIMAL(4,2) DEFAULT 1.0,
    duration_days INTEGER,
    peak_day_offset INTEGER,

    -- Top ticket categories during pattern
    top_categories JSONB DEFAULT '[]'::jsonb,
    top_subjects JSONB DEFAULT '[]'::jsonb,

    -- Recommendations
    staffing_recommendation JSONB DEFAULT '{}'::jsonb,
    kb_content_recommendations JSONB DEFAULT '[]'::jsonb,

    -- Confidence
    occurrences_observed INTEGER DEFAULT 1,
    confidence_score DECIMAL(3,2) CHECK (confidence_score BETWEEN 0 AND 1),

    -- Metadata
    detected_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_analytics_seasonal_patterns_type ON analytics.seasonal_patterns(pattern_type);
CREATE INDEX idx_analytics_seasonal_patterns_dates ON analytics.seasonal_patterns(start_date, end_date);


-- ================================================================
-- REAL-TIME SURGE DETECTION TABLES
-- ================================================================

-- Ticket surge events
CREATE TABLE analytics.ticket_surge_events (
    surge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Detection metadata
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    detection_method VARCHAR(100),

    -- Surge characteristics
    surge_start TIMESTAMP WITH TIME ZONE NOT NULL,
    surge_end TIMESTAMP WITH TIME ZONE,
    severity VARCHAR(50) CHECK (severity IN ('low', 'medium', 'high', 'critical')),

    -- Metrics
    expected_ticket_rate INTEGER NOT NULL,
    actual_ticket_rate INTEGER NOT NULL,
    surge_magnitude DECIMAL(5,2),

    -- Analysis
    primary_subject_keywords TEXT[],
    affected_channels JSONB DEFAULT '{}'::jsonb,
    affected_categories JSONB DEFAULT '{}'::jsonb,

    -- Root cause
    root_cause VARCHAR(50) CHECK (root_cause IN ('website_bug', 'shipping_delay', 'product_defect', 'marketing_campaign', 'unknown')),
    root_cause_description TEXT,
    related_incident_id VARCHAR(100),

    -- Response
    response_actions JSONB DEFAULT '[]'::jsonb,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,

    -- Impact
    total_excess_tickets INTEGER,
    estimated_customer_impact VARCHAR(50),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_analytics_surge_detected ON analytics.ticket_surge_events(detected_at);
CREATE INDEX idx_analytics_surge_severity ON analytics.ticket_surge_events(severity);
CREATE INDEX idx_analytics_surge_root_cause ON analytics.ticket_surge_events(root_cause);
CREATE INDEX idx_analytics_surge_active ON analytics.ticket_surge_events(surge_end) WHERE surge_end IS NULL;


-- ================================================================
-- STAFFING OPTIMIZATION TABLES
-- ================================================================

-- Staffing recommendations
CREATE TABLE analytics.staffing_recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Time period
    recommendation_for_date DATE NOT NULL,
    shift_start TIME,
    shift_end TIME,

    -- Current staffing
    current_agent_count INTEGER,
    current_schedule_pattern VARCHAR(100),

    -- Predicted demand
    predicted_ticket_volume INTEGER NOT NULL,
    predicted_volume_by_hour JSONB DEFAULT '{}'::jsonb,

    -- Recommendation
    recommended_agent_count INTEGER NOT NULL,
    recommended_changes JSONB DEFAULT '[]'::jsonb,

    -- Business impact
    sla_compliance_current DECIMAL(5,2),
    sla_compliance_recommended DECIMAL(5,2),
    labor_cost_delta DECIMAL(10,2),
    estimated_overtime_hours DECIMAL(6,2),

    -- Confidence
    confidence_score DECIMAL(3,2) CHECK (confidence_score BETWEEN 0 AND 1),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),

    UNIQUE(recommendation_for_date, shift_start, shift_end)
);

CREATE INDEX idx_analytics_staffing_recs_date ON analytics.staffing_recommendations(recommendation_for_date);


-- ================================================================
-- BUSINESS EVENTS TABLES
-- ================================================================

-- Business events catalog (sales, launches, etc.)
CREATE TABLE analytics.business_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event details
    event_name VARCHAR(200) NOT NULL,
    event_type VARCHAR(100) CHECK (event_type IN ('sale', 'product_launch', 'website_change', 'holiday', 'marketing_campaign', 'promotion', 'other')),
    event_start DATE NOT NULL,
    event_end DATE,

    -- Impact on support
    expected_ticket_volume_change DECIMAL(5,2),
    actual_ticket_volume_change DECIMAL(5,2),
    expected_ticket_categories JSONB DEFAULT '[]'::jsonb,

    -- Event metadata
    description TEXT,
    created_by VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_analytics_business_events_type ON analytics.business_events(event_type);
CREATE INDEX idx_analytics_business_events_dates ON analytics.business_events(event_start, event_end);


-- ================================================================
-- MODEL PERFORMANCE TRACKING
-- ================================================================

-- Forecast model performance
CREATE TABLE analytics.forecast_model_performance (
    performance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Model info
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50),
    evaluation_period_start DATE NOT NULL,
    evaluation_period_end DATE NOT NULL,

    -- Accuracy metrics
    total_forecasts INTEGER DEFAULT 0,
    mean_absolute_error DECIMAL(8,2),
    mean_absolute_percentage_error DECIMAL(5,2),
    root_mean_squared_error DECIMAL(8,2),
    r_squared DECIMAL(5,4),

    -- Breakdown by forecast horizon
    accuracy_1day_ahead DECIMAL(5,2),
    accuracy_7day_ahead DECIMAL(5,2),
    accuracy_30day_ahead DECIMAL(5,2),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(model_name, model_version, evaluation_period_start, evaluation_period_end)
);

CREATE INDEX idx_analytics_model_performance_model ON analytics.forecast_model_performance(model_name, model_version);
CREATE INDEX idx_analytics_model_performance_period ON analytics.forecast_model_performance(evaluation_period_start, evaluation_period_end);


-- ================================================================
-- FUNCTIONS & TRIGGERS
-- ================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION analytics.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_analytics_seasonal_patterns_updated_at BEFORE UPDATE
    ON analytics.seasonal_patterns FOR EACH ROW
    EXECUTE FUNCTION analytics.update_updated_at_column();

CREATE TRIGGER update_analytics_business_events_updated_at BEFORE UPDATE
    ON analytics.business_events FOR EACH ROW
    EXECUTE FUNCTION analytics.update_updated_at_column();


-- Calculate forecast accuracy when actual data comes in
CREATE OR REPLACE FUNCTION analytics.calculate_forecast_accuracy()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.actual_ticket_count IS NOT NULL AND OLD.actual_ticket_count IS NULL THEN
        -- Calculate error metrics
        NEW.error_absolute := ABS(NEW.actual_ticket_count - NEW.predicted_ticket_count);

        IF NEW.actual_ticket_count > 0 THEN
            NEW.error_percentage := ((NEW.actual_ticket_count - NEW.predicted_ticket_count)::DECIMAL / NEW.actual_ticket_count * 100);
        END IF;
    END IF;

    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER calculate_analytics_forecast_accuracy BEFORE UPDATE
    ON analytics.ticket_volume_forecasts FOR EACH ROW
    EXECUTE FUNCTION analytics.calculate_forecast_accuracy();


-- ================================================================
-- INITIAL DATA (Business Events Calendar)
-- ================================================================

-- Insert common holidays and shopping events
INSERT INTO analytics.business_events (event_name, event_type, event_start, event_end, description, expected_ticket_volume_change) VALUES
('Black Friday', 'sale', DATE '2025-11-28', DATE '2025-11-28', 'Black Friday shopping event', 0.50),
('Cyber Monday', 'sale', DATE '2025-12-01', DATE '2025-12-01', 'Cyber Monday online shopping', 0.45),
('Holiday Shopping Season', 'holiday', DATE '2025-11-15', DATE '2025-12-25', 'Peak holiday shopping period', 0.35),
('New Year Sale', 'sale', DATE '2026-01-01', DATE '2026-01-07', 'New Year clearance sale', 0.25),
('Valentine''s Day', 'holiday', DATE '2026-02-14', DATE '2026-02-14', 'Valentine''s Day gift shopping', 0.15),
('Spring Cleaning Sale', 'sale', DATE '2026-03-15', DATE '2026-03-31', 'Spring organization and cleaning', 0.20),
('Mother''s Day', 'holiday', DATE '2026-05-10', DATE '2026-05-10', 'Mother''s Day gift shopping', 0.18),
('Father''s Day', 'holiday', DATE '2026-06-21', DATE '2026-06-21', 'Father''s Day gift shopping', 0.12),
('Back to School', 'marketing_campaign', DATE '2026-08-01', DATE '2026-09-15', 'Back to school crafting season', 0.30),
('Halloween Sale', 'sale', DATE '2026-10-20', DATE '2026-10-31', 'Halloween themed projects', 0.15);


-- ================================================================
-- VIEWS
-- ================================================================

-- View: Latest forecasts by day
CREATE VIEW analytics.latest_daily_forecasts AS
SELECT DISTINCT ON (DATE(period_start))
    forecast_id,
    DATE(period_start) as forecast_date,
    predicted_ticket_count,
    confidence_interval_lower,
    confidence_interval_upper,
    forecast_model,
    forecast_created_at,
    actual_ticket_count,
    error_percentage
FROM analytics.ticket_volume_forecasts
WHERE granularity = 'day'
  AND period_start >= CURRENT_DATE
ORDER BY DATE(period_start), forecast_created_at DESC;


-- View: Active surge events
CREATE VIEW analytics.active_surge_events AS
SELECT
    surge_id,
    detected_at,
    surge_start,
    severity,
    expected_ticket_rate,
    actual_ticket_rate,
    surge_magnitude,
    primary_subject_keywords,
    root_cause,
    root_cause_description,
    (NOW() - surge_start) as duration
FROM analytics.ticket_surge_events
WHERE surge_end IS NULL
ORDER BY detected_at DESC;


-- View: High-ticket products (current month)
CREATE VIEW analytics.current_high_ticket_products AS
SELECT
    product_id,
    product_title,
    product_type,
    units_sold,
    tickets_generated,
    ticket_rate,
    avg_ticket_rate_for_category,
    recommended_actions
FROM analytics.product_ticket_correlation
WHERE period_start >= DATE_TRUNC('month', CURRENT_DATE)
  AND is_high_ticket_product = TRUE
ORDER BY ticket_rate DESC
LIMIT 50;


-- ================================================================
-- COMMENTS
-- ================================================================

COMMENT ON SCHEMA analytics IS 'Predictive analytics for ticket forecasting and product insights';
COMMENT ON TABLE analytics.ticket_volume_history IS 'Historical ticket volume aggregated by hour/day/week/month';
COMMENT ON TABLE analytics.ticket_volume_forecasts IS 'ML-generated forecasts with accuracy tracking';
COMMENT ON TABLE analytics.product_ticket_correlation IS 'Products causing disproportionate support tickets';
COMMENT ON TABLE analytics.ticket_surge_events IS 'Real-time anomaly detection for ticket volume spikes';
COMMENT ON TABLE analytics.seasonal_patterns IS 'Recurring patterns (holidays, seasons, etc.)';
COMMENT ON TABLE analytics.staffing_recommendations IS 'Optimal staffing levels based on predicted demand';
