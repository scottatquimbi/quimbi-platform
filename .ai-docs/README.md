# AI-Accessible Documentation Repository

**Purpose**: Structured documentation for AI systems to understand and work with the Unified Behavioral Segmentation System.

**Last Updated**: October 13, 2025

---

## Directory Structure

### 📐 architecture/
Design documents and architectural decisions.

- **[AFFORDANCE_BASED_TAXONOMY.md](architecture/AFFORDANCE_BASED_TAXONOMY.md)** - Core design philosophy replacing hardcoded axes with discovered affordances
- **[WHY_CURRENT_SYSTEM_FAILS.md](architecture/WHY_CURRENT_SYSTEM_FAILS.md)** - Original problem analysis (now fixed)
- **[FUZZY_MEMBERSHIP_EXPLAINED.md](architecture/FUZZY_MEMBERSHIP_EXPLAINED.md)** - Mathematical foundation for fuzzy segmentation
- **[ENGAGEMENT_GRAPH_PROPOSAL.md](architecture/ENGAGEMENT_GRAPH_PROPOSAL.md)** - Future enhancement proposal

### 🔌 api/
API documentation and deployment guides.

- **[API_DOCUMENTATION.md](api/API_DOCUMENTATION.md)** - Complete REST API reference (v2.0.0)
- **[RAILWAY_SETUP.md](api/RAILWAY_SETUP.md)** - Railway deployment configuration
- **[DEPLOYMENT_GUIDE.md](api/DEPLOYMENT_GUIDE.md)** - Comprehensive deployment instructions

### 📚 guides/
User and developer guides.

- **[TESTING_GUIDE.md](guides/TESTING_GUIDE.md)** - How to test the system with proper data
- **[MIGRATION_GUIDE.md](guides/MIGRATION_GUIDE.md)** - Migrating from hardcoded to affordance-based system
- **[TEMPORAL_JOURNEY_TRACKING.md](guides/TEMPORAL_JOURNEY_TRACKING.md)** - Tracking player journeys over time

### 🔧 implementation/
Technical implementation details and progress tracking.

- **[DEVELOPMENT_SUMMARY.md](implementation/DEVELOPMENT_SUMMARY.md)** - Initial affordance discovery implementation
- **[SEGMENT_DISCOVERY_SUMMARY.md](implementation/SEGMENT_DISCOVERY_SUMMARY.md)** - Segment discovery within affordances implementation
- **[PACKAGE_SUMMARY.md](implementation/PACKAGE_SUMMARY.md)** - System overview and deployment package details
- **[NEXT_STEPS_SUMMARY.md](implementation/NEXT_STEPS_SUMMARY.md)** - Original problem statement (historical)

### 🔍 analysis/
Data analysis and compatibility studies.

- **[RAILWAY_TEST_DATA_ANALYSIS.md](analysis/RAILWAY_TEST_DATA_ANALYSIS.md)** - Critical analysis of test data compatibility

---

## Quick Navigation by Use Case

### For Understanding the System
1. Start with [PACKAGE_SUMMARY.md](implementation/PACKAGE_SUMMARY.md) - Overview
2. Read [AFFORDANCE_BASED_TAXONOMY.md](architecture/AFFORDANCE_BASED_TAXONOMY.md) - Core concept
3. Review [API_DOCUMENTATION.md](api/API_DOCUMENTATION.md) - API reference

### For Implementation Work
1. Read [DEVELOPMENT_SUMMARY.md](implementation/DEVELOPMENT_SUMMARY.md) - What was built
2. Read [SEGMENT_DISCOVERY_SUMMARY.md](implementation/SEGMENT_DISCOVERY_SUMMARY.md) - Latest features
3. Check [TESTING_GUIDE.md](guides/TESTING_GUIDE.md) - How to test

### For Deployment
1. Read [DEPLOYMENT_GUIDE.md](api/DEPLOYMENT_GUIDE.md) - General deployment
2. Read [RAILWAY_SETUP.md](api/RAILWAY_SETUP.md) - Railway-specific setup
3. Read [MIGRATION_GUIDE.md](guides/MIGRATION_GUIDE.md) - Migration strategy

### For Data Requirements
1. ⚠️ **CRITICAL**: Read [RAILWAY_TEST_DATA_ANALYSIS.md](analysis/RAILWAY_TEST_DATA_ANALYSIS.md)
2. Check [TESTING_GUIDE.md](guides/TESTING_GUIDE.md) - Data format requirements
3. Review [API_DOCUMENTATION.md](api/API_DOCUMENTATION.md) - Event ingestion examples

---

## System Status

✅ **Core Implementation**: Complete
- Affordance discovery engine
- Segment discovery engine
- Individual player profiling
- Complete REST API

