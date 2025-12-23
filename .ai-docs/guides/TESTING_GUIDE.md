# Testing Guide - Affordance-Based Segmentation

Quick guide to test the newly implemented affordance discovery system.

---

## ⚠️ CRITICAL: Event Type Requirements

**Before testing affordance discovery**, understand this requirement:

### ✅ Good Event Data (Required for Affordance Discovery)
```json
{
  "events": [
    {"event_type": "mission_start", ...},
    {"event_type": "combat_encounter", ...},
    {"event_type": "item_crafted", ...},
    {"event_type": "mission_complete", ...}
  ]
}
```
**Need**: 10-20 distinct event types with diverse distribution across players

### ❌ Bad Event Data (Won't Work)
```json
{
  "events": [
    {"event_type": "daily_activity", ...},
    {"event_type": "daily_activity", ...}
  ]
}
```
**Problem**: All same event type = nothing to cluster = no affordances discovered

**See**: [RAILWAY_TEST_DATA_ANALYSIS.md](RAILWAY_TEST_DATA_ANALYSIS.md) for complete analysis

---

## Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the server
python3 main.py
```

Server will start at: `http://localhost:8000`
Swagger docs at: `http://localhost:8000/docs`

---

## Test 1: Verify Syntax Fixes

```bash
# All these should return without errors
python3 -m py_compile backend/core/adaptive_behavioral_categorization.py
python3 -m py_compile backend/core/affordance_discovery_engine.py
python3 -m py_compile backend/api/affordance_api.py
python3 -m py_compile main.py

echo "✅ All syntax checks passed"
```

---

## Test 2: Health Check

```bash
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2025-10-13T...",
#   "version": "1.0.0",
#   "components": {
#     "api": "healthy",
#     "database": "healthy"
#   }
# }
```

---

## Test 3: Check New API Endpoints in Swagger

1. Open browser to: `http://localhost:8000/docs`
2. Look for new section: **`affordance_discovery`**
3. Should see three endpoints:
   - `POST /api/v1/affordances/discover`
   - `GET /api/v1/affordances/{game_id}`
   - `POST /api/v1/affordances/player/profile`

---

## Test 4: Ingest Sample Events (Granular)

**IMPORTANT**: The new system needs granular event types (not "daily_activity").

```bash
curl -X POST http://localhost:8000/api/v1/ingestion/events \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "test_player_001",
    "game_id": "test_game",
    "events": [
      {
        "event_type": "mission_start",
        "event_timestamp": "2025-10-13T10:00:00Z",
        "event_data": {"mission_name": "prologue"}
      },
      {
        "event_type": "combat_encounter",
        "event_timestamp": "2025-10-13T10:15:00Z",
        "event_data": {"enemy_type": "basic"}
      },
      {
        "event_type": "mission_complete",
        "event_timestamp": "2025-10-13T10:30:00Z",
        "event_data": {"xp_gained": 100}
      },
      {
        "event_type": "item_crafted",
        "event_timestamp": "2025-10-13T10:35:00Z",
        "event_data": {"item": "sword"}
      },
      {
        "event_type": "dialogue_choice",
        "event_timestamp": "2025-10-13T10:40:00Z",
        "event_data": {"choice": "friendly"}
      }
    ]
  }'

# Repeat for 100+ players with varied event types
```

---

## Test 5: Run Affordance Discovery

```bash
curl -X POST http://localhost:8000/api/v1/affordances/discover \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": "test_game",
    "force_recalibration": false,
    "min_population": 10
  }'

# Expected response:
# {
#   "game_id": "test_game",
#   "affordances_discovered": 3,
#   "affordance_names": [
#     "progression_affordance",
#     "combat_affordance",
#     "crafting_affordance"
#   ],
#   "total_variance_explained": 0.75,
#   "confidence_score": 0.75,
#   "timestamp": "2025-10-13T..."
# }
```

**Note**: If you get "Insufficient data", you need to:
1. Ingest more players (100+ recommended)
2. Ensure diverse event_type values
3. Lower min_population in request

---

## Test 6: Get Discovered Affordances

```bash
curl http://localhost:8000/api/v1/affordances/test_game

# Expected response:
# [
#   {
#     "affordance_name": "progression_affordance",
#     "event_types": ["mission_start", "mission_complete", "level_up"],
#     "variance_explained": 0.42,
#     "interpretation": "Widely adopted feature with high engagement"
#   },
#   ...
# ]
```

---

## Test 7: Get Player Affordance Profile

