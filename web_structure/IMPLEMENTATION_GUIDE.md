# Implementation Guide: Week-by-Week Plan

**Date**: 2025-11-24
**Goal**: Transform current system into Platform + Apps architecture without breaking anything

---

## Overview

This guide shows you **exactly what to do** to reorganize your current codebase into a platform model while continuing to ship features.

**Total Timeline:** 4 weeks to complete reorganization + ongoing feature development

---

## Week 1: Schema Separation & Code Reorganization

### Day 1-2: Database Schema Migration

**Create the schemas:**
```sql
-- migrations/001_create_schemas.sql

-- Create schemas
CREATE SCHEMA IF NOT EXISTS platform;
CREATE SCHEMA IF NOT EXISTS support_app;
CREATE SCHEMA IF NOT EXISTS shared;

-- Move platform tables
ALTER TABLE IF EXISTS customer_profiles SET SCHEMA platform;
ALTER TABLE IF EXISTS archetype_definitions SET SCHEMA platform;
ALTER TABLE IF EXISTS dim_archetype_l1 SET SCHEMA platform;
ALTER TABLE IF EXISTS dim_archetype_l2 SET SCHEMA platform;
ALTER TABLE IF EXISTS dim_archetype_l3 SET SCHEMA platform;

-- Move support tables
ALTER TABLE IF EXISTS tickets SET SCHEMA support_app;
ALTER TABLE IF EXISTS ticket_messages SET SCHEMA support_app;
ALTER TABLE IF EXISTS ticket_notes SET SCHEMA support_app;
ALTER TABLE IF EXISTS ticket_ai_recommendations SET SCHEMA support_app;

-- Move shared tables
ALTER TABLE IF EXISTS tenants SET SCHEMA shared;

-- Create database roles
CREATE ROLE IF NOT EXISTS quimbi_platform_role;
CREATE ROLE IF NOT EXISTS quimbi_support_role;

-- Grant permissions
GRANT ALL ON SCHEMA platform TO quimbi_platform_role;
GRANT SELECT ON SCHEMA support_app TO quimbi_platform_role;
GRANT ALL ON SCHEMA shared TO quimbi_platform_role;

GRANT ALL ON SCHEMA support_app TO quimbi_support_role;
GRANT SELECT ON SCHEMA platform TO quimbi_support_role;
GRANT ALL ON SCHEMA shared TO quimbi_support_role;

GRANT ALL ON ALL TABLES IN SCHEMA platform TO quimbi_platform_role;
GRANT SELECT ON ALL TABLES IN SCHEMA support_app TO quimbi_platform_role;
GRANT ALL ON ALL TABLES IN SCHEMA support_app TO quimbi_support_role;
GRANT SELECT ON ALL TABLES IN SCHEMA platform TO quimbi_support_role;
```

**Run migration:**
```bash
# Local testing
psql $DATABASE_URL -f migrations/001_create_schemas.sql

# Production (Railway)
PGPASSWORD="..." psql -h switchyard.proxy.rlwy.net -p 47164 -U postgres -d railway -f migrations/001_create_schemas.sql
```

**Update all models:**
```python
# platform/models/customer_profile.py
class CustomerProfile(Base):
    __tablename__ = "customer_profiles"
    __table_args__ = {"schema": "platform"}
    # ... rest unchanged

# apps/support/models/ticket.py
class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = {"schema": "support_app"}
    # ... rest unchanged
```

**Test:**
```bash
# Verify schemas exist
psql $DATABASE_URL -c "\dn"

# Verify tables moved
psql $DATABASE_URL -c "\dt platform.*"
psql $DATABASE_URL -c "\dt support_app.*"

# Run app and verify queries work
python -m pytest tests/
```

---

### Day 3-5: Directory Restructure

**Create new directory structure:**
```bash
mkdir -p platform/api/routers
mkdir -p platform/ml
mkdir -p platform/segmentation
mkdir -p platform/services
mkdir -p platform/models
mkdir -p platform/cache

mkdir -p apps/support/api/routers
mkdir -p apps/support/models
mkdir -p apps/support/services
mkdir -p apps/support/integrations

mkdir -p shared/auth
mkdir -p shared/database
mkdir -p shared/middleware
mkdir -p shared/config
```

**Move files systematically:**

