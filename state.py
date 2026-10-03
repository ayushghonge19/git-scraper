"""State definition for GitHub Memory Assistant.

In LangGraph, the State is the central data schema shared across all nodes
in the graph. Each node receives the current state and returns an update.
"""

from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """The graph state schema holding the conversation messages.

    Attributes:
        messages: Sequence of chat messages (HumanMessage, AIMessage, etc.).
            The `add_messages` reducer tells LangGraph how to merge new messages:
            it appends incoming messages rather than replacing the whole list,
            and handles message ID matching if needed.
    """
    messages: Annotated[list[BaseMessage], add_messages]
