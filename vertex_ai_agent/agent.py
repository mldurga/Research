"""
Vertex AI Agent with MCP Integration for PI System
This agent connects to the MCP server running in GCP Cloud Run and exposes PI System tools
"""

import os
from google.genai import types
from google.genai.agents import adk

# Configuration from environment variables
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://your-cloud-run-url.run.app")
MCP_SERVER_BEARER_TOKEN = os.getenv("MCP_SERVER_BEARER_TOKEN", "")  # Optional

# CRITICAL: Use synchronous agent definition for production deployment
# This is required for Vertex AI Agent Engine deployments

def create_mcp_connection():
    """Create MCP connection parameters for the Cloud Run server"""
    headers = {}
    if MCP_SERVER_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {MCP_SERVER_BEARER_TOKEN}"

    connection_params = adk.mcp.SseConnectionParams(
        url=MCP_SERVER_URL,
        headers=headers
    )

    return connection_params


# Create the MCP toolset with connection to Cloud Run MCP server
mcp_toolset = adk.mcp.MCPToolset(
    connection_params=create_mcp_connection(),
    # Optional: Filter specific tools if you don't want to expose all MCP tools
    # tool_filter=["search_af_elements_semantic", "get_recorded_values", "batch_get_element_attributes"]
)

# Define the root agent with PI System expertise
root_agent = adk.agents.LlmAgent(
    model='gemini-2.0-flash-exp',
    name='pi_system_assistant',
    preamble="""You are an expert AI assistant for AVEVA PI System (formerly OSIsoft PI System).

You have access to a comprehensive set of tools for interacting with PI System data through MCP (Model Context Protocol).

Your capabilities include:
1. **Semantic Search**: Search for AF elements using natural language queries (search_af_elements_semantic)
2. **Data Retrieval**: Get historical and real-time data from PI Points and AF Attributes
3. **System Health**: Monitor PI System health and performance
4. **Forecasting**: Generate time-series forecasts using Prophet for predictive analytics
5. **Batch Operations**: Efficiently retrieve attributes for multiple elements

When helping users:
- Always use semantic search first to find relevant AF elements before retrieving data
- Use batch operations when possible for better performance
- Provide clear explanations of PI System concepts
- Format data in user-friendly tables or summaries
- Suggest best practices for PI System data access
- When forecasting, explain the model performance metrics and confidence intervals

For data queries:
1. First, use search_af_elements_semantic to find the equipment/elements
2. Then, use batch_get_element_attributes to get attribute WebIds
3. Finally, use get_recorded_values or get_interpolated_values to retrieve data

Always verify data quality and provide insights, not just raw data.
""",
    tools=[mcp_toolset],
    # Enable function calling for tool execution
    tool_config=types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode='AUTO',  # Let the model decide when to call tools
            allowed_function_names=None  # Allow all tools from MCP
        )
    ),
    # System instructions for better responses
    system_instruction="""You are a specialized AI agent for industrial process data analysis using AVEVA PI System.

    Key principles:
    - Always validate data quality before analysis
    - Provide context and insights, not just raw numbers
    - Use appropriate time ranges for different types of analysis
    - Explain technical terms in user-friendly language
    - Suggest follow-up questions or related analyses
    - Handle errors gracefully and suggest alternatives

    For time series data:
    - Default to last 24 hours for current operational data
    - Use longer periods (7-30 days) for trend analysis
    - Consider seasonality and patterns in your analysis
    - Flag anomalies and unusual patterns

    For forecasting:
    - Explain model performance metrics (RMSE, MAPE, R²)
    - Describe uncertainty ranges and confidence intervals
    - Provide actionable recommendations based on predictions
    - Suggest when to retrain or update models
    """
)

# Export the root agent (required for ADK deployment)
__all__ = ['root_agent']