```bash
# Platform code
git mv backend/ml platform/
git mv backend/segmentation platform/
git mv backend/services/ai_service.py platform/services/
git mv backend/cache/redis_cache.py platform/cache/

# Support app code
git mv backend/api/routers/tickets.py apps/support/api/routers/
git mv backend/api/routers/ai.py apps/support/api/routers/
git mv backend/models/ticket.py apps/support/models/

# Shared code
git mv backend/api/auth.py shared/auth/
git mv backend/api/dependencies.py shared/auth/
git mv backend/core/database.py shared/database/
git mv backend/middleware shared/
git mv backend/core/config.py shared/config/

# Update imports (next step)
```

**Create platform models package:**
```python
# platform/models/__init__.py
from .customer_profile import CustomerProfile
from .archetype import ArchetypeDefinition, DimArchetypeL1, DimArchetypeL2, DimArchetypeL3

__all__ = [
    "CustomerProfile",
    "ArchetypeDefinition",
    "DimArchetypeL1",
    "DimArchetypeL2",
    "DimArchetypeL3",
]
```

```python
# platform/models/customer_profile.py
from sqlalchemy import Column, String, Integer, Float, JSONB, DateTime
from sqlalchemy.sql import func
from shared.database import Base

class CustomerProfile(Base):
    __tablename__ = "customer_profiles"
    __table_args__ = {"schema": "platform"}

    customer_id = Column(String, primary_key=True)
    store_id = Column(String)
    archetype_id = Column(String)
    # ... rest of existing fields
```

**Create support app models package:**
```python
# apps/support/models/__init__.py
from .ticket import Ticket, TicketMessage, TicketNote, TicketAIRecommendation

__all__ = [
    "Ticket",
    "TicketMessage",
    "TicketNote",
    "TicketAIRecommendation",
]
```

```python
# apps/support/models/ticket.py
from sqlalchemy import Column, String, UUID, DateTime, Boolean
from shared.database import Base

class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = {"schema": "support_app"}

    id = Column(UUID, primary_key=True)
    customer_id = Column(String)  # Reference to platform.customer_profiles
    # ... rest of existing fields
```

**Update all imports:**
```bash
# Use find/replace across codebase
# Old: from backend.models import Ticket
# New: from apps.support.models import Ticket

# Old: from backend.services.ai_service import ai_service
# New: from platform.services.ai_service import ai_service

# Verify with grep
grep -r "from backend" . --exclude-dir=archive
# Should return nothing after updates
```

**Test everything still works:**
```bash
python -m pytest tests/
python backend/main.py  # Should start without errors
```

---

## Week 2: Platform API Layer

### Day 1-2: Create Platform Intelligence API

**Create platform router:**
```python
# platform/api/routers/intelligence.py

from fastapi import APIRouter, Depends
from typing import Dict, Any
from platform.services.intelligence_service import IntelligenceService
from shared.auth.dependencies import require_api_key

router = APIRouter(
    prefix="/api/intelligence",
    tags=["platform-intelligence"],
    dependencies=[Depends(require_api_key)]
)

@router.post("/analyze")
async def analyze_customer(
    customer_id: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze customer behavioral profile.

    Returns DNA, segments, archetype, behavioral scores.
    Generic endpoint - works for any application (support, marketing, sales).
    """
    intelligence = IntelligenceService()
    return await intelligence.analyze_customer(customer_id, context)


@router.post("/predict/churn")
async def predict_churn(customer_id: str) -> Dict[str, Any]:
    """Predict customer churn risk."""
    intelligence = IntelligenceService()
    return await intelligence.predict_churn(customer_id)


@router.post("/predict/ltv")
async def predict_ltv(
    customer_id: str,
    horizon_months: int = 12
) -> Dict[str, Any]:
    """Forecast customer lifetime value."""
    intelligence = IntelligenceService()
    return await intelligence.predict_ltv(customer_id, horizon_months)
```

