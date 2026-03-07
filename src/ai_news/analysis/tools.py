"""Custom MCP tools for the AI News analysis pipeline."""

import json
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


def create_news_tools(
    fetch_results: dict[str, Any],
    exploration_results: dict[str, str] | None = None,
    synthesis_results: dict[str, str] | None = None,
):
    """Create an in-process MCP server with tools for accessing news data.

    The returned server can be passed to ClaudeAgentOptions.mcp_servers so
    that agents can query fetched data, exploration analyses, and synthesis
    results via standard MCP tool calls.

    Args:
        fetch_results: Serialisable dict keyed by source name, each value
            containing at least an ``"items"`` list.
        exploration_results: Optional dict mapping explorer name to its
            analysis text (populated after the exploration phase).
        synthesis_results: Optional dict mapping synthesizer name to its
            synthesis text (populated after the consolidation phase).

    Returns:
        McpSdkServerConfig ready to be included in ``mcp_servers``.
    """

    @tool("get_fetched_data", "Get fetched news data for a specific source", {
        "source": str,
    })
    async def get_fetched_data(args: dict[str, Any]) -> dict[str, Any]:
        source = args["source"]
        if source == "all":
            summary = {}
            for src, data in fetch_results.items():
                summary[src] = {
                    "items_found": data.get("items_found", len(data.get("items", []))),
                    "source": src,
                }
            return {"content": [{"type": "text", "text": json.dumps(summary, indent=2)}]}

        data = fetch_results.get(source)
        if data is None:
            available = list(fetch_results.keys())
            return {
                "content": [
                    {"type": "text", "text": f"Source '{source}' not found. Available: {available}"}
                ]
            }
        return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}

    @tool("get_all_fetched_data", "Get a summary of all fetched data with item counts", {})
    async def get_all_fetched_data(_args: dict[str, Any]) -> dict[str, Any]:
        summary = {}
        for src, data in fetch_results.items():
            items = data.get("items", [])
            summary[src] = {
                "items_found": len(items),
                "sample_titles": [item.get("title", "")[:80] for item in items[:5]],
            }
        return {"content": [{"type": "text", "text": json.dumps(summary, indent=2)}]}

    @tool("get_source_items", "Get all items from a specific source", {
        "source": str,
    })
    async def get_source_items(args: dict[str, Any]) -> dict[str, Any]:
        source = args["source"]
        data = fetch_results.get(source)
        if data is None:
            return {"content": [{"type": "text", "text": f"Source not found: {source}"}]}
        items = data.get("items", [])
        return {"content": [{"type": "text", "text": json.dumps(items, indent=2)}]}

    tools_list = [get_fetched_data, get_all_fetched_data, get_source_items]

    if exploration_results is not None:
        @tool("get_exploration_results", "Get exploration analysis results from domain experts", {})
        async def get_exploration_results_tool(_args: dict[str, Any]) -> dict[str, Any]:
            return {"content": [{"type": "text", "text": json.dumps(exploration_results, indent=2)}]}

        tools_list.append(get_exploration_results_tool)

    if synthesis_results is not None:
        @tool("get_synthesis_results", "Get synthesis results from consolidation agents", {})
        async def get_synthesis_results_tool(_args: dict[str, Any]) -> dict[str, Any]:
            return {"content": [{"type": "text", "text": json.dumps(synthesis_results, indent=2)}]}

        tools_list.append(get_synthesis_results_tool)

    return create_sdk_mcp_server(
        name="ai-news-data",
        version="1.0.0",
        tools=tools_list,
    )
