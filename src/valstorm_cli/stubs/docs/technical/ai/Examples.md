# AI Agent Examples

This page provides practical examples of how to interact with Valstorm AI Agents and what tools they might use for different requests.

## Data Exploration

### 1. Understanding Object Structures
**User Request**: "What does the `lead` object look like?" or "What fields are on the `lead` table?"
**AI Action**: The agent calls `schemas_get(api_name='lead')`.
**Result**: The agent explains the fields and types available on the `lead` object.

### 2. Querying Data
**User Request**: "Show me leads created today."
**AI Action**: The agent calls `query_mongo` with a pipeline filtering by `created_date`.
**Result**: A list or summary of leads created today.

### 3. Multi-step reasoning
**User Request**: "Find all leads where the 'Status' is 'New'. If you don't know the status field name, check the schema first."
**AI Action**: 
1. The agent calls `schemas_get` for `lead`.
2. After receiving the schema, it identifies the status field (e.g., `status__c`).
3. It then calls `query_mongo` with the correct field name.

## Record Management

### 1. Single Record Update
**User Request**: "Update the lead with ID `0fb95bf9-27a2-4930-80f7-f482d612fa5c` to the status of `Nurture`."
**AI Action**: The agent calls `records_update` with the specified ID and status value.

### 2. Bulk Update
**User Request**: "Update the lead records with IDs `0fb95bf9...` and `a29adb70...` to the status of `Engaged`."
**AI Action**: The agent calls `records_update` with a list of update objects containing the IDs and the new status.

### 3. Record Creation
**User Request**: "Create a new lead for John Doe at Acme Corp with email john@acme.com."
**AI Action**: The agent calls `records_create` for the `lead` object with the provided data.

## Communication

### 1. Sending SMS
**User Request**: "Send an SMS to John at +1234567890 saying 'Your lead has been updated'."
**AI Action**: The agent calls `communications_send_sms`.

## Tips for Better Results

- **Context is Key**: If you have many objects, tell the agent which one to look at.
- **Explicit IDs**: When asking for updates, providing the record ID directly is the most reliable method.
- **Verify Schema**: If an agent struggles to find a field, ask it to "Check the schema for [Object]" first.
