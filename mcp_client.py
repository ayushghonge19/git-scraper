"""Composio MCP Client and Tool Discovery for GitHub Memory Assistant.

Connects to Composio's Model Context Protocol (MCP) server over Streamable HTTP transport,
discovers exposed GitHub tools dynamically, and provides them to the LangGraph agent.

Architecture:
    LangGraph Agent --> MultiServerMCPClient --> Composio MCP Server --> GitHub API
"""

import logging
import os
from typing import List, Tuple
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_active_github_user_id(client) -> str:
    """Finds an active GitHub connected account user_id from Composio.
    
    If no active account is found, falls back to COMPOSIO_USER_ID from environment
    or 'default'.
    """
    configured_user = os.getenv("COMPOSIO_USER_ID")
    if configured_user:
        return configured_user

    try:
        accounts = client.connected_accounts.list()
        for acc in accounts.items:
            toolkit = (
                getattr(acc, "toolkit", None)
                or getattr(acc, "app_unique_id", "")
                or ""
            )
            status = getattr(acc, "status", "").upper()
            if "github" in str(toolkit).lower() and status == "ACTIVE":
                return acc.user_id
    except Exception as e:
        logger.debug("Could not inspect connected accounts: %s", e)

    return "default"


async def discover_mcp_tools() -> Tuple[List, str]:
    """Connects to Composio MCP Server, discovers exposed GitHub tools, and returns them.

    Returns:
        tuple[list, str]: (List of LangChain StructuredTool instances, description/status string)
    """
    composio_api_key = os.getenv("COMPOSIO_API_KEY")
    if not composio_api_key:
        return [], "Composio MCP disabled (COMPOSIO_API_KEY not set)"

    try:
        from composio import Composio
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = Composio(api_key=composio_api_key)
        user_id = get_active_github_user_id(client)

        # Create session exposing core GitHub repository, issues, and content reading tools
        github_tools = [
            "GITHUB_GET_A_REPOSITORY",
            "GITHUB_SEARCH_REPOSITORIES",
            "GITHUB_LIST_REPOSITORY_ISSUES",
            "GITHUB_GET_A_REPOSITORY_README",
            "GITHUB_GET_RAW_REPOSITORY_CONTENT",
            "GITHUB_GET_REPOSITORY_CONTENT",
            "GITHUB_SEARCH_CODE",
        ]
        session = client.create(
            user_id=user_id,
            tools={"github": github_tools},
            session_preset="direct_tools",
        )

        # Connect MultiServerMCPClient over Streamable HTTP transport
        mcp_client = MultiServerMCPClient(
            {
                "composio": {
                    "url": session.mcp.url,
                    "transport": "streamable_http",
                    "headers": session.mcp.headers,
                }
            }
        )

        # Inspect and discover the tools actually exposed by the connected Composio MCP server
        tools = await mcp_client.get_tools()
        tool_names = [t.name for t in tools]
        status = (
            f"Connected to Composio MCP Server ({session.mcp.url})\n"
            f"  User ID: {user_id}\n"
            f"  Discovered MCP Tools: {', '.join(tool_names)}"
        )
        return tools, status

    except Exception as e:
        logger.warning("Failed to initialize Composio MCP client: %s", e)
        return [], f"Composio MCP Error: {e}"
