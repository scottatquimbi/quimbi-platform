# Migration Guide: From Hardcoded Axes to Affordance Discovery

**Version**: 1.0
**Date**: October 13, 2025

This guide helps you transition from the old hardcoded axis system to the new affordance-based discovery system.

---

## Overview

### What Changed

| Aspect | Old System (v1.x) | New System (v2.0) |
|--------|------------------|-------------------|
| **Axis Discovery** | Hardcoded 4 universal axes | Discovered from events |
| **Individual Explanation** | ❌ Generic labels | ✅ Actual behavior % |
| **API Endpoints** | `/taxonomy/calibrate` | `/affordances/discover` |
| **Event Requirements** | Daily aggregates | Granular event types |
| **Output** | "engagement: hardcore" | "87% progression, 12% combat" |

### Why Migrate?

1. **Individual Explanability**: Know WHAT players do, not just statistical labels
2. **No Hardcoded Assumptions**: Works for any game, any genre
3. **Actionable Insights**: "Player hasn't discovered crafting" → surface tutorial
4. **Better Personalization**: Recommend based on actual behavior, not proxies

---

## Migration Paths

### Path 1: New Games (Recommended)
Start fresh with affordance discovery from day one.

**Steps**:
1. Ingest events with granular `event_type` values
2. Use `/api/v1/affordances/discover` instead of `/api/v1/segmentation/taxonomy/calibrate`
3. Get player profiles with `/api/v1/affordances/player/profile`

**Benefits**: Clean start, full benefits immediately

---

### Path 2: Existing Games (Gradual Migration)
Run both systems in parallel, gradually transition.

**Steps**:
1. Update event ingestion to include granular event types (keep old format too)
2. Run affordance discovery on new data
3. Compare outputs side-by-side
4. Transition consumers to new endpoints when confident
5. Deprecate old endpoints

**Benefits**: Risk-free, can validate before switching

---

### Path 3: Hybrid (Temporary)
Use old system for existing analytics, new system for new features.

**Steps**:
1. Keep old system running for backward compatibility
2. Use new system for new features (recommendations, interventions)
3. Eventually deprecate old system once all consumers migrated

**Benefits**: Fastest time-to-value for new features

---

## Step-by-Step Migration

### Step 1: Update Data Ingestion

#### Before (Daily Aggregates)
```json
{
  "player_id": "player_123",
  "game_id": "my_game",
  "events": [
    {
      "event_type": "daily_activity",
      "event_timestamp": "2025-10-13T00:00:00Z",
      "event_data": {
        "session_count": 5,
        "avg_session_duration": 24,
        "purchase_count": 2
      }
    }
  ]
}
```

**Problem**: Loses event-level granularity. Can't discover affordances.

#### After (Granular Events)
```json
{
  "player_id": "player_123",
  "game_id": "my_game",
  "events": [
    {
      "event_type": "mission_start",
      "event_timestamp": "2025-10-13T10:00:00Z",
      "event_data": {"mission_id": "prologue"}
    },
    {
      "event_type": "combat_encounter",
      "event_timestamp": "2025-10-13T10:15:00Z",
      "event_data": {"enemy_type": "basic"}
    },
    {
      "event_type": "item_crafted",
      "event_timestamp": "2025-10-13T10:30:00Z",
      "event_data": {"item": "sword"}
    }
  ]
}
```

**Benefit**: Preserves what players actually DO. Enables affordance discovery.

**Action Items**:
1. Update your event collection code to send granular event types
2. Define event taxonomy for your game (mission_start, combat_encounter, etc.)
3. Continue sending old format for backward compatibility (optional)

---

### Step 2: Run Affordance Discovery

#### Old Endpoint (Deprecated)
```bash
curl -X POST http://localhost:8000/api/v1/segmentation/taxonomy/calibrate \
  -H "Content-Type: application/json" \
  -d '{"game_id": "my_game"}'
```

**Returns**: Hardcoded axes (monetization, engagement, temporal, social)

#### New Endpoint (Recommended)
```bash
curl -X POST http://localhost:8000/api/v1/affordances/discover \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": "my_game",
    "min_population": 100
  }'
```

**Returns**: Discovered affordances from YOUR game's events

**Action Items**:
1. Run affordance discovery on your game
2. Verify affordance names make sense for your product
3. Store affordance names for future reference

---

### Step 3: Update Player Profile Retrieval

#### Old Endpoint (Deprecated)
```bash
curl -X POST http://localhost:8000/api/v1/segmentation/categorize \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "player_123",
    "game_id": "my_game"
  }'
```

