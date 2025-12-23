# Unified Behavioral Segmentation API - Complete Documentation

**Version**: 2.0.0 (Affordance-Based)
**Last Updated**: October 13, 2025

**Base URL (Staging)**: `https://unified-segmentation-staging.up.railway.app`
**Base URL (Production)**: `https://unified-segmentation-production.up.railway.app`
**Local Development**: `http://localhost:8000`
**Interactive Docs**: `{BASE_URL}/docs`
**OpenAPI Spec**: `{BASE_URL}/openapi.json`

---

## 🎉 What's New (v2.0.0)

### New: Affordance Discovery API
The system now **discovers affordances from events** instead of using hardcoded axes!

**New Endpoints**:
- `POST /api/v1/affordances/discover` - Discover product affordances from events
- `GET /api/v1/affordances/{game_id}` - Get discovered affordances
- `POST /api/v1/affordances/player/profile` - Get player's affordance engagement

**Why This Matters**:
- No hardcoded assumptions about game features
- Explains WHAT players actually do (not just statistical labels)
- Actionable insights: "87% narrative progression, 12% combat"

**Read More**: [DEVELOPMENT_SUMMARY.md](DEVELOPMENT_SUMMARY.md)

---

## 📚 Table of Contents

1. [Affordance Discovery](#-affordance-discovery-endpoints-new) ⭐ NEW!
2. [Segment Discovery](#-segment-discovery-endpoints-new) ⭐ NEW!
3. [Data Ingestion](#-data-ingestion-endpoints)
4. [Taxonomy Calibration](#-taxonomy-calibration-endpoints) ⚠️ DEPRECATED
5. [Player Categorization](#-player-categorization-endpoints)
6. [Anomaly Detection](#-anomaly-detection-endpoints)
7. [Admin & Migration](#-admin--migration-endpoints)
8. [Health & Monitoring](#-health--monitoring-endpoints)

---

## ⭐ AFFORDANCE DISCOVERY ENDPOINTS (NEW!)

### POST /api/v1/affordances/discover
**Discover behavioral affordances from player events.**

Analyzes event patterns to discover product affordances (progression, combat, economy, etc.) instead of using hardcoded axes.

**Request Body**: `AffordanceDiscoveryRequest`
```json
{
  "game_id": "mass_effect_3",
  "force_recalibration": false,
  "min_population": 100
}
```

**Response**: `AffordanceDiscoveryResponse`
```json
{
  "game_id": "mass_effect_3",
  "affordances_discovered": 5,
  "affordance_names": [
    "progression_affordance",
    "combat_affordance",
    "economy_affordance",
    "social_affordance",
    "exploration_affordance"
  ],
  "total_variance_explained": 0.87,
  "population_analyzed": 1523,
  "confidence_score": 0.87,
  "timestamp": "2025-10-13T14:30:00Z"
}
```

**curl Example**:
```bash
curl -X POST http://localhost:8000/api/v1/affordances/discover \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": "mass_effect_3",
    "min_population": 100
  }'
```

**How It Works**:
1. Analyzes which events co-occur together
2. Clusters events into affordances using hierarchical clustering
3. Names affordances based on event types
4. Stores as behavioral axes with `axis_type='AFFORDANCE'`

---

### GET /api/v1/affordances/{game_id}
**Get discovered affordances for a game.**

Returns all affordances that have been discovered, including event types and interpretation.

**Path Parameters**:
- `game_id` (string, required) - Game identifier

**Response**: `Array<AffordanceDetail>`
```json
[
  {
    "affordance_name": "progression_affordance",
    "event_types": [
      "mission_start",
      "mission_complete",
      "level_up",
      "story_progression"
    ],
    "population_percentage": 0.85,
    "avg_event_percentage": 0.42,
    "variance_explained": 0.38,
    "interpretation": "Widely adopted feature with high engagement intensity. 85% of players use this, averaging 42% of their events."
  },
  {
    "affordance_name": "combat_affordance",
    "event_types": [
      "combat_encounter",
      "enemy_killed",
      "ability_used",
      "weapon_fired"
    ],
    "population_percentage": 0.72,
    "avg_event_percentage": 0.28,
    "variance_explained": 0.24,
    "interpretation": "Commonly used feature with moderate engagement. 72% of players use this, averaging 28% of their events."
  }
]
```

**curl Example**:
```bash
curl http://localhost:8000/api/v1/affordances/mass_effect_3
```

---

### POST /api/v1/affordances/player/profile
**Get individual player's affordance engagement profile.**

Shows HOW the player engages with each discovered affordance.

**Request Body**: `PlayerAffordanceRequest`
```json
{
  "player_id": "player_00042",
  "game_id": "mass_effect_3"
}
```

**Response**: `PlayerAffordanceResponse`
```json
{
  "player_id": "player_00042",
  "game_id": "mass_effect_3",
  "primary_affordances": [
    "progression_affordance",
    "combat_affordance"
  ],
  "affordance_engagement": {
    "progression_affordance": {
      "event_count": 287,
      "event_percentage": 0.58,
      "velocity": 3.2,
      "consistency": 0.89
    },
    "combat_affordance": {
      "event_count": 198,
      "event_percentage": 0.29,
      "velocity": 2.1,
      "consistency": 0.76
    },
    "economy_affordance": {
      "event_count": 64,
      "event_percentage": 0.12,
      "velocity": 0.8,
      "consistency": 0.31
    },
    "social_affordance": {
      "event_count": 5,
      "event_percentage": 0.01,
      "velocity": 0.1,
      "consistency": 0.05
    }
  },
  "affordances_engaged": 3,
  "affordances_ignored": 2,
  "total_events": 682,
  "confidence": 0.85,
  "interpretation": "Player heavily engages with progression_affordance (58% of events) with secondary focus on combat_affordance (29%). Has not discovered 2 affordances - opportunity for recommendations.",
  "timestamp": "2025-10-13T14:35:00Z"
}
```

**curl Example**:
```bash
curl -X POST http://localhost:8000/api/v1/affordances/player/profile \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "player_00042",
    "game_id": "mass_effect_3"
  }'
```

**Metrics Explained**:
- `event_percentage` - % of player's total events in this affordance
- `velocity` - Average events per day in this affordance
- `consistency` - How regularly player engages (0.0-1.0)

**Use Cases**:
- **Content Recommendations**: Player has 12% economy engagement → recommend crafting tutorial
- **Churn Prevention**: High progression velocity dropping → send retention campaign
- **Feature Discovery**: Player hasn't engaged with social → surface multiplayer prompts

---

## 🎯 SEGMENT DISCOVERY ENDPOINTS (NEW!)

After affordances are discovered, segment discovery clusters players by their engagement levels within each affordance.

### POST /api/v1/affordances/segments/discover
**Discover segments within affordances by clustering players.**

Clusters players into segments like "progression_high", "progression_medium", "progression_low" based on their engagement with each affordance.

**Request Body**: `SegmentDiscoveryRequest`
```json
{
  "game_id": "my_game"
}
```

**Response**: `SegmentDiscoveryResponse`
```json
{
  "game_id": "my_game",
  "segments_discovered": 12,
  "segments_by_affordance": {
    "progression": 3,
    "combat": 3,
    "economy": 3,
    "social": 3
  },
  "timestamp": "2025-10-13T15:00:00Z"
}
```

**curl Example**:
```bash
curl -X POST http://localhost:8000/api/v1/affordances/segments/discover \
  -H "Content-Type: application/json" \
  -d '{"game_id": "my_game"}'
```

**How It Works**:
1. For each affordance, loads all players' engagement metrics
2. Extracts features: [event_percentage, velocity, consistency]
3. Runs KMeans clustering to find natural groupings
4. Names segments based on engagement level (high/medium/low)
5. Stores segment centers and population statistics

---

### GET /api/v1/affordances/segments/{game_id}
**Get all discovered segments for a game.**

Returns segments across all affordances with their characteristics.

**Path Parameters**:
- `game_id` (string, required) - Game identifier

**Response**: `Array<SegmentDetail>`
```json
[
  {
    "segment_id": "progression_high",
    "segment_name": "progression_high",
    "affordance_name": "progression",
    "center_metrics": {
      "event_percentage": 0.58,
      "velocity": 3.2,
      "consistency": 0.89
    },
    "member_count": 342,
    "population_percentage": 0.25
  },
  {
    "segment_id": "progression_medium",
    "segment_name": "progression_medium",
    "affordance_name": "progression",
    "center_metrics": {
      "event_percentage": 0.28,
      "velocity": 1.8,
      "consistency": 0.72
    },
    "member_count": 617,
    "population_percentage": 0.45
  },
  {
    "segment_id": "combat_high",
    "segment_name": "combat_high",
    "affordance_name": "combat",
    "center_metrics": {
      "event_percentage": 0.45,
      "velocity": 2.5,
      "consistency": 0.82
    },
    "member_count": 278,
    "population_percentage": 0.20
  }
]
```

**curl Example**:
```bash
curl http://localhost:8000/api/v1/affordances/segments/my_game
```

---

### POST /api/v1/affordances/segments/player/memberships
**Get player's fuzzy memberships in affordance segments.**

Shows which segments the player belongs to and with what strength (fuzzy membership).

**Request Body**: `PlayerSegmentMembershipRequest`
```json
{
  "player_id": "player_123",
  "game_id": "my_game"
}
```

**Response**: `PlayerSegmentMembershipResponse`
```json
{
  "player_id": "player_123",
  "game_id": "my_game",
  "primary_segments": {
    "progression": "progression_high",
    "combat": "combat_medium",
    "economy": "economy_low"
  },
  "all_memberships": [
    {
      "segment_id": "progression_high",
      "segment_name": "progression_high",
      "affordance": "progression",
      "membership_strength": 0.92,
      "distance_from_center": 0.3,
      "position_offset": {
        "event_percentage": 0.02,
        "velocity": 0.1,
        "consistency": 0.03
      },
      "confidence": 0.85
    },
    {
      "segment_id": "progression_medium",
      "segment_name": "progression_medium",
      "affordance": "progression",
      "membership_strength": 0.15,
      "distance_from_center": 2.1,
      "position_offset": {
        "event_percentage": 0.30,
        "velocity": 1.4,
        "consistency": 0.17
      },
      "confidence": 0.85
    },
    {
      "segment_id": "combat_medium",
      "segment_name": "combat_medium",
      "affordance": "combat",
      "membership_strength": 0.78,
      "distance_from_center": 0.6,
      "position_offset": {
        "event_percentage": -0.04,
        "velocity": -0.2,
        "consistency": 0.01
      },
      "confidence": 0.85
    }
  ],
  "timestamp": "2025-10-13T15:05:00Z"
}
```

**curl Example**:
```bash
curl -X POST http://localhost:8000/api/v1/affordances/segments/player/memberships \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "player_123",
    "game_id": "my_game"
  }'
```

**Interpretation**:
- **Primary Segments**: Highest membership per affordance (what segment they "are")
- **All Memberships**: Fuzzy membership in ALL segments (with varying strengths)
- **Membership Strength**: 0.0-1.0, higher = closer to segment center
- **Distance from Center**: Mahalanobis distance in normalized space

**Use Cases**:
- **Classification**: "This is a progression_high player"
- **Transitions**: Player moving from high to medium → potential churn
- **Recommendations**: progression_high + economy_low → surface crafting
- **A/B Testing**: Target players with specific segment combinations

**See**: [SEGMENT_DISCOVERY_SUMMARY.md](SEGMENT_DISCOVERY_SUMMARY.md) for complete documentation

---

## 📊 DATA INGESTION ENDPOINTS

### POST /api/v1/ingestion/events
Ingest behavioral events for a single player.

**⚠️ IMPORTANT: Event Type Requirements**

For **affordance discovery** to work, events must have **granular event types**:

✅ **Good** (Granular):
```json
{
  "events": [
    {"event_type": "mission_start", ...},
    {"event_type": "combat_encounter", ...},
    {"event_type": "item_crafted", ...}
  ]
}
```

❌ **Bad** (All same type):
```json
{
  "events": [
    {"event_type": "daily_activity", ...},
    {"event_type": "daily_activity", ...}
  ]
}
```

**Why**: Affordance discovery clusters event types into affordances. With only one event type, there's nothing to cluster.

**See**: [RAILWAY_TEST_DATA_ANALYSIS.md](RAILWAY_TEST_DATA_ANALYSIS.md) for details

---

### Example 1: Granular Events (Recommended for Affordance Discovery)

**Request Body**: `PlayerEventsRequest`
```json
{
  "player_id": "player_123",
  "game_id": "my_game",
  "events": [
    {
      "event_type": "mission_start",
      "event_timestamp": "2025-10-13T10:00:00Z",
      "event_data": {
        "mission_id": "prologue",
        "difficulty": "normal"
      }
    },
    {
      "event_type": "combat_encounter",
      "event_timestamp": "2025-10-13T10:15:00Z",
      "event_data": {
        "enemy_type": "basic",
        "enemies_count": 3
      }
    },
    {
      "event_type": "mission_complete",
      "event_timestamp": "2025-10-13T10:30:00Z",
      "event_data": {
        "xp_gained": 100,
        "loot_quality": "rare"
      }
    },
    {
      "event_type": "item_crafted",
      "event_timestamp": "2025-10-13T10:35:00Z",
      "event_data": {
        "item_type": "sword",
        "materials_used": 5
      }
    },
    {
      "event_type": "dialogue_choice",
      "event_timestamp": "2025-10-13T10:40:00Z",
      "event_data": {
        "npc": "companion_1",
        "choice": "friendly"
      }
    }
  ]
}
```

**Use For**: Affordance discovery, segment discovery, player profiling

---

### Example 2: Aggregated Events (Legacy - Old System Only)

**Request Body**: `PlayerEventsRequest`
```json
{
  "player_id": "player_123",
  "game_id": "stress_test_001",
  "events": [
    {
      "event_type": "daily_activity",
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
  ]
}
```

**Use For**: Old hardcoded axis system only (deprecated)

**Response**: `IngestionResponse`
```json
{
  "success": true,
  "events_inserted": 1,
  "player_id": "player_123",
  "game_id": "stress_test_001",
  "message": "1 events ingested successfully"
}
```

**curl Example**:
```bash
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/ingestion/events \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "player_123",
    "game_id": "stress_test_001",
    "events": [
      {
        "event_type": "daily_activity",
        "event_timestamp": "2025-10-13T12:00:00Z",
        "event_data": {
          "session_count": 5,
          "total_session_duration_minutes": 120,
          "purchase_count": 2,
          "total_purchase_amount": 49.99
        }
      }
    ]
  }'
```

---

### POST /api/v1/ingestion/events/batch
Batch ingest events for multiple players.

**Request Body**: `Array<PlayerEventsRequest>`

---

### GET /api/v1/ingestion/stats/{game_id}
Get ingestion statistics for a game.

**Response**:
```json
{
  "game_id": "stress_test_001",
  "total_players": 1000,
  "total_events": 135070,
  "earliest_event": "2025-07-05",
  "latest_event": "2025-10-13",
  "events_per_player_avg": 135.07
}
```

**curl Example**:
```bash
curl https://unified-segmentation-staging.up.railway.app/api/v1/ingestion/stats/stress_test_001
```

---

## 🔬 TAXONOMY CALIBRATION ENDPOINTS

### POST /api/v1/segmentation/taxonomy/calibrate
Discover behavioral axes and segments for a game using PCA and KMeans clustering.

**Request Body**: `TaxonomyCalibrationRequest`
```json
{
  "game_id": "stress_test_001",
  "force_recalibration": false
}
```

**Response**: `TaxonomyCalibrationResponse`
```json
{
  "game_id": "stress_test_001",
  "axes_discovered": 2,
  "total_axes": 2,
  "universal_axes": ["engagement", "temporal"],
  "game_specific_axes": [],
  "variance_explained": 0.4,
  "population_size": 1000,
  "confidence_score": 0.3,
  "timestamp": "2025-10-13T17:12:37.993009"
}
```

**curl Example**:
```bash
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/segmentation/taxonomy/calibrate \
  -H "Content-Type: application/json" \
  -d '{"game_id": "stress_test_001"}'
```

**Notes**:
- Requires minimum 1000 players with 10+ events each
- Discovers 4 universal axes: engagement, monetization, temporal, social
- Discovers game-specific axes through PCA on unexplained variance
- Target variance explained: >70%

---

### GET /api/v1/segmentation/taxonomy/{game_id}
Get existing taxonomy for a game (from database).

**Response**:
```json
{
  "game_id": "stress_test_001",
  "genre": null,
  "total_axes": 2,
  "variance_explained": 0.4,
  "universal_axes": ["engagement", "temporal"],
  "game_specific_axes": [],
  "confidence_score": 0.3,
  "population_size": 1000,
  "last_calibration": "2025-10-13T17:12:37.993009"
}
```

**curl Example**:
```bash
curl https://unified-segmentation-staging.up.railway.app/api/v1/segmentation/taxonomy/stress_test_001
```

---

## 👤 PLAYER CATEGORIZATION ENDPOINTS

### POST /api/v1/segmentation/categorize
Categorize a player with fuzzy segment memberships across all axes.

**Request Body**: `CategorizationRequest`
```json
{
  "player_id": "player_123",
  "game_id": "stress_test_001"
}
```

**Response**: `CategorizationResponse`
```json
{
  "player_id": "player_123",
  "game_id": "stress_test_001",
  "primary_segments": {
    "engagement": "hardcore",
    "temporal": "consistent_player"
  },
  "ai_optimized_segments": {
    "engagement": "hardcore",
    "temporal": "consistent_player"
  },
  "all_memberships": {
    "engagement": {
      "hardcore": {
        "membership_strength": 0.85,
        "distance_from_center": 0.15,
        "position_offset": {"avg_daily_sessions": 0.5},
        "confidence": 0.9
      },
      "casual": {
        "membership_strength": 0.15,
        "distance_from_center": 0.85,
        "position_offset": {"avg_daily_sessions": -2.5},
        "confidence": 0.9
      }
    }
  },
  "variance_explained": 0.4,
  "confidence": 0.85,
  "timestamp": "2025-10-13T18:00:00Z"
}
```

**curl Example**:
```bash
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/segmentation/categorize \
  -H "Content-Type: application/json" \
  -d '{"player_id": "player_123", "game_id": "stress_test_001"}'
```

---

### POST /api/v1/segmentation/categorize/batch
Batch categorize multiple players.

**Query Parameters**:
- `player_ids`: Array of player IDs
- `game_id`: Game identifier

---

## 🚨 ANOMALY DETECTION ENDPOINTS

### POST /api/v1/segmentation/anomalies/detect
Detect behavioral anomalies using distance-from-center approach.

**Request Body**: `AnomalyDetectionRequest`
```json
{
  "player_id": "player_123",
  "game_id": "stress_test_001",
  "lookback_days": 90
}
```

**Response**: `AnomalyDetectionResponse`
```json
{
  "player_id": "player_123",
  "game_id": "stress_test_001",
  "is_anomalous": true,
  "overall_anomaly_score": 0.75,
  "confidence": 0.85,
  "context": "Player exhibiting unusual spending spike",
  "axis_anomalies": {
    "monetization": {
      "segment_name": "whale",
      "is_anomalous": true,
      "anomaly_score": 0.75,
      "current_distance": 3.5,
      "typical_distance": 0.5,
      "distance_delta": 3.0,
      "threshold_used": 2.0
    }
  },
  "timestamp": "2025-10-13T18:00:00Z"
}
```

**curl Example**:
```bash
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/segmentation/anomalies/detect \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "player_123",
    "game_id": "stress_test_001",
    "lookback_days": 90
  }'
```

---

## 🔧 ADMIN & MIGRATION ENDPOINTS

### POST /api/v1/admin/create-complete-schema
Create all required database tables for the unified segmentation system.

**Response**:
```json
{
  "success": true,
  "message": "Complete unified segmentation schema created",
  "tables_created": [
    "game_behavioral_taxonomy",
    "behavioral_axes",
    "segment_definitions",
    "player_segment_memberships",
    "behavioral_segments",
    "player_segmentation_state",
    "anomaly_detection_log",
    "calibration_history"
  ],
  "total_tables": 8
}
```

**curl Example**:
```bash
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/admin/create-complete-schema
```

---

### POST /api/v1/admin/fix-schema-columns
Fix schema column names to match taxonomy engine expectations.

**Response**:
```json
{
  "success": true,
  "message": "Schema columns fixed",
  "fixes_applied": [
    "behavioral_axes recreated",
    "segment_definitions created"
  ]
}
```

---

### GET /api/v1/admin/verify-schema
Verify all required tables exist with row counts.

**Response**:
```json
{
  "schema_complete": true,
  "tables": {
    "player_behavior_events": {"exists": true, "row_count": 135070},
    "game_behavioral_taxonomy": {"exists": true, "row_count": 1},
    "behavioral_axes": {"exists": true, "row_count": 2},
    "segment_definitions": {"exists": true, "row_count": 4}
  },
  "total_required": 9,
  "total_existing": 9
}
```

**curl Example**:
```bash
curl https://unified-segmentation-staging.up.railway.app/api/v1/admin/verify-schema
```

---

### GET /api/v1/admin/table-schemas
Get detailed schema information for all tables (column names, types, constraints).

**curl Example**:
```bash
curl https://unified-segmentation-staging.up.railway.app/api/v1/admin/table-schemas
```

---

### POST /api/v1/admin/run-migration
Manually run database migration (creates player_behavior_events table).

---

## ❤️ HEALTH & MONITORING ENDPOINTS

### GET /health
Basic health check with component status.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-13T18:00:00Z",
  "version": "1.0.0",
  "components": {
    "api": "healthy",
    "database": "healthy"
  }
}
```

---

### GET /health/ready
Kubernetes readiness probe (checks database connectivity).

---

### GET /health/live
Kubernetes liveness probe.

---

### GET /metrics
Prometheus metrics endpoint (placeholder - implement later).

---

## 📝 DATA SCHEMAS

### event_data JSONB Structure
```json
{
  "session_count": 5,
  "total_session_duration_minutes": 120.5,
  "avg_session_duration_minutes": 24.1,
  "purchase_count": 2,
  "total_purchase_amount": 49.99,
  "is_weekend": false,
  "progression_level": 15,
  "currency_spend_rate": 1.5,
  "progression_speed": 0.8,
  "items_crafted": 12,
  "content_discovered": 0.45
}
```

### Universal Behavioral Axes
1. **Engagement** - How intensely players engage with content
   - Metrics: avg_daily_sessions, avg_session_duration, play_day_frequency
   - Segments: hardcore, regular, casual, inactive

2. **Monetization** - Player spending behavior
   - Metrics: monthly_spend, purchase_frequency, avg_purchase_amount
   - Segments: whale, dolphin, minnow, free_play

3. **Temporal** - When and how consistently players engage
   - Metrics: weekend_vs_weekday_ratio, session_consistency
   - Segments: weekend_concentrator, weekday_player, consistent_player, irregular_player

4. **Social** - Social interaction patterns
   - Metrics: guild_participation, social_feature_usage
   - Segments: social_coordinator, social_participant, solo_player

### Game-Specific Axes
Discovered through PCA on game-specific metrics:
- Progression axis (progression_level, progression_speed)
- Economy axis (currency_spend_rate, items_crafted)
- Content axis (content_discovered, exploration_rate)

---

## 🔗 Integration Examples

### Complete Workflow: Data Ingestion → Calibration → Categorization

```bash
# Step 1: Ingest player data
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/ingestion/events \
  -H "Content-Type: application/json" \
  -d @player_events.json

# Step 2: Check ingestion stats
curl https://unified-segmentation-staging.up.railway.app/api/v1/ingestion/stats/stress_test_001

# Step 3: Calibrate taxonomy (requires 1000+ players)
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/segmentation/taxonomy/calibrate \
  -H "Content-Type: application/json" \
  -d '{"game_id": "stress_test_001"}'

# Step 4: Categorize player
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/segmentation/categorize \
  -H "Content-Type: application/json" \
  -d '{"player_id": "player_123", "game_id": "stress_test_001"}'

# Step 5: Detect anomalies
curl -X POST https://unified-segmentation-staging.up.railway.app/api/v1/segmentation/anomalies/detect \
  -H "Content-Type: application/json" \
  -d '{"player_id": "player_123", "game_id": "stress_test_001", "lookback_days": 90}'
```

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: "No taxonomy found for game"
**Solution**: Run calibration first with `POST /api/v1/segmentation/taxonomy/calibrate`

**Issue**: "Not enough data for calibration"
**Solution**: Ensure 1000+ players with 10+ events each are ingested

**Issue**: "Low variance explained (<70%)"
**Solution**: Increase diversity in player behaviors, add more spending/engagement variance

**Issue**: "Only 2-3 axes discovered instead of 4"
**Solution**: Check that monetization and social metrics have sufficient variance in your data

---

## 📚 Additional Resources

- **Swagger UI**: https://unified-segmentation-staging.up.railway.app/docs
- **OpenAPI Spec**: https://unified-segmentation-staging.up.railway.app/openapi.json
- **Schema Details**: GET /api/v1/admin/table-schemas
- **Health Status**: GET /health
