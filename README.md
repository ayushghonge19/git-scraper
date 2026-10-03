# GitHub Memory Assistant (Phase 3 — Composio MCP Integration)

An educational AI assistant built with **LangGraph StateGraph**, **MongoDB Checkpoint Persistence**, **Composio Model Context Protocol (MCP)**, and **Google Gemini** (or OpenAI).

---

## 1. Goal & Architecture

In Phase 3, we connect our persistent LangGraph assistant to live GitHub operations using **Composio's MCP server**.

```text
┌─────────────────────────┐
│     LangGraph Agent     │  (Autonomously decides when a tool is needed)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  MultiServerMCPClient   │  (Discovers tools exposed over Streamable HTTP)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Composio MCP Server   │  (Routes tool calls & manages auth credentials)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│       GitHub API        │  (Fetches live repositories, issues, branches)
└─────────────────────────┘
```

The agent maintains persistent conversation history across restarts using **MongoDB Atlas** while dynamically calling live GitHub tools via MCP.

---

## 2. Project Structure

```text
git-scraper/
├── main.py                  # CLI entry point showing tool execution & chat loop
├── graph.py                 # Tool-calling StateGraph with tools_condition & MongoDB Saver
├── mcp_client.py            # Composio MCP connection, account resolution & tool discovery
├── checkpointer.py          # MongoDB checkpointer connection & local persistence fallback
├── state.py                 # AgentState schema with messages & add_messages reducer
├── config.py                # Environment configuration & LLM initialization (Gemini / OpenAI)
├── verify_persistence.py    # Automated test verifying restart persistence & thread isolation
├── requirements.txt         # Dependencies (langgraph, composio, langchain-mcp-adapters, etc.)
├── .env.example             # Template with GEMINI_API_KEY, MONGODB_URI, and COMPOSIO_API_KEY
├── .gitignore               # Ignores .env, .venv, local caches
└── README.md                # Documentation & architectural breakdown
```

---

## 3. Discovered MCP Tools

Rather than hardcoding tool names, the assistant connects to the Composio MCP server on startup and dynamically inspects the available tools:

* **`GITHUB_GET_A_REPOSITORY`**: Retrieves repository details (owner, stars, description, default branch, language, visibility, clone URL).
* **`GITHUB_SEARCH_REPOSITORIES`**: Searches repositories across GitHub by keywords and queries.
* **`GITHUB_LIST_REPOSITORY_ISSUES`**: Lists issues and pull requests for a given repository.

---

## 4. Getting Started

### 1. Configure Environment (`.env`)

Copy `.env.example` to `.env` and fill in the required keys:

```env
# Free Google Gemini Key (https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL_NAME=gemini-flash-lite-latest

# MongoDB Connection
MONGODB_URI=mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB_NAME=github_memory_assistant

# Composio API Key (https://app.composio.dev)
COMPOSIO_API_KEY=your_composio_api_key_here
```

### 2. Run the Application

```powershell
python main.py
```

Or specify a thread ID directly:

```powershell
python main.py --thread demo
```

---

## 5. Example Interaction

```text
Thread ID (press Enter for 'demo'): demo

[Active Thread: demo]

You: Remember my name is Ayush.
Assistant: Got it, Ayush! I will remember that.

You: Check my DisasterLAN repository.

[Uses Composio MCP GitHub tool: GITHUB_SEARCH_REPOSITORIES]
  Arguments: {"q": "DisasterLAN"}

[Uses Composio MCP GitHub tool: GITHUB_GET_A_REPOSITORY]
  Arguments: {"owner": "ayushghonge19", "repo": "DisasterLAN"}

[Uses Composio MCP GitHub tool: GITHUB_LIST_REPOSITORY_ISSUES]
  Arguments: {"state": "all", "repo": "DisasterLAN", "owner": "ayushghonge19"}

Assistant: I found your DisasterLAN repository! Here are the details:
* Repository Name: ayushghonge19/DisasterLAN
* Primary Language: JavaScript
* Visibility: Public
* Default Branch: main
* Open Issues: 0
* Last Pushed: April 1, 2026

[Exit application]

[Start application again with thread_id = demo]

[Restored 10 messages from MongoDB for thread 'demo']

You: What is my name and what repository did we check?
Assistant: Your name is Ayush, and the repository we discussed is ayushghonge19/DisasterLAN.
```

---

## 6. Conceptual Breakdown

### 1. What is MCP (Model Context Protocol)?
**MCP** is an open standard designed by Anthropic that standardizes how AI applications discover, inspect, and invoke external tools and context. Instead of each library writing bespoke API wrappers for every service, MCP defines a unified protocol for tool schemas, prompts, and resources.

### 2. MCP Client vs. MCP Server
* **MCP Client** (in our app: `MultiServerMCPClient` from `langchain-mcp-adapters`): Runs inside the AI application. It connects to the server, queries `tools/list` to discover what functions are available, and sends `tools/call` requests when the LLM requests a tool call.
* **MCP Server** (hosted by Composio): A service that implements the MCP specification. It exposes the schemas of available tools and handles the execution of incoming tool calls.

### 3. Composio's Role
Composio acts as a managed MCP server and integration platform. It handles:
* **Authentication & OAuth**: Maintains secure user credentials (such as linked GitHub OAuth accounts).
* **Tool Router**: Translates standardized MCP requests into authenticated API calls against external services (GitHub, Slack, Jira, etc.).
* **Session Isolation**: Provides per-session MCP endpoints with fine-grained tool exposure.

### 4. How the GitHub Tool Reaches GitHub
1. **Decision**: The user asks *"Check my DisasterLAN repository"*. The LangGraph LLM evaluates its bound tools and produces an `AIMessage` with a `tool_call` for `GITHUB_GET_A_REPOSITORY(owner="ayushghonge19", repo="DisasterLAN")`.
2. **MCP Dispatch**: LangGraph's `ToolNode` invokes the discovered MCP tool. The `MultiServerMCPClient` serializes the call into an MCP `tools/call` JSON-RPC message sent via Streamable HTTP to Composio's MCP server endpoint.
3. **Composio Execution**: Composio's MCP server receives the request, matches it to the user's active GitHub connection (`user_id`), attaches the authenticated OAuth token, and issues an HTTP `GET https://api.github.com/repos/ayushghonge19/DisasterLAN`.
4. **Result Propagation**: GitHub's API response is packaged by Composio into an MCP tool result and returned to the MCP client.
5. **State & Synthesis**: LangGraph appends the `ToolMessage` to the state, writes a checkpoint to MongoDB, and triggers the agent node to compose the final human-readable answer.
