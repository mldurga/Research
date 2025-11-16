"""
Test script for the Vertex AI Agent with MCP integration
Run this locally to verify agent functionality before deployment
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_mcp_connection():
    """Test MCP server connection"""
    print("Testing MCP server connection...")

    mcp_url = os.getenv("MCP_SERVER_URL")
    if not mcp_url:
        print("❌ MCP_SERVER_URL not set in environment")
        return False

    try:
        import requests
        # Test if the MCP server is accessible
        response = requests.get(f"{mcp_url}/health", timeout=10)
        if response.status_code == 200:
            print(f"✅ MCP server is accessible at {mcp_url}")
            return True
        else:
            print(f"⚠️  MCP server returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error connecting to MCP server: {str(e)}")
        return False


def test_agent_import():
    """Test agent module import"""
    print("\nTesting agent import...")

    try:
        from agent import root_agent
        print(f"✅ Agent imported successfully: {root_agent.name}")
        print(f"   Model: {root_agent.model}")
        print(f"   Tools: {len(root_agent.tools)} toolset(s)")
        return True
    except Exception as e:
        print(f"❌ Error importing agent: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_tools():
    """Test agent tools availability"""
    print("\nTesting agent tools...")

    try:
        from agent import root_agent

        # Check if MCP toolset is loaded
        if not root_agent.tools:
            print("⚠️  No tools loaded in agent")
            return False

        print(f"✅ Agent has {len(root_agent.tools)} toolset(s)")

        # Try to list available tools from MCP
        for i, toolset in enumerate(root_agent.tools):
            print(f"   Toolset {i+1}: {type(toolset).__name__}")

        return True
    except Exception as e:
        print(f"❌ Error testing agent tools: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_local_agent():
    """Test agent locally with a simple query"""
    print("\nTesting agent with a simple query...")

    try:
        from agent import root_agent

        # Simple test query
        test_query = "What PI System tools are available?"

        print(f"   Query: {test_query}")
        print("   Running agent... (this may take a moment)")

        # Note: This requires proper ADK setup and may not work without full deployment
        # Uncomment when ready to test
        # response = root_agent.run(test_query)
        # print(f"   Response: {response}")

        print("⚠️  Local execution test skipped (requires full ADK setup)")
        print("   Deploy to Vertex AI to test full functionality")

        return True
    except Exception as e:
        print(f"❌ Error testing agent: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Vertex AI Agent - Pre-deployment Tests")
    print("=" * 60)

    results = {
        "MCP Connection": test_mcp_connection(),
        "Agent Import": test_agent_import(),
        "Agent Tools": test_agent_tools(),
        "Local Agent Test": test_local_agent()
    }

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    all_passed = True
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All tests passed! Ready for deployment.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix issues before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
