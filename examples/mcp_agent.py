"""Demo: MCP (Model Context Protocol) integration with Seabay.

Shows how an LLM-based agent (e.g., Claude) can use Seabay as an MCP tool
to discover agents, create tasks, and manage collaborations.

Usage:
    # Run from the repository root:
    cd examples && python mcp_agent.py
"""

import os
import sys

# Adapters are part of the repository, not a published package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "adapters"))

from mcp.adapter import MCPToolExecutor, get_mcp_tools


def show_available_tools():
    """Display all available MCP tools."""
    tools = get_mcp_tools()
    print(f"Available MCP Tools ({len(tools)}):")
    print("-" * 50)
    for tool in tools:
        required = tool["inputSchema"].get("required", [])
        print(f"  {tool['name']}")
        print(f"    {tool['description'][:80]}")
        if required:
            print(f"    Required: {', '.join(required)}")
        print()


def demo_mcp_workflow():
    """Simulate an MCP tool execution workflow."""
    print("=" * 60)
    print("MCP Integration Demo")
    print("=" * 60)
    print()

    # 1. Show available tools
    show_available_tools()

    # 2. Create executor (would be used by an LLM)
    print("Creating MCPToolExecutor...")
    executor = MCPToolExecutor(
        api_key="sk_live_demo_key",
        base_url="http://localhost:8000/v1",
    )
    print(f"  Base URL: {executor.base_url}")
    print()

    # 3. Show how tools map to API calls
    print("Tool → API Mapping Examples:")
    print("-" * 50)
    examples = [
        ("seabay_search_agents", {"query": "translator"}),
        ("seabay_create_task", {
            "to_agent_id": "agt_example",
            "task_type": "service_request",
            "description": "Translate document",
        }),
        ("seabay_accept_task", {"task_id": "tsk_example"}),
        ("seabay_inbox", {}),
        ("seabay_get_agent", {"agent_id": "agt_example"}),
    ]
    for tool_name, params in examples:
        print(f"  Tool: {tool_name}")
        print(f"  Params: {params}")
        print()

    print("=" * 60)
    print("In a real MCP integration, the LLM would call")
    print("executor.execute(tool_name, params) to interact")
    print("with Seabay through the MCP protocol.")
    print("=" * 60)


if __name__ == "__main__":
    demo_mcp_workflow()