**Returns**:
```json
{
  "primary_segments": {
    "engagement": "hardcore",
    "monetization": "whale"
  }
}
```

**Problem**: What does "hardcore" mean? What do they DO?

#### New Endpoint (Recommended)
```bash
curl -X POST http://localhost:8000/api/v1/affordances/player/profile \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "player_123",
    "game_id": "my_game"
  }'
```

**Returns**:
```json
{
  "affordance_engagement": {
    "progression": {"event_percentage": 0.58},
    "combat": {"event_percentage": 0.29},
    "economy": {"event_percentage": 0.12}
  },
  "interpretation": "Story-driven player focused on progression..."
}
```

**Benefit**: Actionable! You know exactly what they do.

**Action Items**:
1. Update your analytics dashboards to use new endpoint
2. Update recommendation engines to use affordance engagement
3. Update A/B testing segmentation to use affordance profiles

---

### Step 4: Update Downstream Consumers

#### Recommendation Engine

**Before**:
```python
if player.primary_segments["engagement"] == "hardcore":
    recommend_difficult_content()
```

**Problem**: "hardcore" is vague. Hardcore progression? Hardcore combat?

**After**:
```python
if player.affordance_engagement["combat"]["event_percentage"] > 0.5:
    recommend_difficult_combat()
elif player.affordance_engagement["progression"]["event_percentage"] > 0.5:
    recommend_complex_story_missions()
```

**Benefit**: Precise recommendations based on actual behavior.

#### Churn Prediction

**Before**:
```python
if player.segment_drift["engagement"] < -0.3:
    churn_risk = HIGH
```

**Problem**: Which aspect of engagement dropped?

**After**:
```python
# Check which affordance dropped
for affordance, metrics in player.affordance_engagement.items():
    if metrics["velocity"] < historical_avg * 0.5:
        alert(f"Dropping engagement in {affordance}")
        send_targeted_retention(affordance)
```

**Benefit**: Targeted interventions based on specific behavior changes.

---

## API Mapping

### Complete Endpoint Migration Table

| Old Endpoint | Status | New Endpoint | Notes |
|-------------|--------|--------------|-------|
| `POST /api/v1/segmentation/taxonomy/calibrate` | ⚠️ Deprecated | `POST /api/v1/affordances/discover` | Use affordance discovery |
| `GET /api/v1/segmentation/taxonomy/{game_id}` | ⚠️ Deprecated | `GET /api/v1/affordances/{game_id}` | Get discovered affordances |
| `POST /api/v1/segmentation/categorize` | ⚙️ Still works | `POST /api/v1/affordances/player/profile` | Use affordance profile |
| `POST /api/v1/ingestion/events` | ✅ No change | `POST /api/v1/ingestion/events` | Update event types to be granular |
| `POST /api/v1/segmentation/anomalies/detect` | ✅ No change | Same | Works with both systems |
| `GET /api/v1/segmentation/journey/{player_id}` | ✅ No change | Same | Works with both systems |

**Legend**:
- ⚠️ Deprecated - Still works, but migrate away
- ⚙️ Still works - Old endpoint functional, new one preferred
- ✅ No change - Endpoint unchanged

---

## Data Format Changes

### Event Schema

#### Old Format (Aggregated)
```python
{
    "event_type": "daily_activity",  # Generic
    "event_data": {
        "session_count": 5,           # Summary stat
        "avg_session_duration": 24,   # Summary stat
        "purchase_count": 2            # Summary stat
    }
}
```

#### New Format (Granular)
```python
{
    "event_type": "mission_start",    # Specific action
    "event_data": {
        "mission_id": "prologue",     # Context
        "difficulty": "normal",        # Context
        "player_level": 5              # Context
    }
}
```

**Key Difference**: New format captures WHAT happened, not aggregated statistics.

---

## Testing Migration

### Validation Checklist

**Before Going Live**:
- [ ] Granular events ingesting successfully
- [ ] Affordance discovery returns sensible affordance names
- [ ] Player affordance profiles show expected engagement patterns
- [ ] Downstream consumers updated to use new API
- [ ] Analytics dashboards updated
- [ ] Monitoring/alerts updated

**Validation Queries**:

1. **Check Event Diversity**:
```sql
SELECT event_type, COUNT(*) as count
FROM player_behavior_events
WHERE game_id = 'my_game'
GROUP BY event_type
ORDER BY count DESC;
```
**Expected**: 10+ distinct event types (not just "daily_activity")