⚠️ **Test Data**: Incompatible
- Existing Railway data uses aggregated events
- Requires granular event types for affordance discovery
- See [RAILWAY_TEST_DATA_ANALYSIS.md](analysis/RAILWAY_TEST_DATA_ANALYSIS.md)

📋 **Future Enhancements**: Documented
- Engagement graph discovery
- Temporal journey tracking
- Automatic recalibration

---

## Key Concepts

**Affordance**: A discoverable product feature that players can engage with (progression, combat, economy, social, etc.)

**Segment**: A cluster of players with similar engagement levels within an affordance (high/medium/low)

**Fuzzy Membership**: Players belong to ALL segments with varying strengths (0.0-1.0), not binary classification

**Granular Events**: Specific event types (mission_start, combat_encounter) required for affordance discovery

**Aggregated Events**: Summary statistics (daily_activity) that cannot be used for affordance discovery

---

## Critical Requirements

### ✅ Works With Affordance Discovery
```json
{
  "events": [
    {"event_type": "mission_start", "event_timestamp": "...", "event_data": {...}},
    {"event_type": "combat_encounter", "event_timestamp": "...", "event_data": {...}},
    {"event_type": "item_crafted", "event_timestamp": "...", "event_data": {...}},
    {"event_type": "guild_joined", "event_timestamp": "...", "event_data": {...}}
  ]
}
```

### ❌ Does NOT Work With Affordance Discovery
```json
{
  "events": [
    {"event_type": "daily_activity", "event_timestamp": "...", "event_data": {...}},
    {"event_type": "daily_activity", "event_timestamp": "...", "event_data": {...}},
    {"event_type": "daily_activity", "event_timestamp": "...", "event_data": {...}}
  ]
}
```

**Reason**: Affordance discovery clusters events by co-occurrence patterns. All events having the same type provides no diversity to cluster.

---

## Workflow

### Initial Setup (One-Time Per Game)
```
1. Ingest events with granular event types
   ↓
2. POST /api/v1/affordances/discover
   → Discovers affordances (progression, combat, etc.)
   ↓
3. POST /api/v1/affordances/segments/discover
   → Creates segments within affordances (high/medium/low)
```

### Per-Player Analysis (Ongoing)
```
1. POST /api/v1/affordances/player/profile
   → Get player's affordance engagement (58% progression, 29% combat)
   ↓
2. POST /api/v1/affordances/segments/player/memberships
   → Get player's segment memberships (progression_high: 0.92)
   ↓
3. Take action based on profile
   → Recommend content, send offers, prevent churn
```

---

## File Sizes and Complexity

| File | Lines | Complexity | Purpose |
|------|-------|-----------|---------|
| AFFORDANCE_BASED_TAXONOMY.md | 400+ | High | Core design |
| API_DOCUMENTATION.md | 1100+ | High | Complete API reference |
| DEVELOPMENT_SUMMARY.md | 600+ | Medium | Implementation details |
| SEGMENT_DISCOVERY_SUMMARY.md | 600+ | Medium | Segment implementation |
| RAILWAY_TEST_DATA_ANALYSIS.md | 1100+ | High | Critical data analysis |
| MIGRATION_GUIDE.md | 600+ | Medium | Migration instructions |
| TESTING_GUIDE.md | 500+ | Medium | Testing instructions |
| PACKAGE_SUMMARY.md | 600+ | Medium | System overview |

---

## Version History

### v2.0.0 (October 13, 2025)
- ✅ Affordance discovery implementation
- ✅ Segment discovery implementation
- ✅ Complete API with 6 new endpoints
- ✅ Documentation organized into .ai-docs/
- ⚠️ Test data compatibility issue identified

### v1.0.0 (October 9, 2025)
- Initial deployment package
- Hardcoded axis system (deprecated)
- Core engines implemented
- Railway deployment ready

---

## For AI Systems

This documentation repository is structured for easy AI consumption:

1. **Hierarchical organization** - Documents grouped by purpose
2. **Clear file names** - Purpose evident from name
3. **Cross-references** - Markdown links between related docs
4. **Status indicators** - ✅ ⚠️ ❌ for quick assessment
5. **Code examples** - Inline examples throughout
6. **Mathematical notation** - LaTeX and code format

**Recommended approach for AI systems**:
1. Read this README.md first for structure
2. Navigate to relevant category directory
3. Read primary document for that category
4. Follow cross-references for deeper understanding

---

## Contact and Support

**GitHub Repository**: (Add your repo URL)
**Issues**: Report at GitHub Issues
**Documentation Updates**: Submit PR to .ai-docs/

---

**Last Updated**: October 13, 2025
**Documentation Version**: 2.0.0
**System Status**: ✅ Core Implementation Complete
