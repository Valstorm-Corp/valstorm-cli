# PlatformContext

The `PlatformContext` is a unified facade for all Valstorm platform operations. It provides a standardized way to interact with various platform services such as database operations, schema management, communication, and external integrations.

## Overview

The `PlatformContext` class aggregates several domain-specific contexts, each handling a particular aspect of the platform. It is designed to be injected into FastAPI routes or used within system functions to provide a consistent execution environment.

### Initialization

```python
from valstorm_platform.platform_context import PlatformContext

# current_user is a valstorm.models.User object
platform = PlatformContext(current_user)
```

In FastAPI routes, use the dependency:

```python
from valstorm_platform.platform_context import get_platform_context, PlatformContext

@router.get("/my-route")
async def my_route(ctx: PlatformContext = Depends(get_platform_context)):
    # Use ctx here
    ...
```

## Sub-Contexts

### 1. `records` (RecordContext)
Handles Create, Update, and Delete (CUD) operations on MongoDB collections. Supports both synchronous and asynchronous execution (via Celery).

- `create(api_name, input_data, async_run=False, **kwargs)`
- `update(api_name, input_data, async_run=False, **kwargs)`
- `delete(api_name, input_data, async_run=False, **kwargs)`
- `bulk_write(api_name, operations, **kwargs)`

### 2. `query` (QueryContext)
Provides methods for querying data using SQL-like syntax or MongoDB aggregation pipelines.

- `sql(query, **kwargs)`: Executes a SQL-like query.
- `mongo(collection, pipeline, **kwargs)`: Executes a MongoDB aggregation pipeline.
- `resolve_lookup(api_name, record_id)`: Resolves a record ID into a full lookup object.

### 3. `schemas` (SchemaContext)
Provides access to object schemas.

- `get(api_name)`: Get the schema for a specific object.
- `list()`: List all simplified schemas for the organization.
- `list_all()`: Get full schema definitions for all objects.

### 4. `communications` (CommunicationContext)
Aggregates communication services like Twilio and Notifications.

- `send_sms(to_phone, message, **kwargs)`
- `twilio`: Sub-context for advanced Twilio operations (lookup, conversation management, etc.).
- `notifications`: Sub-context for sending and managing in-app notifications.

### 5. `integrations` (IntegrationContext)
Provides unified access to external integrations.

- `salesforce`: Query, create, and update records in Salesforce.
- `google`: Access Google Workspace services (Drive, etc.).
- `microsoft`: Microsoft 365 operations and event mapping.

### 6. `workflows` (WorkflowContext)
Executes system functions and automation workflows.

- `run_function(function_name, kwargs, **kwargs_extra)`
- `run_workflow(workflow_id, data, **kwargs)`
- `safe_execute(func, *args, **kwargs)`: Safely executes an async function with logging.

### 7. `files` (FileContext)
Handles file operations, primarily using Amazon S3.

- `upload(path, data, **kwargs)`
- `delete_s3(location)`
- `s3_client`: Direct access to the S3 client.

### 8. `utils` (UtilsContext)
General platform utilities for data formatting and parsing.

- `aware_datetime(dt)`: Ensures a datetime object is timezone-aware.
- `phone_formatter(phone)`: Formats phone numbers.
- `html_to_md(html)`: Converts HTML to Markdown.

### 9. `metadata` (MetadataContext)
Accesses organization-level settings and configuration.

- `get_config(api_name)`: Returns organization settings.

## Direct Access

- `platform.db`: Provides direct access to the organization's MongoDB database.
- `platform.log(message, level="info")`: Centralized logging via `valstorm.dependencies.add_log`.