**Create intelligence service:**
```python
# platform/services/intelligence_service.py

from typing import Dict, Any
from sqlalchemy import select
from shared.database import get_db_session
from platform.models import CustomerProfile
from platform.ml.churn_model import predict_churn_proba
from platform.ml.ltv_model import predict_ltv_value
from platform.cache.intelligence_cache import get_cached_analysis, cache_analysis

class IntelligenceService:
    """Centralized service for customer intelligence operations."""

    async def analyze_customer(
        self,
        customer_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze customer and return full intelligence profile.

        Context can include:
        - orders: Recent order history
        - interactions: Recent customer interactions
        - events: Behavioral events

        Returns unified intelligence usable by any application.
        """
        # Check cache first
        cached = await get_cached_analysis(customer_id)
        if cached:
            return cached

        # Fetch customer profile
        async with get_db_session() as db:
            result = await db.execute(
                select(CustomerProfile).where(
                    CustomerProfile.customer_id == customer_id
                )
            )
            profile = result.scalar_one_or_none()

            if not profile:
                return {"error": "Customer not found"}

        # Build intelligence response
        intelligence = {
            "customer_id": customer_id,
            "archetype": {
                "id": profile.archetype_id,
                "level": profile.archetype_level,
                "segments": profile.dominant_segments,
            },
            "behavioral_metrics": {
                "lifetime_value": profile.lifetime_value,
                "total_orders": profile.total_orders,
                "avg_order_value": profile.avg_order_value,
                "days_since_last_purchase": profile.days_since_last_purchase,
                "customer_tenure_days": profile.customer_tenure_days,
            },
            "predictions": {
                "churn_risk": profile.churn_risk_score,
                "ltv_12mo": await self.predict_ltv(customer_id, 12),
            },
            "communication_guidance": self._build_communication_guidance(profile),
        }

        # Cache for 15 minutes
        await cache_analysis(customer_id, intelligence, ttl=900)

        return intelligence

    def _build_communication_guidance(self, profile: CustomerProfile) -> list:
        """Generate communication style recommendations based on archetype."""
        guidance = []
        segments = profile.dominant_segments or {}

        if "deal_hunter" in segments.get("price_sensitivity", ""):
            guidance.append("Customer responds well to value propositions")
        elif "full_price" in segments.get("price_sensitivity", ""):
            guidance.append("Focus on quality over discounts")

        # ... rest of existing logic from get_customer_profile_for_ai

        return guidance
```

**Update main.py to include platform routes:**
```python
# main.py or platform_main.py

from fastapi import FastAPI
from platform.api.routers import intelligence

app = FastAPI(title="Quimbi Platform")

# Include platform routes
app.include_router(intelligence.router)

# Keep existing routes for backward compatibility
# from apps.support.api.routers import tickets, ai
# app.include_router(tickets.router)
# app.include_router(ai.router)
```

---

### Day 3-4: Create Platform Generation API

```python
# platform/api/routers/generation.py

from fastapi import APIRouter, Depends
from typing import Dict, Any, List
from platform.services.ai_generation_service import AIGenerationService
from shared.auth.dependencies import require_api_key

router = APIRouter(
    prefix="/api/generation",
    tags=["platform-generation"],
    dependencies=[Depends(require_api_key)]
)

@router.post("/message")
async def generate_message(
    customer_profile: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate personalized message for any context.

    Context includes:
    - conversation: Message history
    - goal: "resolve_support_issue", "nurture_lead", "upsell", etc.
    - channel: "email", "sms", "chat"
    - constraints: tone, length, etc.
    """
    generator = AIGenerationService()
    return await generator.generate_message(customer_profile, context)


@router.post("/actions")
async def recommend_actions(
    customer_profile: Dict[str, Any],
    scenario: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Recommend next best actions for any scenario.

    Scenarios: "support_ticket", "sales_opportunity", "marketing_campaign"
    """
    generator = AIGenerationService()
    return await generator.recommend_actions(customer_profile, scenario, context)
```

