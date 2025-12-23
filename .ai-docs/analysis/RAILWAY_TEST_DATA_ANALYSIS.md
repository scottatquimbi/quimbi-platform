# Railway Test Data Analysis - Affordance Discovery Compatibility

**Date**: October 13, 2025
**Question**: Can the existing Railway DB test data be used to test affordance discovery?

---

## TL;DR

**❌ NO** - The current test data **CANNOT** be used for affordance discovery.

**Why**: All events have `event_type = "daily_activity"` (aggregated), but affordance discovery requires **granular event types** like "mission_start", "combat_encounter", "item_crafted".

**Solution**: Need to either:
1. Generate new test data with granular event types, OR
2. Modify the test data ingestion to split daily_activity into granular events

---

## Current Test Data Structure

### What's In Railway DB

**Game ID**: `stress_test_001`
**Players**: ~1,000 players (based on stress test naming)
**Events**: ~135,070 events (135 events per player avg)

**Event Structure**:
```json
{
  "event_type": "daily_activity",  // ❌ PROBLEM: All events have same type
  "event_timestamp": "2025-10-13T12:00:00Z",
  "event_data": {
    "session_count": 5,
    "total_session_duration_minutes": 120,
    "avg_session_duration_minutes": 24,
    "purchase_count": 2,
    "total_purchase_amount": 49.99,
    "is_weekend": false,
    "progression_level": 15,
    "currency_spend_rate": 1.5,
    "progression_speed": 0.8,
    "items_crafted": 12,
    "content_discovered": 0.45
  }
}
```

---

## Why This Won't Work

### Affordance Discovery Requirements

Affordance discovery works by:
1. **Analyzing event co-occurrence** - Which events happen together?
2. **Clustering events** - Group similar events into affordances
3. **Naming affordances** - Based on event types

**Example Expected Input**:
```json
[
  {"event_type": "mission_start", ...},
  {"event_type": "mission_complete", ...},
  {"event_type": "combat_encounter", ...},
  {"event_type": "enemy_killed", ...},
  {"event_type": "item_crafted", ...},
  {"event_type": "resource_gathered", ...}
]
```

**Affordance Discovery Output**:
```json
{
  "progression_affordance": ["mission_start", "mission_complete", "level_up"],
  "combat_affordance": ["combat_encounter", "enemy_killed", "ability_used"],
  "economy_affordance": ["item_crafted", "resource_gathered", "trade"]
}
```

### Current Test Data Problem

**All events have the same `event_type`**:
```sql
SELECT DISTINCT event_type FROM player_behavior_events;
-- Result: "daily_activity"
```

**What Affordance Discovery Would See**:
- Event types: `["daily_activity"]` (only 1 unique type)
- Co-occurrence matrix: All 1.0 (every event "co-occurs" with itself)
- Clustering result: **Cannot cluster 1 event type**

**Error You'd Get**:
```
No affordances discovered - insufficient event type diversity.
Need at least 2 distinct event types.
```

---

## What The Test Data Contains

### The `event_data` Field

The test data **does contain** diverse behavioral metrics:
```json
{
  "session_count": 5,              // Engagement metric
  "purchase_count": 2,              // Monetization metric
  "items_crafted": 12,              // Economy metric
  "progression_level": 15,          // Progression metric
  "content_discovered": 0.45        // Exploration metric
}
```

**BUT**: These are in `event_data` as **aggregated statistics**, not as distinct `event_type` values.

---

## Solutions

### Option 1: Generate New Test Data (Recommended)

Create test data with granular event types:

```python
import random
from datetime import datetime, timedelta

event_types = [
    # Progression
    "mission_start", "mission_complete", "level_up", "quest_accepted",

    # Combat
    "combat_encounter", "enemy_killed", "ability_used", "boss_defeated",

    # Economy
    "item_crafted", "resource_gathered", "shop_visit", "trade_complete",

    # Social
    "guild_joined", "party_formed", "chat_sent", "friend_added",

    # Exploration
    "area_discovered", "collectible_found", "map_revealed"
]

def generate_player_events(player_id, num_events=135):
    events = []
    base_time = datetime.now() - timedelta(days=90)

    # Each player has behavioral preferences
    player_profile = random.choice([
        {"progression": 0.6, "combat": 0.3, "economy": 0.1},  # Story-focused
        {"combat": 0.7, "progression": 0.2, "economy": 0.1},  # Combat-focused
        {"economy": 0.5, "progression": 0.3, "combat": 0.2},  # Crafter
    ])

    for i in range(num_events):
        # Weight event selection by player profile
        event_type = weighted_random_choice(event_types, player_profile)

        events.append({
            "event_type": event_type,
            "event_timestamp": base_time + timedelta(hours=i*2),
            "event_data": {"session_id": f"session_{i//10}"}
        })

    return events

# Generate for 1000 players
for player_id in range(1000):
    events = generate_player_events(f"test_player_{player_id}")
    ingest_events(f"test_player_{player_id}", "affordance_test_game", events)
```

**Result**:
- 15-20 unique event types
- Diverse player behavior patterns
- Ready for affordance discovery

---

### Option 2: Transform Existing Data

Extract event types from `event_data` fields:

