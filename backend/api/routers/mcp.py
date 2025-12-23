"""
MCP Core Query Endpoints Router

Provides:
- MCP tool listing
- MCP tool query execution
- Natural language query processing (Claude AI)

Protected by API key authentication and rate limiting.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime
import os

# Import MCP server
from mcp_server.segmentation_server import handle_mcp_call, MCP_TOOLS

# Import rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

# Import authentication
from backend.api.dependencies import require_api_key

# Import logging
from backend.middleware.logging_config import get_logger

logger = get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/api/mcp",
    tags=["mcp"],
    dependencies=[Depends(require_api_key)],
    responses={404: {"description": "Not found"}},
)


# ==================== Request/Response Models ====================

class MCPToolRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]


class MCPToolResponse(BaseModel):
    tool_name: str
    result: Dict[str, Any]
    timestamp: datetime


# ==================== MCP Tool Endpoints ====================

@router.get("/tools")
async def list_mcp_tools():
    """List all available MCP tools (public endpoint for discovery)."""
    return {
        "tools": [
            {
                "name": tool_name,
                "description": tool_info["description"],
                "parameters": tool_info["parameters"]
            }
            for tool_name, tool_info in MCP_TOOLS.items()
        ],
        "total_tools": len(MCP_TOOLS)
    }


@router.post("/query", response_model=MCPToolResponse, dependencies=[Depends(require_api_key)])
@limiter.limit("100/hour")
async def query_mcp_tool(
    http_request: Request,
    request: MCPToolRequest
):
    """
    Execute an MCP tool query.

    Note: Now protected by API key authentication.
    Also protected by rate limiting and CORS.

    Available tools:
    - get_customer_profile: Get full behavioral profile
    - search_customers: Find customers by archetype/segments
    - get_archetype_stats: Get cohort statistics
    - calculate_segment_trends: Analyze growth/decline
    - predict_churn_risk: Calculate churn probability
    - recommend_segments_for_campaign: Get campaign targeting recommendations
    """
    try:
        result = handle_mcp_call(request.tool_name, request.parameters)
        return MCPToolResponse(
            tool_name=request.tool_name,
            result=result,
            timestamp=datetime.now()
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Tool not found: {request.tool_name}")
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        logger.error(f"MCP tool execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# NOTE: Natural language query endpoint removed from router
# Full implementation lives in backend/main.py at /api/mcp/query/natural-language
# This avoids route conflicts and ensures the complete Claude AI function calling
# implementation is accessible (router was blocking the main.py endpoint)
