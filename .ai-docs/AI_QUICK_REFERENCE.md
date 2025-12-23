# AI Quick Reference Guide

**Purpose**: Fast lookup for common AI assistant tasks when working with this system.

---

## 🚨 Read This First

⚠️ **CRITICAL DATA REQUIREMENT**: This system requires **granular event types** (mission_start, combat_encounter, item_crafted) NOT aggregated events (daily_activity).

📖 **Essential Reading**: [analysis/RAILWAY_TEST_DATA_ANALYSIS.md](analysis/RAILWAY_TEST_DATA_ANALYSIS.md)

---

## Common AI Tasks

### Task 1: "Review the segmentation system"

**Files to read**:
1. [implementation/PACKAGE_SUMMARY.md](implementation/PACKAGE_SUMMARY.md) - System overview
2. [architecture/AFFORDANCE_BASED_TAXONOMY.md](architecture/AFFORDANCE_BASED_TAXONOMY.md) - Core design
3. [implementation/DEVELOPMENT_SUMMARY.md](implementation/DEVELOPMENT_SUMMARY.md) - What was built

**Key points to mention**:
- System discovers affordances from events (no hardcoded axes)
- Uses fuzzy membership for nuanced classification
- Requires granular event types for affordance discovery
- Complete with affordance + segment discovery

---

### Task 2: "Help me test the system"

**Files to read**:
1. ⚠️ [analysis/RAILWAY_TEST_DATA_ANALYSIS.md](analysis/RAILWAY_TEST_DATA_ANALYSIS.md) - **READ THIS FIRST**
2. [guides/TESTING_GUIDE.md](guides/TESTING_GUIDE.md) - Testing instructions
3. [api/API_DOCUMENTATION.md](api/API_DOCUMENTATION.md) - API reference

**Key points to check**:
- Does test data have diverse event types? (10-20 distinct types)
- Are events granular (mission_start) or aggregated (daily_activity)?
- If aggregated → System won't work, need to generate new data

**Test workflow**:
```bash
# 1. Check data compatibility
# Look for diverse event_type values in player_behavior_events table

# 2. If data is compatible:
POST /api/v1/affordances/discover {"game_id": "..."}
POST /api/v1/affordances/segments/discover {"game_id": "..."}
POST /api/v1/affordances/player/profile {"player_id": "...", "game_id": "..."}

# 3. If data is NOT compatible:
# See RAILWAY_TEST_DATA_ANALYSIS.md for 3 solution options
```

---

### Task 3: "Deploy the system"

**Files to read**:
1. [api/DEPLOYMENT_GUIDE.md](api/DEPLOYMENT_GUIDE.md) - General deployment
2. [api/RAILWAY_SETUP.md](api/RAILWAY_SETUP.md) - Railway-specific
3. [guides/MIGRATION_GUIDE.md](guides/MIGRATION_GUIDE.md) - Migration strategy

**Quick deploy (Railway)**:
```bash
railway init
railway add  # PostgreSQL
railway up
```

---

### Task 4: "Explain how affordance discovery works"

**Files to read**:
1. [architecture/AFFORDANCE_BASED_TAXONOMY.md](architecture/AFFORDANCE_BASED_TAXONOMY.md) - Design
2. [implementation/DEVELOPMENT_SUMMARY.md](implementation/DEVELOPMENT_SUMMARY.md) - Implementation

**Key explanation points**:
- Builds event co-occurrence matrix (which events happen together?)
- Clusters events using hierarchical clustering
- Names affordances intelligently (progression, combat, economy)
- Each player gets affordance profile (58% progression, 29% combat)

**Code reference**: `backend/core/affordance_discovery_engine.py`

---

### Task 5: "Explain how segment discovery works"

**Files to read**:
1. [implementation/SEGMENT_DISCOVERY_SUMMARY.md](implementation/SEGMENT_DISCOVERY_SUMMARY.md) - Complete guide

**Key explanation points**:
- For each affordance, clusters players by engagement level
- Uses KMeans on [event_percentage, velocity, consistency]
- Creates segments like progression_high, combat_medium, economy_low
- Fuzzy membership: player belongs to ALL segments with varying strengths

**Code reference**: `backend/core/affordance_segmentation_engine.py`

---

### Task 6: "Fix errors in the codebase"

