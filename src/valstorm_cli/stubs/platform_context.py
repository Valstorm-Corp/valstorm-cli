# VALSTORM SDK STUBS
# This file is auto-generated. Do not modify implementation.
# These stubs provide type hints for local development.

from datetime import datetime
from typing import Optional, Annotated, Any, List, Dict, Union, Callable, Set

# Mock types for hinting
class TransactionScope: pass
class TriggerTransaction: pass
class PlatformContext: pass
class Request: pass

from datetime import datetime, timezone
from typing import Optional, Annotated, Any, List, Dict, Union, Callable
from fastapi import Depends, HTTPException, Request
from .trigger_context import TransactionScope
from .models import User

class BaseContext:
    """Base class for all domain-specific contexts."""

    def __init__(self, platform: 'PlatformContext'):
        pass

class RecordContext(BaseContext):
    """Context for record-related operations (CUD)."""

    def UpdateOne(self, filter: Dict[str, Any], update: Dict[str, Any], upsert: bool=False):
        pass

    async def bulk_write(self, api_name: str, operations: List[Any], **kwargs):
        """Perform a bulk write operation on a collection."""
        pass

    async def create(self, api_name: str, input_data: Union[dict, list[dict]], async_run: bool=False, **kwargs):
        """Create one or more records."""
        pass

    async def update(self, api_name: str, input_data: Union[dict, list[dict]], async_run: bool=False, **kwargs):
        """Update one or more records."""
        pass

    async def delete(self, api_name: str, input_data: Union[dict, list[dict]], async_run: bool=False, **kwargs):
        """Delete one or more records."""
        pass

class QueryContext(BaseContext):
    """Context for data querying (SQL, Mongo)."""

    async def sql(self, query: str, **kwargs):
        """Execute a SQL-like query."""
        pass

    async def mongo(self, collection: str, pipeline: list[dict], **kwargs):
        """Execute a MongoDB aggregation pipeline."""
        pass

    async def resolve_lookup(self, api_name: str, record_id: str) -> dict:
        """Resolves a record ID into a full lookup object."""
        pass

class SchemaContext(BaseContext):
    """Context for schema operations."""

    async def get(self, api_name: str):
        """Get the schema for a specific object."""
        pass

    async def list(self):
        """List all schemas available for the organization."""
        pass

    async def list_all(self):
        """Returns full schema definitions for all objects."""
        pass

class TaskContext(BaseContext):
    """Context for background task management."""

    async def schedule(self, name: str, func: str, run_at: datetime, data: dict, **kwargs):
        """Schedule a task for future execution."""
        pass

class FileContext(BaseContext):
    """Context for file operations (S3)."""

    async def upload(self, path: str, data: Any, **kwargs):
        """Upload a file to storage."""
        pass

    def delete_s3(self, location: str):
        pass

    @property
    def s3_client(self):
        pass

    @property
    def s3_bucket_name(self):
        pass

class TwilioContext(BaseContext):
    """Sub-context for Twilio-specific operations."""

    async def lookup(self, phone_number: str, **kwargs):
        """Perform a Twilio phone number lookup."""
        pass

    async def delete_conversation(self, service_id: str, conversation_sid: str, **kwargs):
        """Delete a Twilio service conversation."""
        pass

    async def application_cud(self, data: dict, method: str, **kwargs):
        """Create, update, or delete a Twilio application."""
        pass

    async def get_session(self, type: str='user', **kwargs):
        """Returns an authenticated Twilio session.
type: 'user' or 'phone'"""
        pass

    def get_callback(self, request: Request):
        pass

    @property
    def alerts(self):
        pass

class NotificationContext(BaseContext):
    """Sub-context for notification operations."""

    async def notify(self, notifications: List[Dict], **kwargs):
        """Send notifications to users."""
        pass

    async def mark_read(self, data: Union[list[dict], dict]=None, **kwargs):
        """Mark notifications as read by providing a list of key/value pairs."""
        pass