```python
# platform/services/ai_generation_service.py

from typing import Dict, Any
import anthropic
import os

class AIGenerationService:
    """AI generation using Claude, abstracted for any use case."""

    def __init__(self):
        self.claude_client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

    async def generate_message(
        self,
        customer_profile: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate personalized message using customer intelligence.

        Works for support tickets, marketing emails, sales outreach, etc.
        """
        # Extract from context
        goal = context.get("goal", "generic_communication")
        channel = context.get("channel", "email")
        tone = context.get("constraints", {}).get("tone", "professional")
        conversation = context.get("conversation", [])

        # Build prompt (generic, not support-specific)
        prompt = self._build_generation_prompt(
            customer_profile,
            goal,
            channel,
            tone,
            conversation
        )

        # Call Claude
        response = self.claude_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            "message": response.content[0].text,
            "tone": tone,
            "channel": channel,
            "personalization_applied": self._extract_personalizations(
                customer_profile
            ),
        }

    def _build_generation_prompt(
        self,
        profile: Dict,
        goal: str,
        channel: str,
        tone: str,
        conversation: list
    ) -> str:
        """Build Claude prompt based on goal and customer profile."""

        # Goal-specific instructions
        goal_instructions = {
            "resolve_support_issue": "Focus on solving the problem quickly and professionally",
            "nurture_lead": "Build relationship and provide value, soft sell",
            "upsell": "Recommend complementary products based on purchase history",
            "win_back": "Re-engage inactive customer with personalized offer",
        }

        # Build customer context from intelligence
        customer_context = f"""
Customer Intelligence:
- Archetype: {profile.get('archetype', {}).get('segments', {})}
- LTV: ${profile.get('behavioral_metrics', {}).get('lifetime_value', 0):.2f}
- Purchase Frequency: {profile.get('behavioral_metrics', {}).get('total_orders', 0)} orders
- Communication Guidance: {', '.join(profile.get('communication_guidance', []))}
"""

        prompt = f"""You are an AI assistant generating personalized customer communication.

{customer_context}

Goal: {goal_instructions.get(goal, goal)}
Channel: {channel}
Tone: {tone}

Recent conversation:
{self._format_conversation(conversation)}

Generate a message that:
1. Reflects the customer's behavioral profile
2. Achieves the stated goal
3. Matches the tone and channel
4. Uses specific details from their history when relevant

Only return the message content, no metadata.
"""
        return prompt
```

**Test platform APIs:**
```bash
# Start server
python main.py

# Test intelligence endpoint
curl -X POST http://localhost:8000/api/intelligence/analyze \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "123", "context": {}}'

# Test generation endpoint
curl -X POST http://localhost:8000/api/generation/message \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_profile": {...},
    "context": {
      "goal": "resolve_support_issue",
      "channel": "email",
      "conversation": [...]
    }
  }'
```

---

### Day 5: Create Platform Client for Support App

```python
# apps/support/services/platform_client.py

import httpx
import os
from typing import Dict, Any, Optional
from shared.config import settings

class PlatformClient:
    """
    Client for calling Quimbi Platform APIs.

    This abstraction allows support app to use platform intelligence
    without knowing if it's same process or separate service.
    """

    def __init__(self):
        # For now, platform runs in same process
        # Future: external URL like https://platform.quimbi.ai
        self.base_url = os.getenv(
            "PLATFORM_URL",
            "http://localhost:8000"  # Same process
        )
        self.api_key = os.getenv("PLATFORM_API_KEY", settings.ADMIN_KEY)
        self.http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key},
            timeout=30.0
        )

    async def analyze_customer(
        self,
        customer_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get customer intelligence from platform."""
        response = await self.http_client.post(
            "/api/intelligence/analyze",
            json={"customer_id": customer_id, "context": context or {}}
        )
        response.raise_for_status()
        return response.json()

    async def predict_churn(self, customer_id: str) -> Dict[str, Any]:
        """Get churn prediction from platform."""
        response = await self.http_client.post(
            "/api/intelligence/predict/churn",
            json={"customer_id": customer_id}
        )
        response.raise_for_status()
        return response.json()

    async def generate_message(
        self,
        customer_profile: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate AI message via platform."""
        response = await self.http_client.post(
            "/api/generation/message",
            json={
                "customer_profile": customer_profile,
                "context": context
            }
        )
        response.raise_for_status()
        return response.json()

    async def recommend_actions(
        self,
        customer_profile: Dict[str, Any],
        scenario: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get recommended actions from platform."""
        response = await self.http_client.post(
            "/api/generation/actions",
            json={
                "customer_profile": customer_profile,
                "scenario": scenario,
                "context": context
            }
        )
        response.raise_for_status()
        return response.json()


# Singleton instance
platform_client = PlatformClient()
```