```bash
curl -X POST http://localhost:8000/api/v1/affordances/player/profile \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "test_player_001",
    "game_id": "test_game"
  }'

# Expected response:
# {
#   "player_id": "test_player_001",
#   "game_id": "test_game",
#   "primary_affordances": ["progression_affordance", "combat_affordance"],
#   "affordance_engagement": {
#     "progression_affordance": {
#       "event_count": 287,
#       "event_percentage": 0.58,
#       "velocity": 3.2,
#       "consistency": 0.89
#     },
#     "combat_affordance": {
#       "event_count": 198,
#       "event_percentage": 0.29,
#       "velocity": 2.1,
#       "consistency": 0.76
#     }
#   },
#   "affordances_engaged": 2,
#   "affordances_ignored": 1,
#   "total_events": 682,
#   "confidence": 0.85,
#   "interpretation": "Player heavily engages with progression_affordance (58% of events). Has not discovered 1 affordances - opportunity for recommendations.",
#   "timestamp": "2025-10-13T..."
# }
```

---

## Test 8: Compare Old vs New System

### Old System (Hardcoded Axes)
```bash
# This still uses hardcoded axes
curl -X POST http://localhost:8000/api/v1/segmentation/taxonomy/calibrate \
  -H "Content-Type: application/json" \
  -d '{"game_id": "test_game"}'

# Response will show:
# "universal_axes": ["engagement", "temporal", "monetization", "social"]
# ❌ Problem: Assumes all games have these
```

### New System (Discovered Affordances)
```bash
# This discovers affordances from events
curl -X POST http://localhost:8000/api/v1/affordances/discover \
  -H "Content-Type: application/json" \
  -d '{"game_id": "test_game"}'

# Response will show:
# "affordance_names": ["progression_affordance", "combat_affordance"]
# ✅ Better: Discovers what THIS game actually has
```

---

## Troubleshooting

### "No events found"
**Problem**: Database is empty or event_type is still "daily_activity"
**Solution**: Ingest events with granular event_type values (see Test 4)

### "Insufficient data for affordance discovery"
**Problem**: Not enough players or events
**Solution**:
- Ingest at least 100 players
- Each player should have 10+ events
- Lower `min_population` parameter

### "No affordances found"
**Problem**: All events have same event_type (no variance)
**Solution**: Ingest diverse event types (mission_start, combat_encounter, item_crafted, etc.)

### "Connection refused"
**Problem**: Server not running
**Solution**: `python3 main.py`

### "Table does not exist"
**Problem**: Database migrations not run
**Solution**: `alembic upgrade head`

---

## What Good Output Looks Like

### Diverse Affordances Discovered
```json
{
  "affordances_discovered": 5,
  "affordance_names": [
    "progression_affordance",
    "combat_affordance",
    "economy_affordance",
    "social_affordance",
    "exploration_affordance"
  ],
  "total_variance_explained": 0.87
}
```

### Individual Player Profile
```json
{
  "primary_affordances": ["progression_affordance"],
  "affordance_engagement": {
    "progression_affordance": {
      "event_percentage": 0.72
    },
    "combat_affordance": {
      "event_percentage": 0.15
    },
    "economy_affordance": {
      "event_percentage": 0.08
    }
  },
  "interpretation": "Player heavily engages with progression_affordance (72% of events)"
}
```

This tells you **WHAT the player actually does**, not just "engagement: hardcore".

---

## Running Unit Tests

```bash
# Run existing test suite
pytest tests/test_unified_segmentation_system.py -v

# Note: Some tests may fail because they expect hardcoded axes
# This is expected - those tests need to be updated for affordance-based approach
```

---

## Next Steps After Testing

1. **Verify affordances make sense** for your game's actual mechanics
2. **Tune parameters** in `affordance_discovery_engine.py`:
   - `min_affordance_support` (default: 0.05 = 5% of players)
   - `max_affordances` (default: 10)
   - `min_event_types_per_affordance` (default: 2)

3. **Implement segment discovery** within affordances:
   - Cluster players by affordance engagement level
   - Create "high", "medium", "low" segments per affordance

4. **Update documentation** with your findings

---

## Quick Test Script

Save as `test_affordances.sh`:

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"

echo "1. Health check..."
curl -s $BASE_URL/health | jq .status

echo "\n2. Ingesting sample events..."
curl -s -X POST $BASE_URL/api/v1/ingestion/events \
  -H "Content-Type: application/json" \
  -d @sample_events.json

echo "\n3. Discovering affordances..."
curl -s -X POST $BASE_URL/api/v1/affordances/discover \
  -H "Content-Type: application/json" \
  -d '{"game_id": "test_game", "min_population": 10}' | jq .

echo "\n4. Getting player profile..."
curl -s -X POST $BASE_URL/api/v1/affordances/player/profile \
  -H "Content-Type: application/json" \
  -d '{"player_id": "test_player_001", "game_id": "test_game"}' | jq .

echo "\n✅ Tests complete!"
```

Run with: `chmod +x test_affordances.sh && ./test_affordances.sh`

---

## Success Criteria

✅ Server starts without errors
✅ New endpoints appear in Swagger UI
✅ Affordance discovery returns meaningful affordance names
✅ Player profiles show event_percentage per affordance
✅ Interpretations explain what the player actually does

If all above pass, the system is working correctly!
