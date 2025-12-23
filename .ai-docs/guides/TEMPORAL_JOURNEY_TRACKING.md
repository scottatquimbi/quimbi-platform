# Temporal Journey Tracking - Individual Movement Through Product Affordances

## The Problem We Solved

The unified segmentation system was **population-explanatory** but not **individual-explanatory**:

### What We Had ✅
- **Taxonomy Calibration**: Self-discovered axes (PCA) and segments (KMeans) from population
- **Adaptive Categorization**: Fuzzy membership placing players across N-dimensional segment space
- **Current State**: "Player is 0.8 economy_high, 0.6 engagement_casual, 0.7 temporal_weekend"

### What Was Missing ❌
- **Historical Tracking**: How did fuzzy memberships change over time?
- **Drift Detection**: When did player move from casual → hardcore engagement?
- **Journey Characterization**: Is this player stable, evolving, exploring, or regressing?
- **Individual Explanation**: How does THIS player move through product affordances?

## The Solution: Temporal Drift Tracking

Track **changes in fuzzy membership strengths** over time to reveal individual journeys through the N-dimensional segment space.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Taxonomy Calibration (Quarterly)                                │
│ ├─ PCA discovers axes from population variance                  │
│ ├─ KMeans discovers segments within each axis                   │
│ └─ Stores segment centers + covariance matrices                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Player Categorization (Real-time)                               │
│ ├─ Calculate fuzzy memberships for player across all segments   │
│ ├─ Use Mahalanobis distance from segment centers                │
│ └─ Return N-dimensional fuzzy membership profile                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Snapshot System (NEW - Periodic)                                │
│ ├─ Store complete fuzzy membership profile at point-in-time     │
│ ├─ Frequency: Weekly, or after significant events               │
│ └─ Table: player_membership_history                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Journey Analysis (NEW - On-demand)                              │
│ ├─ Fetch ordered snapshots for player                           │
│ ├─ Detect drifts (membership strength changes >0.2)             │
│ ├─ Characterize journey type (stable/evolving/exploratory)      │
│ └─ Return temporal trajectory through segment space             │
└─────────────────────────────────────────────────────────────────┘
```

## Schema

### player_membership_history
```sql
CREATE TABLE player_membership_history (
    snapshot_id UUID PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    game_id VARCHAR(100) NOT NULL,

    snapshot_timestamp TIMESTAMPTZ NOT NULL,

    -- Full fuzzy membership profile at this point in time
    memberships JSONB NOT NULL,
    -- Format: {
    --   "economy": {"economy_low": 0.2, "economy_high": 0.8, "economy_mid": 0.1},
    --   "engagement": {"engagement_casual": 0.6, "engagement_hardcore": 0.3},
    --   "temporal": {"temporal_weekend": 0.7, "temporal_daily": 0.2}
    -- }

    profile_confidence FLOAT,
    variance_coverage FLOAT,
    data_points_used INT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_membership_history_player
ON player_membership_history(player_id, game_id, snapshot_timestamp DESC);
```

## Key Concepts

### 1. Snapshot
Point-in-time capture of player's **complete fuzzy membership profile** across all discovered segments.

**When to snapshot:**
- After initial categorization (establish baseline)
- Weekly (detect gradual drift)
- After significant events (purchases, level-ups, milestones)

### 2. Drift
**Significant change** in membership strength (Δ > 0.2) between snapshots.

**Example:**
```json
{
  "axis": "engagement",
  "segment": "engagement_casual",
  "starting_strength": 0.9,
  "ending_strength": 0.4,
  "delta": -0.5,
  "duration_days": 45,
  "drift_velocity": -0.011  // -0.5 / 45 days
}
```

**Interpretation**: Player drifted from strongly casual (0.9) to moderately casual (0.4) over 45 days, moving toward hardcore engagement.

### 3. Journey Types

Automatically characterized from drift patterns:

- **Stable**: Few drifts, consistent memberships (stability > 0.8)
- **Evolving**: Gradual directional changes on 1-2 axes
- **Exploratory**: Many drifts across 3+ axes (trying different engagement modes)
- **Regressing**: Negative drift on engagement/monetization axes

### 4. Dominant Axes
Axes with most drift activity reveal **how** player moves through product.

**Example:**
- **Dominant axes**: ["economy", "social"]
- **Interpretation**: Player's journey primarily involves economy and social discovery, with stable engagement patterns

## API Endpoints

### Initialize Journey Tracking
```bash
POST /api/v1/segmentation/journey/initialize-history

# Response
{
  "status": "success",
  "message": "Journey tracking initialized",
  "table_created": "player_membership_history"
}
```

### Create Snapshot (Manual)
```python
from backend.core.temporal_drift_tracking import TemporalDriftTrackingEngine

async with get_db_session() as session:
    engine = TemporalDriftTrackingEngine(session)

    snapshot_id = await engine.snapshot_player_memberships(
        player_id="me3_player_00042",
        game_id="mass_effect_3",
        memberships={
            "economy": {"economy_low": 0.2, "economy_high": 0.8},
            "engagement": {"engagement_casual": 0.6, "engagement_hardcore": 0.3}
        },
        profile_confidence=0.85,
        variance_coverage=0.92,
        data_points_used=156
    )
```

### Get Player Journey
```bash
GET /api/v1/segmentation/journey/{player_id}?game_id=mass_effect_3

# Optional filters
?start_date=2025-07-01T00:00:00Z
&end_date=2025-10-13T00:00:00Z
```

**Response:**
```json
{
  "player_id": "me3_player_00042",
  "game_id": "mass_effect_3",

  "journey_characterization": {
    "type": "evolving",
    "stability_score": 0.62,
    "dominant_axes": ["economy", "engagement"],
    "duration_days": 104,
    "first_snapshot": "2025-07-01T08:00:00Z",
    "last_snapshot": "2025-10-13T16:00:00Z"
  },

  "snapshots": [
    {
      "timestamp": "2025-07-01T08:00:00Z",
      "memberships": {
        "economy": {"economy_low": 0.9, "economy_high": 0.1},
        "engagement": {"engagement_casual": 0.8, "engagement_hardcore": 0.2}
      },
      "profile_confidence": 0.75,
      "variance_coverage": 0.88
    },
    {
      "timestamp": "2025-07-08T10:00:00Z",
      "memberships": {
        "economy": {"economy_low": 0.7, "economy_high": 0.3},
        "engagement": {"engagement_casual": 0.7, "engagement_hardcore": 0.3}
      },
      "profile_confidence": 0.82,
      "variance_coverage": 0.91
    },
    // ... more snapshots
    {
      "timestamp": "2025-10-13T16:00:00Z",
      "memberships": {
        "economy": {"economy_low": 0.2, "economy_high": 0.8},
        "engagement": {"engagement_casual": 0.4, "engagement_hardcore": 0.6}
      },
      "profile_confidence": 0.89,
      "variance_coverage": 0.95
    }
  ],

  "significant_drifts": [
    {
      "axis": "economy",
      "from_segment": "economy_low",
      "to_segment": "economy_high",
      "delta": 0.7,
      "starting_strength": 0.9,
      "ending_strength": 0.8,  // Note: segment-specific, high went from 0.1 → 0.8
      "duration_days": 104,
      "drift_velocity": 0.0067,
      "start_date": "2025-07-01T08:00:00Z",
      "end_date": "2025-10-13T16:00:00Z"
    },
    {
      "axis": "engagement",
      "from_segment": "engagement_casual",
      "to_segment": "engagement_hardcore",
      "delta": 0.4,
      "starting_strength": 0.8,
      "ending_strength": 0.4,  // Casual dropped
      "duration_days": 104,
      "drift_velocity": -0.0038,
      "start_date": "2025-07-01T08:00:00Z",
      "end_date": "2025-10-13T16:00:00Z"
    }
  ],

  "summary": {
    "total_snapshots": 15,
    "significant_drifts_detected": 2,
    "axes_with_movement": 2,
    "journey_interpretation": "Player is evolving through the product with gradual changes on economy, engagement over 104 days (2 significant shifts)"
  }
}
```

## Example Use Cases

### Mass Effect 3 Player Journey

**Scenario**: Analyze how a player moves through ME3's affordances over 3 months.

**Discovered Journey:**
1. **Week 1-4**: Strong casual_engagement (0.9), low economy (0.9 low_spender)
   - Playing story missions, minimal economy interaction

2. **Week 5-8**: Drift detected - economy membership shifting
   - economy_low: 0.9 → 0.5
   - economy_high: 0.1 → 0.5
   - Discovering crafting, market systems

3. **Week 9-12**: Dual drift - becoming hardcore + high spender
   - engagement_casual: 0.8 → 0.3
   - engagement_hardcore: 0.2 → 0.7
   - economy_high: 0.5 → 0.8
   - Deep engagement with endgame content + economy optimization

**Journey Type**: Evolving
**Dominant Axes**: economy, engagement
**Interpretation**: Player discovered economy systems mid-journey, this triggered deeper engagement with the game

### Churn Detection via Journey Analysis

**Red Flag Pattern:**
```json
{
  "journey_type": "regressing",
  "significant_drifts": [
    {"axis": "engagement", "delta": -0.6, "duration_days": 21},
    {"axis": "social", "delta": -0.4, "duration_days": 21}
  ]
}
```

**Interpretation**: Player showing rapid decline in engagement and social activity over 3 weeks - high churn risk.

### Conversion Success Pattern

**Healthy Pattern:**
```json
{
  "journey_type": "evolving",
  "significant_drifts": [
    {"axis": "economy", "delta": 0.7, "duration_days": 60},
    {"axis": "progression", "delta": 0.5, "duration_days": 45}
  ]
}
```

**Interpretation**: Player gradually discovering monetization affordances alongside progression systems - successful conversion path.

## How This Solves the Original Problem

### Before (Population-Explanatory Only)
"Mass Effect 3 has 4 axes with 10 segments explaining 95% of population variance."

**Missing**: How do INDIVIDUALS move through these segments?

### After (Population + Individual Explanatory)
**Population Level:**
"Mass Effect 3 has 4 axes (economy 71%, progression 24%) with economy axis showing [low: 64%, high: 32%, whale: 4%] distribution."

**Individual Level:**
"Player me3_player_00042 started as economy_low (0.9) casual_engagement (0.8), evolved over 104 days to economy_high (0.8) hardcore_engagement (0.6). Journey type: evolving. Dominant axes: economy, engagement. Interpretation: Discovered economy systems mid-journey, triggered deeper engagement."

## Implementation Notes

### Snapshot Cadence

**Recommended**:
- **Initial**: After first categorization (>10 events)
- **Ongoing**: Weekly snapshots for active players
- **Event-triggered**: After purchases, level-ups, major milestones

### Performance

**Storage**: ~1KB per snapshot (compressed JSONB)
- 1M players × 52 weeks = 52M snapshots/year = ~52GB

**Query Performance**:
- Indexed by (player_id, game_id, timestamp DESC)
- Typical journey query (<100 snapshots) executes in <50ms

### Integration with Categorization

**Automatic snapshotting** should be added to categorization engine:

```python
async def categorize_player(player_id, game_id):
    # Generate fuzzy membership profile
    profile = await engine.categorize_player(player_id, game_id)

    # Check if snapshot is due (weekly)
    last_snapshot = await get_last_snapshot(player_id, game_id)
    if not last_snapshot or (datetime.now() - last_snapshot.timestamp).days >= 7:
        # Create snapshot
        await drift_engine.snapshot_player_memberships(
            player_id=player_id,
            game_id=game_id,
            memberships=profile.all_memberships,
            profile_confidence=profile.profile_confidence,
            variance_coverage=profile.variance_coverage,
            data_points_used=profile.data_points_used
        )

    return profile
```

## Next Steps

1. **Deploy to Railway** with history table initialized
2. **Backfill historical snapshots** if categorization has been running
3. **Test journey analysis** on ME3 dataset
4. **Add automated snapshotting** to categorization workflow
5. **Build visualization** of player journeys through segment space

This completes the individual-explanatory layer while maintaining the elegant self-learning architecture of the unified segmentation system.
