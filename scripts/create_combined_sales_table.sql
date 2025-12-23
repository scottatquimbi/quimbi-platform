-- ============================================================================
-- Create combined_sales table in Railway Postgres
-- ============================================================================
-- Run this in Railway Postgres before first sync
-- ============================================================================

CREATE TABLE IF NOT EXISTS combined_sales (
    -- Primary keys
    id BIGSERIAL PRIMARY KEY,
    sync_timestamp TIMESTAMP DEFAULT NOW(),

    -- Order identifiers
    order_id BIGINT,
    order_number BIGINT,
    customer_id BIGINT NOT NULL,

    -- Time dimensions
    order_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP,
    year INTEGER,
    quarter INTEGER,
    month INTEGER,
    month_name VARCHAR(20),
    week INTEGER,
    day INTEGER,
    week_day VARCHAR(20),

    -- Product details
    sku VARCHAR(255),
    product_id BIGINT,
    product_name TEXT,
    variant_name TEXT,
    product_type VARCHAR(255),
    category VARCHAR(255),

    -- Sales metrics (line-item level)
    quantity BIGINT,
    line_item_sales NUMERIC(18,2),
    line_item_discount NUMERIC(18,2),
    line_item_refunds NUMERIC(18,2),
    currency VARCHAR(10),
    sales_channel VARCHAR(255),

    -- Order-level enrichment
    latitude FLOAT,
    longitude FLOAT,
    fulfillment_status VARCHAR(100),
    financial_status VARCHAR(100),
    order_total NUMERIC(18,2),
    order_total_items BIGINT
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_combined_sales_customer ON combined_sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_combined_sales_order_date ON combined_sales(order_date);
CREATE INDEX IF NOT EXISTS idx_combined_sales_product ON combined_sales(product_id);
CREATE INDEX IF NOT EXISTS idx_combined_sales_category ON combined_sales(category);
CREATE INDEX IF NOT EXISTS idx_combined_sales_sku ON combined_sales(sku);
CREATE INDEX IF NOT EXISTS idx_combined_sales_order_id ON combined_sales(order_id);

-- Add foreign key to customers table (if it exists)
-- Uncomment if you want to enforce referential integrity
-- ALTER TABLE combined_sales
-- ADD CONSTRAINT fk_combined_sales_customer
-- FOREIGN KEY (customer_id) REFERENCES customers(customer_id);

-- Verify table was created
SELECT
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE tablename = 'combined_sales';

-- Check indexes
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'combined_sales'
ORDER BY indexname;
