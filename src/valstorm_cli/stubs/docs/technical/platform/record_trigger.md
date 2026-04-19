# Valstorm Record Triggers

Record triggers allow you to inject custom automation into the standard Create, Update, and Delete (CUD) API request lifecycle. Modern Valstorm triggers leverage the **Platform Context**, a unified API that provides safe, high-level access to database operations, integrations, and utility functions.

---

## Trigger Lifecycle Contexts

Triggers execute in one of three stages of the request lifecycle:

*   **Before**: Runs *synchronously* before the database operation. Use this for data validation (raising `HTTPException` to block) or modifying data in-place by updating the records in `context.new_map`.
*   **After**: Runs *synchronously* after the database commit but before the API response is sent. Ideal for immediate side effects that depend on the record being successfully saved.
*   **Async**: Runs *asynchronously* in a background worker. Perfect for heavy lifting like external API syncs, long-running calculations, or non-critical notifications.

---

## The Trigger Structure

Every trigger file must implement an `execute` function.

```python
from valstorm_platform.trigger_context import RecordTriggerContext

async def execute(context: RecordTriggerContext):
    # Your logic here
    pass
```

### The `RecordTriggerContext` Object

The `context` object provides everything needed to process the batch:

| Property | Type | Description |
| :--- | :--- | :--- |
| `context.user` | `User` | The authenticated user performing the action. |
| `context.new_map` | `dict` | `{id: record}` map of the **new** state. |
| `context.old_map` | `dict` | `{id: record}` map of the **previous** state (empty on Create). |
| `context.trigger_context` | `set` | Indicates the phase and action (e.g., `{'Before', 'Update'}`). |
| `context.log(msg, level)` | `method` | Standardized logging (`'info'`, `'warning'`, `'error'`). |
| `context.is_changed(id, field)`| `method` | **Preferred** way to check if a specific field was modified. |

---

## Platform Context API Modules

The `context` object exposes several namespaces to interact with the Valstorm ecosystem:

### 1. Data Operations (`context.records` & `context.query`)
*   **`await context.records.create(api_name, input_data)`**: Create one or many records.
*   **`await context.records.update(api_name, input_data)`**: Update one or many records.
*   **`await context.records.delete(api_name, input_data)`**: Delete one or many records.
*   **`await context.query.sql(query, bypass_cache=True)`**: Execute SQL-like queries against organization data.

### 2. Metadata & Config (`context.metadata`)
*   **`await context.metadata.get_config(api_name)`**: Fetches organization-specific App Metadata (e.g., "B2B Sales Config"). Returns a dictionary.

### 3. Communications (`context.communications`)
*   **`await context.communications.notifications.notify(list[SendNotificationSetting])`**: Send push/in-app notifications.
*   **`await context.communications.notifications.mark_read(data=list[dict])`**: Mark notifications as read using a list of filters (e.g., `{'record_id': '...'}`).

### 4. Integrations (`context.integrations`)
*   **`context.integrations.salesforce`**: `query()`, `create()`, and `update()` records in the linked Salesforce instance.
*   **`context.integrations.google`**: `fetch_drive_files_concurrently(file_ids)` and other Workspace helpers.

### 5. Task Execution (`context.tasks`)
*   **`await context.tasks.run_function(name, kwargs)`**: Execute a system function.
*   **`await context.tasks.run_workflow(workflow_id, data)`**: Trigger a specific automation workflow.

### 6. Utilities (`context.utils`)
*   **`context.utils.phone_formatter(phone)`**: Standardizes phone strings.
*   **`await context.utils.html_to_md(html)`**: Safely converts HTML content to Markdown.
*   **`context.utils.get_phone_fields(schema)`**: Identifies which fields in an object schema are phone types.

---

## Common Patterns

### Conditional Logic (Detecting Changes)
Always use `context.is_changed()` instead of manual equality checks. It handles deep comparisons (e.g., nested Address objects), type normalization (Dict vs Pydantic Model), and treats `None` and missing keys as equivalent.

```python
async def execute(context: RecordTriggerContext):
    if 'Update' in context.trigger_context:
        for record in context.new_map.values():
            # ONLY runs if the address was actually modified in the payload
            if context.is_changed(record['id'], 'property_address'):
                # Perform address-specific logic
                pass
```

### In-Place Modification (Before context)
In a "Before" trigger, you don't need to call `update()`. Simply modify the objects in `new_map`.

```python
async def execute(context: RecordTriggerContext):
    if 'Before' in context.trigger_context:
        for record in context.new_map.values():
            if not record.get('full_name'):
                record['full_name'] = f"{record.get('first')} {record.get('last')}"
```

### Side Effects with Configuration
Fetch metadata to drive dynamic logic.

```python
async def execute(context: RecordTriggerContext):
    config = await context.metadata.get_config("Lead Automation")
    if not config or not config.get('active'):
        return

    if 'After' in context.trigger_context:
        # Create a related record based on config mapping
        pass
```

### Error Handling
*   In **Before** triggers: Raising `HTTPException` will block the DB transaction and return the error to the user.
*   In **After/Async** triggers: Errors should be logged via `context.log` to prevent interrupting the request or background worker.

---

## Pro-Tips & Best Practices

1.  **Leverage `context.is_changed()`**: Avoid manual diffing like `if new_val != old_val`. `is_changed()` is safer because it explicitly checks the update payload and is resilient to normalization differences (e.g., a field being `None` in one object but missing in another).
2.  **Never call `update()` in a Before trigger**: Modifying the dictionary in `context.new_map` directly is the most efficient way to change data before it hits the database. Calling `context.records.update` inside a Before trigger can cause infinite loops or unnecessary database overhead.
3.  **Standardized Logging**: Avoid using standard `print()` statements. Use `context.log("message", level="info")` to ensure your logs are captured in the Valstorm execution history and correctly attributed to the specific trigger run.
4.  **Validate with Exceptions**: To prevent a record from being saved based on custom logic (e.g., checking a credit score threshold), `from fastapi import HTTPException` and raise it within a 'Before' block. This ensures a clean rollback and provides immediate feedback to the UI.
5.  **Batch Processing**: Always write your triggers to handle multiple records. Even if a single record is updated via the UI, the API often processes records in batches. Iterate through `context.new_map.values()` to ensure your logic scale correctly.
6.  **Check Context Early**: Use `if 'Before' in context.trigger_context:` to guard your logic. Many trigger files are registered for multiple phases; explicit checks prevent logic from running in the wrong stage of the lifecycle.

