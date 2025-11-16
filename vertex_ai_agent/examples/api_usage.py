"""
Example Python code for interacting with the deployed Vertex AI Agent
"""

import os
from google.cloud import aiplatform
from google.cloud.aiplatform_v1beta1 import PredictionServiceClient
from google.cloud.aiplatform_v1beta1.types import PredictRequest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-project-id")
REGION = os.getenv("GCP_REGION", "us-central1")
AGENT_NAME = os.getenv("AGENT_ENGINE_APP_NAME", "pi-system-assistant")


def initialize_vertex_ai():
    """Initialize Vertex AI with project and location"""
    aiplatform.init(
        project=PROJECT_ID,
        location=REGION
    )
    print(f"Initialized Vertex AI: {PROJECT_ID} in {REGION}")


def query_agent_simple(query: str):
    """
    Simple query to the agent (basic example)

    Args:
        query: User query string

    Returns:
        Agent response
    """
    initialize_vertex_ai()

    # Note: Replace with actual agent endpoint or resource name
    # This is a simplified example - adjust based on your deployment

    print(f"\nQuery: {query}")
    print("Response: [See Vertex AI console for full integration]")
    print("\nNote: Full API integration requires the agent's endpoint URL")
    print("      which is provided after deployment.")


def query_agent_with_context(query: str, context: dict = None):
    """
    Query agent with additional context

    Args:
        query: User query string
        context: Additional context dictionary

    Returns:
        Agent response
    """
    initialize_vertex_ai()

    print(f"\nQuery: {query}")
    if context:
        print(f"Context: {context}")

    # Add your agent invocation logic here
    # Example structure:
    # response = agent.predict(
    #     instances=[{
    #         "query": query,
    #         "context": context
    #     }]
    # )

    print("Response: [Agent response would appear here]")


def batch_query(queries: list):
    """
    Send multiple queries to the agent

    Args:
        queries: List of query strings

    Returns:
        List of responses
    """
    initialize_vertex_ai()

    results = []
    for i, query in enumerate(queries, 1):
        print(f"\n[Query {i}/{len(queries)}]: {query}")
        # Add actual query logic here
        # response = query_agent_simple(query)
        # results.append(response)

    return results


def streaming_query(query: str):
    """
    Stream responses from the agent (for long-running operations)

    Args:
        query: User query string
    """
    initialize_vertex_ai()

    print(f"\nStreaming query: {query}")
    print("Waiting for response...")

    # Add streaming logic here if supported
    # for chunk in agent.stream(query):
    #     print(chunk, end='', flush=True)


# Example usage scenarios

def example_semantic_search():
    """Example: Search for equipment using semantic search"""
    query = "Find all temperature sensors in Unit 100"
    print("\n" + "=" * 60)
    print("Example: Semantic Search")
    print("=" * 60)
    query_agent_simple(query)


def example_data_retrieval():
    """Example: Retrieve historical data"""
    query = "Get the last 24 hours of data for temperature sensor TS-101"
    print("\n" + "=" * 60)
    print("Example: Data Retrieval")
    print("=" * 60)
    query_agent_simple(query)


def example_forecasting():
    """Example: Generate forecast"""
    query = "Forecast the next 7 days for sensor TS-101 based on 30 days of history"
    print("\n" + "=" * 60)
    print("Example: Forecasting")
    print("=" * 60)
    query_agent_simple(query)


def example_system_health():
    """Example: Check system health"""
    query = "Check PI System health and vector database status"
    print("\n" + "=" * 60)
    print("Example: System Health Check")
    print("=" * 60)
    query_agent_simple(query)


def example_complex_workflow():
    """Example: Complex multi-step workflow"""
    queries = [
        "Find all pumps in the facility",
        "Get current power consumption for those pumps",
        "Identify any pumps with abnormal power usage",
        "Suggest maintenance actions for abnormal pumps"
    ]

    print("\n" + "=" * 60)
    print("Example: Complex Workflow")
    print("=" * 60)

    batch_query(queries)


def main():
    """Run all examples"""
    print("=" * 60)
    print("Vertex AI Agent - API Usage Examples")
    print("=" * 60)
    print(f"\nProject: {PROJECT_ID}")
    print(f"Region: {REGION}")
    print(f"Agent: {AGENT_NAME}")
    print("\nNote: These are example patterns. Actual implementation")
    print("      requires the deployed agent's endpoint URL.")
    print("=" * 60)

    # Run examples
    example_semantic_search()
    example_data_retrieval()
    example_forecasting()
    example_system_health()
    example_complex_workflow()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
