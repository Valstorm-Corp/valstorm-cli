# AI API Reference

The AI subsystem exposes several endpoints for interacting with agents and tools. All routes are prefixed with `/v1/ai`.

## Routes

### `POST /agent/chat`
The main endpoint for interacting with an AI Agent or starting a general chat.

**Request Body (`ChatRequest`):**
- `user_message` (string): The message from the user.
- `agent_id` (string, optional): The ID of the specific AI Agent to use.
- `ai_chat` (string, optional): The ID of an existing chat session. If omitted, a new session is created.
- `model` (string, optional): Override the model to use (for general chat).
- `system_prompt` (string, optional): Override the system prompt (for general chat).
- `allowed_tools` (list[string], optional): List of tool IDs to allow (for general chat).

**Response:**
- `ai_chat` (string): The ID of the chat session.
- `reply` (string): The model's response text.
- `status` (string): `"completed"` or `"needs_confirmation"`.
- `tool_name` (string, optional): The name of the tool requesting confirmation.
- `tool_args` (dict, optional): The arguments for the tool requesting confirmation.

---

### `POST /agent/confirm`
Used to approve or deny a tool execution that requested confirmation.

**Request Body (`ConfirmToolRequest`):**
- `ai_chat` (string): The ID of the chat session.
- `approved` (boolean): Whether the user approved the tool execution.
- `agent_id` (string, optional): The ID of the agent.

**Response:**
Same as `/agent/chat`, resuming the execution loop.

---

### `GET /tools`
Returns the list of all available platform tools that the AI can potentially use.

---

### `GET /agent/{agent_id}/tools`
Returns the list of tool definitions configured for a specific agent.

## Utilities (`utils.py`)

- `sanitize_mongo_pipeline(pipeline)`: Recursively fixes common LLM formatting errors in MongoDB pipelines (e.g., stripping quotes from keys like `$match`).
- `serialize_chat_history(history)` / `deserialize_chat_history(data)`: Converts between Google GenAI `Content` objects and JSON-serializable dictionaries.

## Testing

The AI subsystem includes integration tests and bridge tests:
- `ai_integration_test.py`: Tests the full chat loop and persistence.
- `platform_bridge_test.py`: Verifies that `PlatformContext` methods are correctly mapped to tool definitions.
- `platform_context_test.py`: Tests the core `PlatformContext` functionality.

To run tests:
```bash
pytest apps/api/app/valstorm_platform/platform_context_test.py
pytest apps/api/app/ai/platform_bridge_test.py
pytest apps/api/app/ai/ai_integration_test.py
```
