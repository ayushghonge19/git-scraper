"""CLI entry point for GitHub Memory Assistant (Phase 3 - Composio MCP Integration).

Demonstrates:
    1. LangGraph Agent tool-calling loop (START -> Agent -> Tools -> Agent -> END)
    2. Model Context Protocol (MCP) tool discovery from Composio MCP Server
    3. Direct execution reaching live GitHub API
    4. Persistent state retention via MongoDB Checkpointer across sessions
"""

import argparse
import asyncio
import json
import sys
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from graph import build_graph

# Ensure UTF-8 output encoding on Windows consoles where possible
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def extract_text(content) -> str:
    """Extracts plain text string from string or list content blocks."""
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


async def async_main():
    """Runs the interactive persistent CLI chat loop with Composio MCP tools."""
    parser = argparse.ArgumentParser(
        description="GitHub Memory Assistant (Phase 3 - Composio MCP & MongoDB)"
    )
    parser.add_argument(
        "--thread",
        type=str,
        default=None,
        help="Thread ID for conversation state persistence",
    )
    args = parser.parse_args()

    print("=" * 65)
    print(" Welcome to GitHub Memory Assistant (Phase 3 - Composio MCP)")
    print(" Architecture: Agent -> MCP Client -> Composio MCP Server -> GitHub")
    print("=" * 65)
    print("Connecting to MongoDB and discovering Composio MCP tools...")

    graph, backend_status, mcp_status = await build_graph()

    print(f" Checkpointer: {backend_status}")
    print(f" MCP Status  : {mcp_status}")
    print(" Type 'exit' or 'quit' to end the session.")
    print("=" * 65)
    print()

    # 1. Determine thread_id
    if args.thread:
        thread_id = args.thread.strip()
    else:
        try:
            thread_input = input("Thread ID (press Enter for 'demo'): ").strip()
            if not sys.stdin.isatty():
                print(thread_input)
            thread_id = thread_input if thread_input else "demo"
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            return

    config = {"configurable": {"thread_id": thread_id}}
    print(f"\n[Active Thread: {thread_id}]")

    # Check if prior state exists in MongoDB for this thread
    try:
        existing_state = await graph.aget_state(config)
        if existing_state and existing_state.values.get("messages"):
            msg_count = len(existing_state.values["messages"])
            print(f"[Restored {msg_count} messages from MongoDB for thread '{thread_id}']")
    except Exception:
        pass

    print()

    # 2. Interactive chat loop
    while True:
        try:
            user_input = input("You: ").strip()
            if not sys.stdin.isatty():
                print(user_input)

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print("\nGoodbye!")
                break

            # Handle switching threads dynamically
            if user_input.startswith("/thread "):
                new_thread = user_input.split(" ", 1)[1].strip()
                if new_thread:
                    thread_id = new_thread
                    config = {"configurable": {"thread_id": thread_id}}
                    print(f"\n[Switched to Thread: {thread_id}]")
                    state = await graph.aget_state(config)
                    if state and state.values.get("messages"):
                        print(
                            f"[Restored {len(state.values['messages'])} messages for thread '{thread_id}']\n"
                        )
                    else:
                        print(f"[No prior history for thread '{thread_id}']\n")
                    continue

            # Capture message count prior to this turn to detect new tool calls
            prior_state = await graph.aget_state(config)
            prior_count = (
                len(prior_state.values.get("messages", []))
                if prior_state and prior_state.values
                else 0
            )

            # Pass new user message; graph retrieves conversation state from MongoDB
            user_message = HumanMessage(content=user_input)
            result = await graph.ainvoke({"messages": [user_message]}, config=config)

            # Inspect newly generated messages to highlight tool usage
            new_messages = result["messages"][prior_count:]
            for m in new_messages:
                if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
                    for tc in m.tool_calls:
                        tool_name = tc.get("name")
                        tool_args = json.dumps(tc.get("args", {}))
                        print(f"\n[Uses Composio MCP GitHub tool: {tool_name}]")
                        print(f"  Arguments: {tool_args}")

            # Extract and print the final assistant response
            final_message = result["messages"][-1]
            assistant_response = extract_text(final_message.content)
            print(f"\nAssistant: {assistant_response}\n")

        except KeyboardInterrupt:
            print("\n\nSession interrupted. Goodbye!")
            break
        except EOFError:
            print("\nGoodbye!")
            break
        except ValueError as ve:
            print(f"\n[Configuration Error] {ve}\n")
            break
        except Exception as e:
            print(f"\n[Error] An unexpected error occurred: {e}\n")


def main():
    """Synchronous launcher for async_main."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