**Update support ticket endpoints to use platform client:**
```python
# apps/support/api/routers/tickets.py

from apps.support.services.platform_client import platform_client

@router.get("/api/support/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    # Fetch ticket from support database
    async with get_db_session() as db:
        ticket = await db.get(Ticket, ticket_id)

    # Call platform for customer intelligence
    customer_intel = await platform_client.analyze_customer(
        customer_id=ticket.customer_id
    )

    # Enrich response
    return {
        "ticket": ticket.to_dict(),
        "customer_intelligence": customer_intel,
        "ai_draft": await platform_client.generate_message(
            customer_profile=customer_intel,
            context={
                "goal": "resolve_support_issue",
                "conversation": ticket.messages
            }
        )
    }
```

---

## Week 3: Add Missing Support Features

Now that platform/app separation is clear, add support-specific features to `apps/support/`.

### Day 1-2: Agent Management

**Create agent model:**
```python
# apps/support/models/agent.py

from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from shared.database import Base
import uuid

class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = {"schema": "support_app"}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)

    # Role and permissions
    role = Column(String, default="agent")  # agent, supervisor, admin
    department = Column(String)
    specializations = Column(JSON, default=list)  # ["technical", "billing", "vip"]

    # Availability
    status = Column(String, default="offline")  # online, busy, away, offline
    max_concurrent_tickets = Column(Integer, default=10)
    accepts_new_tickets = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    last_login_at = Column(DateTime)

    is_active = Column(Boolean, default=True)
```

**Create agent router:**
```python
# apps/support/api/routers/agents.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from apps.support.models.agent import Agent
from shared.database import get_db_session
from shared.auth.jwt import create_access_token, verify_password, hash_password
from pydantic import BaseModel

router = APIRouter(prefix="/api/support/agents", tags=["agents"])

class AgentCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str = "agent"

class AgentLogin(BaseModel):
    email: str
    password: str

@router.post("/")
async def create_agent(agent: AgentCreate):
    """Create new agent (admin only)."""
    async with get_db_session() as db:
        new_agent = Agent(
            email=agent.email,
            name=agent.name,
            hashed_password=hash_password(agent.password),
            role=agent.role
        )
        db.add(new_agent)
        await db.commit()
        return {"id": new_agent.id, "email": new_agent.email}

@router.post("/login")
async def login(credentials: AgentLogin):
    """Agent login - returns JWT token."""
    async with get_db_session() as db:
        result = await db.execute(
            select(Agent).where(Agent.email == credentials.email)
        )
        agent = result.scalar_one_or_none()

        if not agent or not verify_password(credentials.password, agent.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token({"agent_id": agent.id, "role": agent.role})
        return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
async def get_current_agent(agent_id: str = Depends(get_current_agent_id)):
    """Get current logged-in agent."""
    async with get_db_session() as db:
        agent = await db.get(Agent, agent_id)
        return agent.to_dict()
```

---

### Day 3-4: Ticket Assignment

```python
# apps/support/models/assignment.py

from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.sql import func
from shared.database import Base
import uuid

class TicketAssignment(Base):
    __tablename__ = "assignments"
    __table_args__ = {"schema": "support_app"}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, nullable=False, index=True)

    assigned_at = Column(DateTime, server_default=func.now())
    assigned_by = Column(String)  # agent_id who made assignment, or "system"
    assignment_reason = Column(String)  # "manual", "auto_skill_match", "auto_load_balance"

    accepted_at = Column(DateTime)
    completed_at = Column(DateTime)

    status = Column(String, default="assigned")  # assigned, accepted, in_progress, completed
```