**Files to read**:
1. [implementation/DEVELOPMENT_SUMMARY.md](implementation/DEVELOPMENT_SUMMARY.md) - Previous fixes

**Common issues**:
- Indentation errors → Check try/except blocks, async with statements
- Missing await → All `session.execute()` calls need `await`
- Import errors → Check `main.py` has router registration

**Validation**:
```bash
python3 -m py_compile backend/core/[filename].py
```

---

### Task 7: "Generate test data"

**Files to read**:
1. ⚠️ [analysis/RAILWAY_TEST_DATA_ANALYSIS.md](analysis/RAILWAY_TEST_DATA_ANALYSIS.md) - **Critical**
2. [guides/TESTING_GUIDE.md](guides/TESTING_GUIDE.md) - Data format

**Requirements**:
- 10-20 distinct event types
- 50-200 events per player
- Diverse behavioral patterns (some progression-focused, some combat-focused)

**Example event types**:
```python
event_types = [
    # Progression
    "mission_start", "mission_complete", "level_up", "quest_accepted",

    # Combat
    "combat_encounter", "enemy_killed", "ability_used", "boss_defeated",

    # Economy
    "item_crafted", "resource_gathered", "shop_visit", "trade_complete",

    # Social
    "guild_joined", "party_formed", "chat_sent", "friend_added"
]
```

**Code example**: See [analysis/RAILWAY_TEST_DATA_ANALYSIS.md](analysis/RAILWAY_TEST_DATA_ANALYSIS.md) Line 127-175

---

### Task 8: "Add new API endpoint"

**Files to read**:
1. [api/API_DOCUMENTATION.md](api/API_DOCUMENTATION.md) - Existing endpoints
2. [implementation/SEGMENT_DISCOVERY_SUMMARY.md](implementation/SEGMENT_DISCOVERY_SUMMARY.md) - Recent additions

**Files to modify**:
1. `backend/api/affordance_api.py` - Add endpoint
2. `main.py` - Register router (if new file)
3. `API_DOCUMENTATION.md` - Document endpoint

**Example**:
```python
@router.post("/api/v1/affordances/new_endpoint", response_model=ResponseModel)
async def new_endpoint(request: RequestModel):
    engine = affordance_discovery_engine
    result = await engine.method(...)
    return ResponseModel(...)
```

---

### Task 9: "Explain fuzzy membership"

**Files to read**:
1. [architecture/FUZZY_MEMBERSHIP_EXPLAINED.md](architecture/FUZZY_MEMBERSHIP_EXPLAINED.md)
2. [implementation/SEGMENT_DISCOVERY_SUMMARY.md](implementation/SEGMENT_DISCOVERY_SUMMARY.md)

