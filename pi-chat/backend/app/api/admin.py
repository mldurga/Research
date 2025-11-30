"""
Admin API endpoints
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
from typing import List, Dict, Any, Optional

router = APIRouter()


class AgentConfig(BaseModel):
    """Agent configuration model"""
    id: str
    name: str
    description: str
    model: str
    system_prompt: str
    tools: List[str] = Field(default_factory=list)
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MCPTool(BaseModel):
    """MCP Tool model"""
    id: str
    name: str
    description: str
    function_name: str
    parameters: Dict[str, Any]
    enabled: bool = True


class VectorDBIndexRequest(BaseModel):
    """Request to index PI System metadata"""
    database: Optional[str] = None
    force_reindex: bool = False


# In-memory storage (use database in production)
agents: Dict[str, AgentConfig] = {}
mcp_tools: Dict[str, MCPTool] = {}


@router.get("/agents", response_model=List[AgentConfig])
async def list_agents():
    """List all configured agents"""
    return list(agents.values())


@router.post("/agents", response_model=AgentConfig)
async def create_agent(agent: AgentConfig):
    """Create a new agent"""
    if agent.id in agents:
        raise HTTPException(status_code=400, detail="Agent already exists")

    agents[agent.id] = agent
    logger.info(f"Created agent: {agent.name}")
    return agent


@router.get("/agents/{agent_id}", response_model=AgentConfig)
async def get_agent(agent_id: str):
    """Get agent by ID"""
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agents[agent_id]


@router.put("/agents/{agent_id}", response_model=AgentConfig)
async def update_agent(agent_id: str, agent: AgentConfig):
    """Update an existing agent"""
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agents[agent_id] = agent
    logger.info(f"Updated agent: {agent.name}")
    return agent


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete an agent"""
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    del agents[agent_id]
    logger.info(f"Deleted agent: {agent_id}")
    return {"status": "deleted"}


@router.get("/mcp-tools", response_model=List[MCPTool])
async def list_mcp_tools():
    """List all MCP tools"""
    return list(mcp_tools.values())


@router.post("/mcp-tools", response_model=MCPTool)
async def create_mcp_tool(tool: MCPTool):
    """Create a new MCP tool"""
    if tool.id in mcp_tools:
        raise HTTPException(status_code=400, detail="MCP tool already exists")

    mcp_tools[tool.id] = tool
    logger.info(f"Created MCP tool: {tool.name}")
    return tool


@router.get("/mcp-tools/{tool_id}", response_model=MCPTool)
async def get_mcp_tool(tool_id: str):
    """Get MCP tool by ID"""
    if tool_id not in mcp_tools:
        raise HTTPException(status_code=404, detail="MCP tool not found")

    return mcp_tools[tool_id]


@router.put("/mcp-tools/{tool_id}", response_model=MCPTool)
async def update_mcp_tool(tool_id: str, tool: MCPTool):
    """Update an existing MCP tool"""
    if tool_id not in mcp_tools:
        raise HTTPException(status_code=404, detail="MCP tool not found")

    mcp_tools[tool_id] = tool
    logger.info(f"Updated MCP tool: {tool.name}")
    return tool


@router.delete("/mcp-tools/{tool_id}")
async def delete_mcp_tool(tool_id: str):
    """Delete an MCP tool"""
    if tool_id not in mcp_tools:
        raise HTTPException(status_code=404, detail="MCP tool not found")

    del mcp_tools[tool_id]
    logger.info(f"Deleted MCP tool: {tool_id}")
    return {"status": "deleted"}


@router.post("/vector-db/index")
async def index_pi_metadata(index_request: VectorDBIndexRequest, request: Request):
    """
    Index PI System metadata in vector database

    This endpoint indexes AF elements and PI points for semantic search.
    """
    try:
        af_client = request.app.state.af_client if hasattr(request.app.state, 'af_client') else None
        vector_db = request.app.state.vector_db if hasattr(request.app.state, 'vector_db') else None

        if not af_client or not vector_db:
            raise HTTPException(status_code=503, detail="Required services not available")

        # Clear existing index if force reindex
        if index_request.force_reindex:
            vector_db.clear_collection()
            logger.info("Cleared existing vector database")

        # Search for all elements (use a broad query)
        elements = af_client.search_elements(
            query="*",
            max_results=1000,
            search_full_hierarchy=True
        )

        # Index elements
        indexed_count = vector_db.bulk_index_elements(elements)

        logger.success(f"Indexed {indexed_count} elements in vector database")

        return {
            "status": "success",
            "indexed_count": indexed_count,
            "message": f"Successfully indexed {indexed_count} PI System elements"
        }

    except Exception as e:
        logger.error(f"Error indexing PI metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector-db/stats")
async def get_vector_db_stats(request: Request):
    """Get vector database statistics"""
    try:
        vector_db = request.app.state.vector_db if hasattr(request.app.state, 'vector_db') else None

        if not vector_db:
            raise HTTPException(status_code=503, detail="Vector database not available")

        stats = vector_db.get_collection_stats()
        return stats

    except Exception as e:
        logger.error(f"Error getting vector DB stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ollama/models")
async def list_ollama_models(request: Request):
    """List available Ollama models"""
    try:
        ollama = request.app.state.ollama if hasattr(request.app.state, 'ollama') else None

        if not ollama:
            raise HTTPException(status_code=503, detail="Ollama not available")

        models = await ollama.list_models()
        return {"models": models}

    except Exception as e:
        logger.error(f"Error listing Ollama models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ollama/pull/{model_name}")
async def pull_ollama_model(model_name: str, request: Request):
    """Pull a new Ollama model"""
    try:
        ollama = request.app.state.ollama if hasattr(request.app.state, 'ollama') else None

        if not ollama:
            raise HTTPException(status_code=503, detail="Ollama not available")

        success = await ollama.pull_model(model_name)

        if success:
            return {"status": "success", "model": model_name}
        else:
            raise HTTPException(status_code=500, detail="Failed to pull model")

    except Exception as e:
        logger.error(f"Error pulling Ollama model: {e}")
        raise HTTPException(status_code=500, detail=str(e))