```python
# apps/support/services/assignment_service.py

from typing import Optional
from sqlalchemy import select, func
from apps.support.models import Agent, Ticket, TicketAssignment
from apps.support.services.platform_client import platform_client
from shared.database import get_db_session

class AssignmentService:
    """Smart ticket assignment using platform intelligence."""

    async def auto_assign_ticket(self, ticket_id: str) -> str:
        """
        Automatically assign ticket to best available agent.

        Uses:
        - Customer intelligence from platform (VIP status, churn risk)
        - Agent availability and workload
        - Agent specializations
        """
        async with get_db_session() as db:
            # Get ticket
            ticket = await db.get(Ticket, ticket_id)

            # Get customer intelligence
            customer_intel = await platform_client.analyze_customer(
                ticket.customer_id
            )

            # Get available agents
            result = await db.execute(
                select(Agent).where(
                    Agent.is_active == True,
                    Agent.status.in_(["online", "away"]),
                    Agent.accepts_new_tickets == True
                )
            )
            available_agents = result.scalars().all()

            # Score agents
            best_agent = await self._score_agents(
                available_agents,
                ticket,
                customer_intel
            )

            # Create assignment
            assignment = TicketAssignment(
                ticket_id=ticket_id,
                agent_id=best_agent.id,
                assigned_by="system",
                assignment_reason="auto_skill_match"
            )
            db.add(assignment)
            await db.commit()

            return best_agent.id

    async def _score_agents(
        self,
        agents: list,
        ticket: Ticket,
        customer_intel: dict
    ) -> Agent:
        """Score agents based on match quality."""
        async with get_db_session() as db:
            agent_scores = []

            for agent in agents:
                score = 0

                # Check workload
                workload_result = await db.execute(
                    select(func.count(TicketAssignment.id))
                    .where(
                        TicketAssignment.agent_id == agent.id,
                        TicketAssignment.status.in_(["assigned", "in_progress"])
                    )
                )
                current_workload = workload_result.scalar()

                if current_workload >= agent.max_concurrent_tickets:
                    continue  # Skip overloaded agents

                # Prefer less loaded agents
                score += (agent.max_concurrent_tickets - current_workload) * 10

                # VIP customers go to senior agents
                is_vip = customer_intel.get("behavioral_metrics", {}).get(
                    "lifetime_value", 0
                ) > 1000
                if is_vip and agent.role == "supervisor":
                    score += 50

                # Match specializations
                if ticket.category in agent.specializations:
                    score += 30

                agent_scores.append((agent, score))

            # Return highest scored agent
            agent_scores.sort(key=lambda x: x[1], reverse=True)
            return agent_scores[0][0] if agent_scores else agents[0]
```

---

### Day 5: SLA Tracking

```python
# apps/support/models/sla.py

from sqlalchemy import Column, String, Integer, DateTime, Boolean
from shared.database import Base

class SLAPolicy(Base):
    __tablename__ = "sla_policies"
    __table_args__ = {"schema": "support_app"}

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    priority = Column(String, nullable=False)  # urgent, high, normal, low

    # Time targets (in minutes)
    first_response_target = Column(Integer, nullable=False)
    resolution_target = Column(Integer, nullable=False)

    is_active = Column(Boolean, default=True)


class SLATracking(Base):
    __tablename__ = "sla_tracking"
    __table_args__ = {"schema": "support_app"}

    id = Column(String, primary_key=True)
    ticket_id = Column(String, nullable=False, unique=True, index=True)
    policy_id = Column(String, nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False)
    first_response_at = Column(DateTime)
    resolved_at = Column(DateTime)

    # Breach tracking
    first_response_breached = Column(Boolean, default=False)
    resolution_breached = Column(Boolean, default=False)

    # Pause time (for "pending customer" status)
    paused_at = Column(DateTime)
    total_paused_minutes = Column(Integer, default=0)
```

**Add SLA monitoring background task:**
```python
# apps/support/tasks/sla_monitor.py

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from apps.support.models.sla import SLATracking, SLAPolicy
from shared.database import get_db_session

async def monitor_slas():
    """Check SLA status every minute and send alerts."""
    while True:
        await asyncio.sleep(60)  # Run every minute

        async with get_db_session() as db:
            # Get active SLA trackings
            result = await db.execute(
                select(SLATracking, SLAPolicy)
                .join(SLAPolicy, SLATracking.policy_id == SLAPolicy.id)
                .where(SLATracking.resolved_at == None)
            )

            for tracking, policy in result:
                now = datetime.utcnow()

                # Check first response SLA
                if not tracking.first_response_at:
                    elapsed = (now - tracking.created_at).total_seconds() / 60
                    if elapsed > policy.first_response_target:
                        tracking.first_response_breached = True
                        await send_sla_breach_alert(tracking, "first_response")

                # Check resolution SLA
                elapsed = (now - tracking.created_at).total_seconds() / 60
                elapsed -= tracking.total_paused_minutes
                if elapsed > policy.resolution_target:
                    tracking.resolution_breached = True
                    await send_sla_breach_alert(tracking, "resolution")

            await db.commit()
```