class CommunicationContext(BaseContext):
    """Context for communication operations (SMS, Email, Notifications)."""

    def __init__(self, platform: 'PlatformContext'):
        pass

    async def send_sms(self, to_phone: str, message: str, **kwargs):
        """Send an SMS message via Twilio."""
        pass

    async def send_email(self, request: Union[Any, dict], async_run: bool=True, **kwargs):
        """Send an email via SendGrid."""
        pass

class WorkflowContext(BaseContext):
    """Context for running system functions and workflows."""

    async def run_function(self, function_name: str, kwargs: dict, **kwargs_extra):
        """Runs a system function."""
        pass

    async def run_workflow(self, workflow_id: str, data: dict, **kwargs):
        """Runs a workflow by its ID."""
        pass

    async def safe_execute(self, func: Callable, *args, **kwargs):
        """Safely executes an async function with error handling and logging."""
        pass

class MetadataContext(BaseContext):
    """Context for organization metadata and settings."""

    async def get_config(self, api_name: str):
        """Get organization configuration/settings by name."""
        pass

class SalesforceContext(BaseContext):
    """Context for Salesforce integration operations."""

    async def query(self, query: str, **kwargs):
        """Execute a SOQL query against Salesforce."""
        pass

    async def create(self, api_name: str, data: Union[dict, list[dict]], **kwargs):
        """Create record(s) in Salesforce."""
        pass

    async def update(self, data: list[dict], **kwargs):
        """Update record(s) in Salesforce."""
        pass

class GoogleContext(BaseContext):
    """Context for Google Workspace operations."""

    async def get_workspace(self, **kwargs):
        """Returns an initialized GoogleWorkspace instance."""
        pass

    async def fetch_drive_files_concurrently(self, file_ids: List[str]):
        """Concurrently fetches file metadata for multiple IDs."""
        pass

class AgentContext(BaseContext):
    """Context for inter-agent communication."""

    async def call(self, agent_id: str, message: str, **kwargs):
        """Delegates a task to another AI Agent and returns the result.

Args:
    agent_id (str): The ID of the target agent to call.
    message (str): The instruction or message to send to the agent."""
        pass

class MicrosoftContext(BaseContext):
    """Context for Microsoft 365 operations."""

    async def get_event_mapper(self):
        """Returns an initialized MicrosoftEventToEventMapper-like interface."""
        pass

class IntegrationContext(BaseContext):
    """Context grouping all external integrations."""

    def __init__(self, platform: 'PlatformContext'):
        pass

class UtilsContext(BaseContext):
    """General platform utilities."""

    def aware_datetime(self, dt: Union[datetime, str, None]) -> Optional[datetime]:
        pass

    def iso_datetime(self, dt: datetime) -> str:
        pass

    def phone_formatter(self, phone: Any) -> dict:
        pass

    def get_phone_fields(self, schema: dict) -> List[str]:
        pass

    async def html_to_md(self, html: str) -> str:
        pass

    def dump_data(self, data: Any) -> Any:
        pass

class ExceptionContext(BaseContext):
    """Access to platform-specific exceptions."""

    @property
    def S3ClientError(self):
        pass

class PlatformContext:
    """
    Unified facade for all Valstorm platform operations.
    """

    def __init__(self, current_user: User, transaction_scope: Optional[Any]=None):
        """Initialize the platform context."""
        self.user = None
        self.records: RecordContext = None
        self.query: QueryContext = None
        self.schemas: SchemaContext = None
        self.tasks: TaskContext = None
        self.files: FileContext = None
        self.communications: CommunicationContext = None
        self.metadata: MetadataContext = None
        self.integrations: IntegrationContext = None
        self.workflows: WorkflowContext = None
        self.agents: AgentContext = None
        self.utils: UtilsContext = None
        self.exceptions: ExceptionContext = None

    @property
    def models(self):
        pass

    def log(self, message: str, level: str='info'):
        pass

async def get_platform_context(current_user: Annotated[User, Depends(get_current_user)]) -> PlatformContext:
    """FastAPI dependency for injecting PlatformContext into routes."""
    pass