**Key points**:
- Players belong to ALL segments, not just one
- Membership strength: 0.0 (doesn't belong) to 1.0 (perfect fit)
- Formula: `membership = exp(-distance² / (2σ²))`
- Uses Mahalanobis distance (accounts for correlation and variance)

**Why it matters**:
- Gradual transitions between segments (no hard boundaries)
- Multiple segment memberships allow nuanced recommendations
- Example: Player could be 92% progression_high + 15% progression_medium

---

### Task 10: "Update documentation"

**Files to update**:
1. [api/API_DOCUMENTATION.md](api/API_DOCUMENTATION.md) - If adding endpoints
2. [implementation/DEVELOPMENT_SUMMARY.md](implementation/DEVELOPMENT_SUMMARY.md) - If implementing features
3. [README.md](../README.md) - If changing system status

**Don't forget**:
- Update version numbers (currently 2.0.0)
- Update "Last Updated" dates
- Add to table of contents if needed
- Update metadata.json if adding new files

---

## File Size Reference

| File | Lines | Read Time |
|------|-------|-----------|
| PACKAGE_SUMMARY.md | 600+ | 10 min |
| API_DOCUMENTATION.md | 1100+ | 20 min |
| RAILWAY_TEST_DATA_ANALYSIS.md | 1100+ | 20 min |
| DEVELOPMENT_SUMMARY.md | 600+ | 10 min |
| SEGMENT_DISCOVERY_SUMMARY.md | 600+ | 10 min |
| MIGRATION_GUIDE.md | 600+ | 10 min |
| TESTING_GUIDE.md | 500+ | 8 min |
| AFFORDANCE_BASED_TAXONOMY.md | 400+ | 8 min |

---

## Quick Answers

### Q: Is the system broken?
**A**: No. Core implementation is complete. System discovers affordances and segments from events.

### Q: Can I test with existing Railway data?
**A**: ⚠️ **NO** - Existing data has all events with type "daily_activity". Need granular event types. See [analysis/RAILWAY_TEST_DATA_ANALYSIS.md](analysis/RAILWAY_TEST_DATA_ANALYSIS.md).

### Q: What's the difference between affordance and segment?
**A**:
- **Affordance**: What players CAN do (progression, combat, economy)
- **Segment**: How much they engage (progression_high, progression_low)

### Q: How many event types do I need?
**A**: 10-20 distinct event types for meaningful affordance discovery.

### Q: Does the old hardcoded axis system still work?
**A**: Yes, but deprecated. Old endpoints still functional for backward compatibility.

### Q: What's the main innovation?
**A**: Discovers affordances from actual player behavior instead of assuming hardcoded axes.

### Q: How do I migrate from old to new system?
**A**: See [guides/MIGRATION_GUIDE.md](guides/MIGRATION_GUIDE.md) - 4-phase rollout plan.

### Q: What database tables are used?
**A**:
- `player_behavior_events` - Raw events
- `game_behavioral_taxonomy` - Discovered affordances
- `behavioral_axes` - Affordance details
- `segment_definitions` - Segments within affordances
- `player_segment_memberships` - Player classifications

---

## API Endpoint Quick Reference

### Affordance Discovery
```bash
# Discover affordances
POST /api/v1/affordances/discover
{"game_id": "my_game", "min_population": 100}

# Get affordances
GET /api/v1/affordances/{game_id}

# Player profile
POST /api/v1/affordances/player/profile
{"player_id": "player_123", "game_id": "my_game"}
```

### Segment Discovery
```bash
# Discover segments
POST /api/v1/affordances/segments/discover
{"game_id": "my_game"}

# Get segments
GET /api/v1/affordances/segments/{game_id}

# Player memberships
POST /api/v1/affordances/segments/player/memberships
{"player_id": "player_123", "game_id": "my_game"}
```

---

## Status Indicators

✅ **Complete** - Fully implemented and tested
⚠️ **Warning** - Attention required
❌ **Broken** - Does not work
📋 **Planned** - Not yet implemented
🔧 **In Progress** - Currently being developed

**Current System Status**:
- ✅ Affordance discovery
- ✅ Segment discovery
- ✅ Player profiling
- ✅ API endpoints
- ⚠️ Test data (incompatible)
- 📋 Engagement graph discovery (future)

---

## Math Quick Reference

**Event Co-occurrence**:
```
cooccurrence[i,j] = count(event_i AND event_j in same session) / count(sessions)
```

**Mahalanobis Distance**:
```
distance = sqrt((x - μ)ᵀ Σ⁻¹ (x - μ))
```

**Fuzzy Membership**:
```
membership = exp(-distance² / (2 * σ²))
```

**Variance Explained**:
```
variance_explained = 1 - (Σ residual_variance / Σ total_variance)
```

---

## Common Errors and Solutions

### Error: "No affordances discovered"
**Cause**: Insufficient event type diversity
**Solution**: Check if all events have same event_type. Need 10-20 distinct types.
**Reference**: [analysis/RAILWAY_TEST_DATA_ANALYSIS.md](analysis/RAILWAY_TEST_DATA_ANALYSIS.md)

### Error: IndentationError
**Cause**: Incorrect indentation in async/try blocks
**Solution**: Ensure try blocks are indented under async with statements
**Reference**: [implementation/DEVELOPMENT_SUMMARY.md](implementation/DEVELOPMENT_SUMMARY.md) Line 13-20

### Error: "No segments discovered"
**Cause**: Affordances not discovered yet
**Solution**: Run POST /api/v1/affordances/discover first
**Reference**: [implementation/SEGMENT_DISCOVERY_SUMMARY.md](implementation/SEGMENT_DISCOVERY_SUMMARY.md)

### Error: Missing await keyword
**Cause**: Async database calls without await
**Solution**: Add `await` before `session.execute()` calls
**Reference**: [implementation/DEVELOPMENT_SUMMARY.md](implementation/DEVELOPMENT_SUMMARY.md)

---

**Last Updated**: October 13, 2025
**Version**: 2.0.0
