# Changelog

All notable changes to the Unified Segmentation E-commerce system will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- SECURITY.md: Comprehensive security documentation for enterprise compliance
- GETTING_STARTED.md: 15-minute onboarding guide for all user types
- CHANGELOG.md: Proper version history tracking
- Documentation folder structure (docs/, operations/, reference/)

### Changed
- Documentation restructure: Reduced from 42 files to 23 organized files
- Improved README.md with clear navigation and purpose

### Removed
- 23 temporary/debug documentation files (test results, status updates, implementation logs)

## [1.2.0] - 2025-11-06

### Added
- Redis authentication for persistent data storage across Railway restarts
- Comprehensive error handling and logging in data loader
- Health check endpoint for data load status verification

### Fixed
- CRITICAL: Redis connection now uses password authentication (QILUmFYIIfifsZnVKSPvejmTemQlrQDh@crossover)
- Data loader successfully loads 27,415 customers and 868 archetypes on Railway startup
- Logging TypeError in star_schema_loader.py (f-string formatting)
- Shopify shop name corrected: lindas-electric-quilters.myshopify.com

### Changed
- Data loader queries `customer_profiles` table with correct column names
- Redis URL configuration in Railway environment variables
- Improved logging verbosity for debugging data loading issues

## [1.1.0] - 2025-11-05

### Added
- Quimbi behavioral segmentation integration (27,415 customers, 868 archetypes)
- Star schema data loader for PostgreSQL to in-memory/Redis caching
- Customer archetype analysis and churn risk scoring
- Behavioral insights in AI-generated support responses

### Fixed
- Hybrid customer lookup system (Shopify + Quimbi) with graceful fallbacks
- Customer authentication flow using Shopify customer ID from Gorgias integrations
- Webhook processing for ticket created vs message created events

## [1.0.0] - 2025-11-04

### Added
- Shopify integration for real-time order data and tracking
- Gorgias webhook integration for AI-generated support responses
- RingCentral voicemail transcript filtering
- API authentication using X-API-Key headers
- PostgreSQL database with customer_profiles table
- Redis caching for performance optimization

### Security
- API key-based authentication for all endpoints
- Admin key for administrative operations
- HTTPS enforcement on all API endpoints
- Database SSL/TLS connections
- Environment variable management for secrets

### Operations
- Railway deployment with PostgreSQL and Redis
- Monitoring strategy and alerting setup
- Incident runbook for on-call support
- Sync troubleshooting procedures

## [0.9.0] - 2025-10-30

### Added
- Initial FastAPI backend setup
- Database schema for customer segmentation
- Basic API endpoints for customer lookup
- Structured logging infrastructure

### Changed
- Migrated from monolithic architecture to microservices

### Fixed
- Multiple router audit issues and endpoint consolidation
- Database connection pooling optimization

---

## Version History Summary

- **v1.2.0** (2025-11-06): Redis authentication fix, full Quimbi data loading operational
- **v1.1.0** (2025-11-05): Quimbi behavioral segmentation integration
- **v1.0.0** (2025-11-04): Shopify + Gorgias integration, production-ready
- **v0.9.0** (2025-10-30): Initial system setup

---

## Migration Notes

### Upgrading to v1.2.0
- Set `REDIS_URL` environment variable with password authentication
- Restart Railway service to trigger data loading
- Verify data loaded: Check `/api/mcp/archetypes/top` endpoint

### Upgrading to v1.1.0
- Run database migration: `alembic upgrade head`
- Load customer_profiles data from Quimbi CSV
- Verify 27,415 customers loaded in PostgreSQL

### Upgrading to v1.0.0
- Set Shopify credentials: `SHOPIFY_SHOP_NAME`, `SHOPIFY_ACCESS_TOKEN`
- Configure Gorgias webhook URL in Gorgias dashboard
- Set `ADMIN_KEY` environment variable

---

## Deprecation Notices

### Deprecated in v1.2.0
- Date-stamped documentation files (use CHANGELOG.md instead)
- In-memory-only data storage (use Redis for persistence)

### Removed in v1.2.0
- `CURRENT_STATUS.md` (superseded by FINAL_SYSTEM_REPORT.md)
- `SYSTEM_STATUS_2025-11-06.md` (use CHANGELOG.md)
- 21 other temporary/debug documentation files

---

## Breaking Changes

### v1.2.0
- None (backward compatible)

### v1.1.0
- Database schema change: Added `customer_profiles` table
- Requires PostgreSQL migration

### v1.0.0
- API authentication now required for all endpoints
- Environment variables required: `SHOPIFY_SHOP_NAME`, `SHOPIFY_ACCESS_TOKEN`, `ADMIN_KEY`

---

## Contributing

When adding entries to this changelog:
- Use "Added" for new features
- Use "Changed" for changes to existing functionality
- Use "Deprecated" for soon-to-be-removed features
- Use "Removed" for removed features
- Use "Fixed" for bug fixes
- Use "Security" for security-related changes

Keep entries concise and user-focused. Link to GitHub issues or PRs where relevant.

---

**Last Updated:** 2025-11-06
