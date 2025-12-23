-- Migration 001: Create Schema Separation
-- Date: 2025-11-24
-- Purpose: Separate platform (ML/AI) from support_app (operational) data

-- Create schemas
CREATE SCHEMA IF NOT EXISTS platform;
CREATE SCHEMA IF NOT EXISTS support_app;
CREATE SCHEMA IF NOT EXISTS shared;

-- Move platform tables (ML/AI/Intelligence data)
ALTER TABLE IF EXISTS customer_profiles SET SCHEMA platform;
ALTER TABLE IF EXISTS archetype_definitions SET SCHEMA platform;
ALTER TABLE IF EXISTS dim_archetype_l1 SET SCHEMA platform;
ALTER TABLE IF EXISTS dim_archetype_l2 SET SCHEMA platform;
ALTER TABLE IF EXISTS dim_archetype_l3 SET SCHEMA platform;

-- Move support app tables (operational ticketing data)
ALTER TABLE IF EXISTS tickets SET SCHEMA support_app;
ALTER TABLE IF EXISTS ticket_messages SET SCHEMA support_app;
ALTER TABLE IF EXISTS ticket_notes SET SCHEMA support_app;
ALTER TABLE IF EXISTS ticket_ai_recommendations SET SCHEMA support_app;

-- Move shared tables (multi-tenancy)
ALTER TABLE IF EXISTS tenants SET SCHEMA shared;

-- Create database roles for access control
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'quimbi_platform_role') THEN
        CREATE ROLE quimbi_platform_role;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'quimbi_support_role') THEN
        CREATE ROLE quimbi_support_role;
    END IF;
END
$$;

-- Grant permissions to platform role
GRANT USAGE ON SCHEMA platform TO quimbi_platform_role;
GRANT ALL ON ALL TABLES IN SCHEMA platform TO quimbi_platform_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA platform TO quimbi_platform_role;

-- Platform can READ support data (for analytics)
GRANT USAGE ON SCHEMA support_app TO quimbi_platform_role;
GRANT SELECT ON ALL TABLES IN SCHEMA support_app TO quimbi_platform_role;

-- Platform can use shared schema
GRANT USAGE ON SCHEMA shared TO quimbi_platform_role;
GRANT ALL ON ALL TABLES IN SCHEMA shared TO quimbi_platform_role;

-- Grant permissions to support role
GRANT USAGE ON SCHEMA support_app TO quimbi_support_role;
GRANT ALL ON ALL TABLES IN SCHEMA support_app TO quimbi_support_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA support_app TO quimbi_support_role;

-- Support can READ platform data (for customer intelligence)
GRANT USAGE ON SCHEMA platform TO quimbi_support_role;
GRANT SELECT ON ALL TABLES IN SCHEMA platform TO quimbi_support_role;

-- Support can use shared schema
GRANT USAGE ON SCHEMA shared TO quimbi_support_role;
GRANT ALL ON ALL TABLES IN SCHEMA shared TO quimbi_support_role;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA platform GRANT ALL ON TABLES TO quimbi_platform_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA support_app GRANT ALL ON TABLES TO quimbi_support_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA shared GRANT ALL ON TABLES TO quimbi_platform_role, quimbi_support_role;

-- Verify migration
DO $$
DECLARE
    platform_count INTEGER;
    support_count INTEGER;
    shared_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO platform_count FROM information_schema.tables WHERE table_schema = 'platform';
    SELECT COUNT(*) INTO support_count FROM information_schema.tables WHERE table_schema = 'support_app';
    SELECT COUNT(*) INTO shared_count FROM information_schema.tables WHERE table_schema = 'shared';

    RAISE NOTICE 'Platform schema tables: %', platform_count;
    RAISE NOTICE 'Support app schema tables: %', support_count;
    RAISE NOTICE 'Shared schema tables: %', shared_count;
END
$$;
