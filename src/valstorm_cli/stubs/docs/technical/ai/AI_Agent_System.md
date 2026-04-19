# AI Agent System

The Valstorm AI Agent system provides a framework for building and deploying specialized AI assistants that can interact with the platform using tools. It integrates Google Gemini LLM with the `PlatformContext` to enable the model to query data, manage records, and trigger workflows.

## Core Components

### 1. `AiAgent` (`ai_agent.py`)
Responsible for loading and managing the context of a specific AI Agent. 
- Fetches configuration from the database (system prompt, model, allowed tools).
- Handles access control checks based on user roles.

### 2. `PlatformBridge` (`platform_bridge.py`)
Bridges the `PlatformContext` to the LLM. 
- Introspects `PlatformContext` methods and generates Gemini-compatible tool definitions (JSON Schema).
- Dispatches tool calls from the LLM back to the platform.

### 3. `ToolBridge` (`tool_bridge.py`)
Aggregates various tool sources for an agent.
- Combines platform tools, custom system functions, and automation workflows into a unified toolset.

### 4. `llm_functions.py`
Contains the core logic for the AI interaction loop (ReAct loop).
- `chat_with_data`: Entry point for multi-turn conversations.
- `execute_tool_cycle`: Manages the loop where the model thinks, calls tools, and receives results.
- Handles message persistence to the database.

## Interaction Flow

1. **Request**: The user sends a message via `/v1/ai/agent/chat`.
2. **Context Loading**: The system loads the agent configuration and existing chat history from the database.
3. **Tool Generation**: Available tools are dynamically generated as JSON schemas.
4. **LLM Call**: Gemini is called with the history and tool definitions.
5. **Tool Execution**: 
   - If Gemini requests a tool call, `PlatformBridge` executes it.
   - If the tool requires confirmation, the loop pauses and returns a `needs_confirmation` status.
6. **Persistence**: Every message (user, model, tool call, tool result) is saved to the `ai_chat_message` collection.
7. **Response**: The final answer is returned to the user.

## Features

- **Multi-tenant Isolation**: Chat history and tool execution are strictly scoped to the user's organization.
- **Persistent Chat**: Conversations are saved, allowing for multi-turn interactions over time.
- **Human-in-the-loop**: Specific tools can be configured to require user approval before execution.
- **Dynamic Tools**: Tools are generated automatically from Python code annotations and docstrings.
- **General Chat**: Support for AI interactions without a specific agent configuration.