2. **Check Affordance Discovery**:
```bash
curl http://localhost:8000/api/v1/affordances/my_game
```
**Expected**: 3-7 affordances with meaningful names

3. **Compare Old vs New**:
```bash
# Old system
curl -X POST /api/v1/segmentation/categorize \
  -d '{"player_id": "test_player", "game_id": "my_game"}'

# New system
curl -X POST /api/v1/affordances/player/profile \
  -d '{"player_id": "test_player", "game_id": "my_game"}'
```
**Expected**: New system provides more specific insights

---

## Rollback Plan

If you need to rollback:

1. **Old endpoints still work** - No breaking changes
2. **Database is backward compatible** - New affordances stored alongside old axes
3. **Can switch consumers back** to old endpoints anytime

**To Rollback**:
```bash
# Just point your code back to old endpoints
POST /api/v1/segmentation/taxonomy/calibrate  # Instead of affordances/discover
POST /api/v1/segmentation/categorize          # Instead of affordances/player/profile
```

No data loss, no schema changes needed.

---

## Common Migration Issues

### Issue 1: "No affordances discovered"

**Symptom**: Affordance discovery returns empty or insufficient data

**Causes**:
- Not enough players (need 100+ for discovery)
- All events have same event_type ("daily_activity")
- Events too sparse (need 10+ events per player)

**Fix**:
1. Verify event diversity: `SELECT DISTINCT event_type FROM player_behavior_events`
2. Lower `min_population` parameter temporarily for testing
3. Ingest more granular events

---

### Issue 2: "Affordance names don't make sense"

**Symptom**: Affordances named "affordance_3_events" instead of "progression"

**Cause**: Event types don't contain recognizable keywords

**Fix**:
1. Update event naming to include keywords (mission, combat, craft, social, etc.)
2. Customize affordance naming in `affordance_discovery_engine.py:_generate_affordance_name()`
3. Manually rename affordances in database if needed

---

### Issue 3: "Player profiles show 0% engagement everywhere"

**Symptom**: All affordance engagement percentages are 0.0

**Cause**: Player's events don't match discovered affordances

**Fix**:
1. Check player has events: `SELECT COUNT(*) FROM player_behavior_events WHERE player_id = '...'`
2. Check event types match affordances: `SELECT event_type FROM player_behavior_events WHERE player_id = '...'`
3. Re-run affordance discovery to include player's event types

---

## Timeline Recommendations

### Week 1: Preparation
- Update event collection to include granular event types
- Run parallel ingestion (old + new formats)
- Define event taxonomy for your game

### Week 2: Testing
- Run affordance discovery on test environment
- Validate affordance names make sense
- Test player profile endpoint with sample players

### Week 3: Parallel Run
- Deploy to production but don't switch consumers yet
- Run both systems in parallel
- Compare outputs, gather feedback

### Week 4: Migration
- Update one consumer at a time (start with internal dashboards)
- Monitor for issues
- Gradually migrate all consumers

### Week 5+: Optimization
- Tune clustering parameters based on learnings
- Deprecate old endpoints after full migration
- Build new features on top of affordance profiles

---

## Support & Questions

- **Documentation**: See [DEVELOPMENT_SUMMARY.md](DEVELOPMENT_SUMMARY.md) for technical details
- **Testing Guide**: See [TESTING_GUIDE.md](TESTING_GUIDE.md) for step-by-step testing
- **API Reference**: See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete API docs

---

## Success Metrics

How to know migration was successful:

✅ **Technical Success**:
- All consumers using new API endpoints
- Event diversity: 10+ event types per game
- Affordance discovery runs successfully
- Player profiles show meaningful engagement percentages

✅ **Business Success**:
- Recommendation CTR increases (more relevant suggestions)
- Churn intervention success rate improves (targeted actions)
- Product insights actionable (know what players DO)
- Team adoption (analytics & product using affordance profiles)

---

## Conclusion

The migration from hardcoded axes to affordance discovery is **low-risk** (backward compatible) with **high-reward** (individual explainability).

**Key Takeaways**:
1. Update event ingestion to be granular (most important step)
2. Use new affordance endpoints for new features
3. Migrate existing consumers gradually
4. Old system still works as fallback

**Next Steps**:
1. Read [TESTING_GUIDE.md](TESTING_GUIDE.md)
2. Update your event collection code
3. Run affordance discovery on test data
4. Validate affordances make sense
5. Start migration!
