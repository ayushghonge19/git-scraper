"""LangGraph workflow definition for GitHub Memory Assistant (Phase 3).

Implements an agentic workflow with Composio MCP GitHub tools and MongoDB persistence:
    START ──> agent ──(tools_condition)──> tools ──> agent ──> END
                     └──(no tools)─────────────────────────> END
"""

import logging
from typing import List, Optional, Tuple
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from state import AgentState
from config import get_llm
from checkpointer import get_checkpointer
from mcp_client import discover_mcp_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are GitHub Memory Assistant, an AI assistant with persistent memory and GitHub capabilities.\n"
    "You have access to GitHub tools via Composio's Model Context Protocol (MCP) server.\n"
    "When a user asks to check, inspect, or search for a repository, issue, or to READ the content/code of a project "
    "(e.g., 'read the content of my project vyakran', 'check DisasterLAN'), decide autonomously which GitHub tool to invoke "
    "(such as GITHUB_GET_A_REPOSITORY_README, GITHUB_GET_REPOSITORY_CONTENT, GITHUB_GET_RAW_REPOSITORY_CONTENT, or GITHUB_SEARCH_CODE).\n"
    "If owner is not explicitly specified, search repositories or try the user's username (such as ayushghonge19)."
)



def create_agent_node(llm_with_tools):
    """Creates the agent node function with tools bound to the LLM."""
    async def agent_node(state: AgentState) -> dict:
        messages = state["messages"]
        # Ensure system prompt is present at the start of conversation
        if not messages or not isinstance(messages[0], SystemMessage):
            call_messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
        else:
            call_messages = list(messages)

        response = await llm_with_tools.ainvoke(call_messages)
        return {"messages": [response]}

    return agent_node


async def build_graph(
    tools: Optional[List] = None,
    checkpointer=None,
) -> Tuple[object, str, str]:
    """Asynchronously builds and compiles the LangGraph agent with MCP tools and MongoDB persistence.

    Returns:
        tuple: (compiled_graph, checkpointer_info, mcp_info)
    """
    checkpointer_info = "In-memory (no checkpointer)"
    if checkpointer is None:
        checkpointer, checkpointer_info = get_checkpointer()

    mcp_info = "No MCP tools configured"
    if tools is None:
        tools, mcp_info = await discover_mcp_tools()

    raw_llm = get_llm()

    builder = StateGraph(AgentState)

    if tools:
        llm_with_tools = raw_llm.bind_tools(tools)
        builder.add_node("agent", create_agent_node(llm_with_tools))
        builder.add_node("tools", ToolNode(tools))

        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", tools_condition)
        builder.add_edge("tools", "agent")
    else:
        # Fallback to pure conversational node if no tools available
        async def simple_agent_node(state: AgentState) -> dict:
            response = await raw_llm.ainvoke(state["messages"])
            return {"messages": [response]}

        builder.add_node("agent", simple_agent_node)
        builder.add_edge(START, "agent")
        builder.add_edge("agent", END)

    compiled_graph = builder.compile(checkpointer=checkpointer)
    return compiled_graph, checkpointer_info, mcp_info
