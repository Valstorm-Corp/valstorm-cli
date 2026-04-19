# AI Tool Integration

The Valstorm AI system uses a dynamic approach to expose platform capabilities and custom logic to the LLM. This is handled by two main bridges: `PlatformBridge` and `ToolBridge`.

## PlatformBridge

The `PlatformBridge` uses Python introspection to automatically turn methods of the `PlatformContext` into tool definitions that Gemini can understand.

### How it works

1. **Introspection**: It iterates through the sub-contexts of `PlatformContext` (e.g., `records`, `query`).
2. **Definition Generation**: For each method, it reads the signature and docstring.
   - **Parameters**: Annotations are mapped to JSON Schema types.
   - **Description**: The docstring is parsed to provide the tool description.
3. **Naming**: Tools are named using the pattern `{context}_{method}` (e.g., `records_create`, `query_sql`).
4. **Execution**: When the LLM calls a tool, the bridge dispatches it to the correct method on the `PlatformContext`.

### Supported Types
The bridge handles mapping Python types to JSON Schema:
- `str` -> `string`
- `int` -> `integer`
- `float` -> `number`
- `bool` -> `boolean`
- `list` -> `array`
- `dict` / `BaseModel` -> `object`

## ToolBridge

The `ToolBridge` is a higher-level aggregator that builds the final toolset for an agent. It supports several types of tools:

### 1. Platform Tools
Standard platform operations provided by `PlatformBridge`.

### 2. Custom Functions
Dynamically loaded Python modules stored in the system. The `ToolBridge` introspects the `execute` method of these modules to build tool definitions.
- **Manifest Support**: Developers can provide an explicit `__tool_manifest__` in the module for precise control over the tool definition.

### 3. Automation Workflows
Enables the AI to trigger existing automation workflows.
- **Input Detection**: It inspects the "Start" or "Webhook" node of a workflow to determine required arguments.

## Tool Configuration (AiAgent)

In the `ai_agent` configuration, allowed tools are defined in the `allowed_tools` list. Each entry can be:
- **String**: A shortcut ID for common platform tools (e.g., `"get_schema"`).
- **Object**: A detailed configuration specifying the type and ID of the tool.

```json
{
  "allowed_tools": [
    "get_schema",
    {
      "type": "platform",
      "id": "query_sql",
      "requires_confirmation": true
    },
    {
      "type": "function",
      "id": "my_custom_function_id"
    }
  ]
}
```

## Security & Authorization

- **Access Control**: Agents can be restricted to specific user roles.
- **Confirmation**: High-risk tools (like `records_delete` or custom financial functions) can be marked with `requires_confirmation: true`, forcing the system to pause and ask for user approval before execution.