```python
async def transform_daily_activity_to_granular(game_id="stress_test_001"):
    """
    Transform existing daily_activity events into granular events.
    """

    # Load all daily_activity events
    events = await fetch_events(game_id, event_type="daily_activity")

    granular_events = []

    for event in events:
        data = event.event_data
        timestamp = event.event_timestamp

        # Extract multiple event types from aggregated data
        if data.get("session_count", 0) > 0:
            granular_events.append({
                "event_type": "session_start",
                "event_timestamp": timestamp,
                "event_data": {"session_duration": data.get("avg_session_duration_minutes")}
            })

        if data.get("purchase_count", 0) > 0:
            granular_events.append({
                "event_type": "purchase_complete",
                "event_timestamp": timestamp,
                "event_data": {"amount": data.get("total_purchase_amount")}
            })

        if data.get("items_crafted", 0) > 0:
            granular_events.append({
                "event_type": "item_crafted",
                "event_timestamp": timestamp,
                "event_data": {"count": data.get("items_crafted")}
            })

        if data.get("progression_level", 0) > 0:
            granular_events.append({
                "event_type": "level_gained",
                "event_timestamp": timestamp,
                "event_data": {"level": data.get("progression_level")}
            })

        if data.get("content_discovered", 0) > 0:
            granular_events.append({
                "event_type": "content_discovered",
                "event_timestamp": timestamp,
                "event_data": {"percentage": data.get("content_discovered")}
            })

    # Ingest transformed events as new game
    await ingest_events(granular_events, game_id="stress_test_001_granular")
```

**Result**:
- 5-7 unique event types
- Uses existing data
- Minimal additional data generation

---

### Option 3: Use Old System Instead

If you just want to test the **existing functionality**, use the old hardcoded axis system:

```bash
# This WILL work with current test data
curl -X POST http://localhost:8000/api/v1/segmentation/taxonomy/calibrate \
  -d '{"game_id": "stress_test_001"}'

# This uses aggregated metrics, not event types
# Returns: monetization, engagement, temporal, social axes
```

**BUT**: This uses the old (deprecated) hardcoded approach, not the new affordance discovery.

---

## Recommended Testing Strategy

### Phase 1: Quick Test (Old System)
```bash
# Test with existing data using old system
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/segmentation/taxonomy/calibrate \
  -d '{"game_id": "stress_test_001"}'

# Verify categorization works
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/segmentation/categorize \
  -d '{"player_id": "player_123", "game_id": "stress_test_001"}'
```

**Purpose**: Verify backend connectivity, database schema, basic functionality

---

### Phase 2: Generate Granular Test Data
```bash
# Generate new test data with granular events
python scripts/generate_granular_test_data.py \
  --game_id "affordance_test_game" \
  --num_players 500 \
  --events_per_player 100 \
  --event_types 15

# Ingest to Railway
python scripts/ingest_to_railway.py \
  --game_id "affordance_test_game" \
  --data_file test_data_granular.json
```

**Purpose**: Create proper test data for affordance discovery

---

### Phase 3: Test Affordance Discovery
```bash
# Discover affordances
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/affordances/discover \
  -d '{"game_id": "affordance_test_game", "min_population": 100}'

# Check discovered affordances
curl https://unified-segmentation-staging.up.railway.app/api/v1/affordances/affordance_test_game

# Get player profile
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/affordances/player/profile \
  -d '{"player_id": "test_player_001", "game_id": "affordance_test_game"}'

# Discover segments
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/affordances/segments/discover \
  -d '{"game_id": "affordance_test_game"}'

# Get player segment memberships
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/affordances/segments/player/memberships \
  -d '{"player_id": "test_player_001", "game_id": "affordance_test_game"}'
```

**Purpose**: Full test of new affordance-based system

---

## Summary Table

| Test Scenario | Existing Test Data | New Granular Data |
|---------------|-------------------|-------------------|
| **Old System (hardcoded axes)** | ✅ Works | ✅ Works |
| **Affordance Discovery** | ❌ Won't work | ✅ Works |
| **Segment Discovery** | ❌ Won't work | ✅ Works |
| **Player Profiling (affordance)** | ❌ Won't work | ✅ Works |
| **Data Ingestion Test** | ✅ Works | ✅ Works |
| **Database Schema Test** | ✅ Works | ✅ Works |

---

## Conclusion

**Can you test affordance discovery with existing Railway data?**
**NO** - You need granular event types.

**What can you test with existing data?**
- ✅ Data ingestion endpoints
- ✅ Database connectivity
- ✅ Old taxonomy calibration (hardcoded axes)
- ✅ Old categorization system
- ✅ Anomaly detection (works with old or new system)

**What do you need for full testing?**
- Generate new test data with 10-20 distinct event types
- Each player should have 50-200 events
- Events should show behavioral diversity (some players progression-focused, others combat-focused, etc.)

**Quick Win**:
Use Option 2 (transform existing data) to create a "stress_test_001_granular" game_id with transformed events. This is faster than generating entirely new data and uses the existing infrastructure.

---

## Next Steps

1. **Immediate**: Test old system with existing data to verify Railway deployment works
2. **Short-term**: Transform existing data to granular events (Option 2)
3. **Long-term**: Generate proper test dataset with realistic game events (Option 1)

---

**For More Information**:
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - How to generate and test with proper data
- [DEVELOPMENT_SUMMARY.md](DEVELOPMENT_SUMMARY.md) - Why affordance discovery needs granular events
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Migrating from aggregated to granular events