---

## Week 4: Testing & Documentation

### Day 1-2: Write Tests

```python
# tests/platform/test_intelligence_api.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_analyze_customer():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/intelligence/analyze",
            json={"customer_id": "test123", "context": {}},
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "archetype" in data
        assert "behavioral_metrics" in data
```

```python
# tests/apps/support/test_tickets.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_ticket_with_ai():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/support/tickets",
            json={
                "customer_id": "test123",
                "subject": "Help needed",
                "channel": "email"
            },
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "ticket" in data
        assert "customer_intelligence" in data
        assert "ai_draft" in data
```

---

### Day 3-4: Update Documentation

Create README files:

```markdown
# platform/README.md

# Quimbi Platform - Customer Intelligence Engine

## What This Is

The Quimbi Platform is a horizontal AI/ML layer that provides customer intelligence
for any application (support, marketing, sales, analytics).

## APIs Provided

- `/api/intelligence/analyze` - Customer behavioral analysis
- `/api/intelligence/predict/churn` - Churn prediction
- `/api/intelligence/predict/ltv` - LTV forecasting
- `/api/generation/message` - AI message generation
- `/api/generation/actions` - Recommended actions

## Key Modules

- `ml/` - Machine learning models (churn, LTV)
- `segmentation/` - 14-axis behavioral segmentation
- `services/` - Intelligence and generation services
- `models/` - Platform data models

## Data Ownership

Platform owns:
- Customer behavioral profiles (segments, DNA)
- ML model artifacts
- Analytics cache

Platform does NOT own:
- Operational data (tickets, campaigns, etc.)
- Application-specific workflows
```

```markdown
# apps/support/README.md

# Support App - Customer Support CRM

## What This Is

A full-featured customer support application built on Quimbi Platform.

## Features

- Ticket management (CRUD, status tracking)
- Agent management (auth, roles, availability)
- Smart assignment (skill-based, load-balanced)
- SLA tracking and breach alerts
- AI-powered drafts and recommendations (via Platform)

## APIs Provided

- `/api/support/tickets` - Ticket operations
- `/api/support/agents` - Agent management
- `/api/support/assignments` - Ticket routing

## Integration with Platform

Support app calls Quimbi Platform for:
- Customer intelligence (DNA, segments, churn risk)
- AI draft generation
- Recommended actions

See `services/platform_client.py` for integration details.
```

---

### Day 5: Deploy & Verify

**Deploy to Railway:**
```bash
# Commit all changes
git add .
git commit -m "Reorganize into platform + apps architecture

- Separate schemas: platform, support_app, shared
- Platform intelligence API (/api/intelligence/*)
- Platform generation API (/api/generation/*)
- Support app uses platform client
- Added agents, assignments, SLA tracking
"

git push

# Deploy
railway up
```

**Verify deployment:**
```bash
# Check platform APIs
curl https://your-app.railway.app/api/intelligence/analyze \
  -H "X-API-Key: $ADMIN_KEY" \
  -d '{"customer_id": "123", "context": {}}'

# Check support APIs
curl https://your-app.railway.app/api/support/tickets \
  -H "X-API-Key: $ADMIN_KEY"

# Check schemas in database
railway run psql $DATABASE_URL -c "\dn"
railway run psql $DATABASE_URL -c "\dt platform.*"
railway run psql $DATABASE_URL -c "\dt support_app.*"
```

---

## Summary

After 4 weeks, you'll have:

✅ **Clear Platform/App Separation**
- `platform/` - Reusable customer intelligence
- `apps/support/` - Support-specific operations
- `shared/` - Common utilities

✅ **Database Schema Isolation**
- `platform` schema - ML/analytics data
- `support_app` schema - Operational data
- `shared` schema - Multi-tenancy

✅ **Platform APIs**
- Intelligence endpoints (analyze, predict)
- Generation endpoints (message, actions)
- Generic, reusable across applications

✅ **Full Support App**
- Agents, assignments, SLA tracking
- Uses platform for all intelligence
- Ready for production

✅ **Foundation for Growth**
- Add `apps/marketing/` later
- Add `apps/sales/` later
- Platform serves all apps

And you did it **without breaking production** or rewriting everything from scratch.
