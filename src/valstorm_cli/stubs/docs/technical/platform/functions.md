# Valstorm Function System

The Valstorm Function System allows you to write, manage, and execute custom Python code within the platform. Functions are versatile building blocks that can be used for complex data processing, integrations, AI orchestrations, and scheduled tasks.

## Overview

A "Function" in Valstorm is a snippet of Python code executed securely in a sandboxed environment. Every function must define an asynchronous `execute` method that receives a `PlatformContext` object, giving it unified access to database operations, external integrations, and communication tools.

### Key Capabilities
- **Database Operations:** Full CRUD and querying (SQL and MongoDB pipelines).
- **Communication:** Sending SMS, emails, and UI notifications.
- **Integrations:** Access to Google Workspace, Salesforce, Twilio, and Microsoft integrations.
- **Workflows:** Triggering other automations or calling other functions.
- **Scheduling:** Functions can be executed dynamically or on a schedule via Scheduled Items.

---

## Writing a Function

### Basic Structure

Every function must have an `async def execute` method. The `PlatformContext` is injected into this method, alongside any custom arguments passed by the invoker.

```python
from valstorm_platform.platform_context import PlatformContext

async def execute(platform: PlatformContext, **kwargs):
    """
    Example function that creates a task.
    """
    try:
        # Retrieve custom arguments
        lead_id = kwargs.get('lead_id')
        task_name = kwargs.get('task_name', 'Default Task')

        if not lead_id:
            platform.log("Missing lead_id", "error")
            return {"status": "error", "message": "lead_id is required"}

        # Use the platform API to interact with the system
        await platform.records.create('task', {
            "name": task_name,
            "status": "Not Started",
            "related_to": {
                "id": lead_id,
                "schema": "lead"
            }
        })

        platform.log(f"Successfully created task for lead {lead_id}", "info")
        return {"status": "success"}

    except Exception as e:
        platform.log(f"Error in my_function: {str(e)}", "error")
        return {"status": "error", "message": str(e)}
```

### The `PlatformContext`

The `PlatformContext` object is your gateway to Valstorm's internal APIs. It provides a clean, unified interface.

*   `platform.records`: `.create()`, `.update()`, `.delete()` records.
*   `platform.query`: `.sql()` for standard querying, `.mongo()` for complex aggregation pipelines.
*   `platform.communications`: Send SMS (`.send_sms()`), UI notifications (`.notifications.notify()`).
*   `platform.workflows`: Trigger workflows (`.run_workflow()`) or other functions (`.run_function()`).
*   `platform.integrations`: Access third-party services (e.g., `platform.integrations.google`, `platform.integrations.salesforce`).
*   `platform.metadata`: Access org-specific settings (`.get_config()`).
*   `platform.log()`: Write to the system logs.
*   `platform.user`: The current executing `User` object.

---

## Invoking Functions

Functions can be invoked from multiple places within the Valstorm ecosystem.

### 1. Via Record Triggers

You can call a function from within a V2 Record Trigger using the `platform.workflows.run_function()` method.

```python
async def execute(context: RecordTriggerContext) -> None:
    # Trigger a custom function asynchronously
    await context.workflows.run_function(
        function_name="my_custom_function.py",
        kwargs={
            "lead_id": context.new_map["some_id"]["id"]
        }
    )
```

### 2. Via Automations (Workflows)

Automations (Flow Builder) can include a "Function Node" that executes a specific function. The node can pass dynamic variables from the automation's context into the function as `kwargs`.

### 3. Via API Request

Functions can be triggered directly via the Valstorm API using the `/v1/automation/function` endpoint.

**POST** `/v1/automation/function`
```json
{
  "function_name": "my_custom_function.py",
  "inputs": {
    "lead_id": "12345",
    "task_name": "Follow up call"
  }
}
```

### 4. Via Scheduled Items

You can create a `scheduled_item` record to execute a function at a specific date and time.

```python
# Creating a scheduled execution
await platform.records.create('scheduled_item', {
    "name": "Run My Function Tomorrow",
    "run_date_time": "2026-04-16T10:00:00Z",
    "status": "Queued",
    "function": {
        "id": "function-record-id",
    },
    "data": {
        "lead_id": "12345"
    }
})
```

---

## Security & Execution Context

- **Sandboxing**: Functions are loaded and executed inside a `FunctionProxy` that ensures AST (Abstract Syntax Tree) validation to prevent malicious operations.
- **Timeouts**: Execution is wrapped in a strict timeout to prevent long-running loops from blocking system resources.
- **Multi-Tenancy**: The `PlatformContext` is strictly bound to the `current_user` and their organization. Functions inherently cannot access data outside their tenant.
