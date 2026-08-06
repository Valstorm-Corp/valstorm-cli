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

import asyncio
import inspect
from collections.abc import Callable
from datetime import datetime, timezone
from functools import partial
from typing import Annotated, Any, Optional, Union
from fastapi import Depends, Request
from valstorm.auth import get_current_user
from valstorm.dependencies import add_log
from valstorm_platform.models import User
from valstorm_platform.trigger_context import TransactionScope

class BaseContext:
    """Base class for all domain-specific contexts."""

    def __init__(self, platform: 'PlatformContext'):
        """
        Initialize the base context.

        Args:
            platform (PlatformContext): The parent platform context.
        """
        pass

class RecordContext(BaseContext):
    """Context for record-related operations (CUD)."""

    async def create(self, api_name: str, input_data: Union[dict, list[dict]], async_run: bool=False, **kwargs):
        """
        Create one or more records.
        """
        pass

    async def update(self, api_name: str, input_data: Union[dict, list[dict]], async_run: bool=False, **kwargs):
        """
        Update one or more records.
        """
        pass

    async def delete(self, api_name: str, input_data: Union[dict, list[dict]], async_run: bool=False, **kwargs):
        """
        Delete one or more records.
        """
        pass

    async def calculate_rollup(self, record_id: str, api_name: str, rollup_field_api_name: str) -> float:
        """
        Dynamically calculate a rollup summary field for a specific record.
        """
        pass

class QueryContext(BaseContext):
    """Context for data querying (SQL, Mongo)."""

    async def sql(self, query: str, **kwargs):
        """
        Execute a SQL-like query.
        """
        pass

    async def mongo(self, collection: str, pipeline: list[dict], **kwargs):
        """
        Execute a MongoDB aggregation pipeline.
        """
        pass

    async def graphql(self, query: str, variables: Optional[dict]=None) -> dict:
        """
        Execute a GraphQL query against the organization's dynamic schema.
        """
        pass

    async def resolve_lookup(self, api_name: str, record_id: str) -> dict:
        """
        Resolves a record ID into a full lookup object.
        """
        pass

class SchemaContext(BaseContext):
    """Context for schema operations."""

    async def get(self, api_name: str):
        """
        Get the schema for a specific object.
        """
        pass

    async def list(self):
        """
        List all schemas available for the organization.
        """
        pass

    async def list_all(self):
        """
        Returns full schema definitions for all objects.
        """
        pass

class TaskContext(BaseContext):
    """Context for background task management."""

    async def schedule(self, name: str, func: str, run_at: datetime, data: dict, **kwargs):
        """
        Schedule a task for future execution.
        """
        pass

class FileContext(BaseContext):
    """Context for file operations (S3)."""

    async def upload(self, filename: str, body: Any, content_type: str='application/octet-stream', is_binary: bool=True, public: bool=False, **kwargs):
        """
        Upload a file to storage.
        """
        pass

    async def get_file(self, location: str):
        """
        Retrieves a file from S3 and returns its content.
        Automatically scopes to the organization's folder.
        """
        pass

    async def delete_s3(self, location: str):
        """
        Deletes a file from S3.
        Automatically scopes to the organization's folder.
        """
        pass

    async def move_s3(self, source_location: str, destination_location: str, public: bool=False):
        """
        Moves a file in S3.
        Automatically scopes both paths to the organization's folder.
        """
        pass

    async def update_acl(self, location: str, public: bool):
        """
        Updates the ACL of an S3 file.
        Automatically scopes to the organization's folder.
        """
        pass

    @property
    def s3_bucket_name(self):
        """
        Returns the S3 bucket name.
        """
        pass

class TwilioContext(BaseContext):
    """Sub-context for Twilio-specific operations."""

    async def lookup(self, phone_number: str, **kwargs):
        """
        Perform a Twilio phone number lookup.
        """
        pass

    async def delete_conversation(self, service_id: str, conversation_sid: str, **kwargs):
        """
        Delete a Twilio service conversation.
        """
        pass

    async def application_cud(self, data: dict, method: str, **kwargs):
        """
        Create, update, or delete a Twilio application.
        """
        pass

    async def _get_session(self, type: str='user', **kwargs):
        """
        Returns an authenticated Twilio session.
        type: 'user' or 'phone'
        """
        pass

    def get_callback(self, request: Request):
        """
        Wraps TwilioCallback.
        """
        pass

    @property
    def alerts(self):
        """Twilio alert helpers."""
        pass

class NotificationContext(BaseContext):
    """Sub-context for notification operations."""

    async def notify(self, notifications: list[dict], **kwargs):
        """
        Send notifications to users.
        """
        pass

    async def mark_read(self, data: Union[list[dict], dict]=None, **kwargs):
        """
        Mark notifications as read by providing a list of key/value pairs.
        """
        pass

class CommunicationContext(BaseContext):
    """Context for communication operations (SMS, Email, Notifications)."""

    def __init__(self, platform: 'PlatformContext'):
        pass

    async def send_sms(self, to_phone: str, message: str, **kwargs):
        """
        Send an SMS message via Twilio.
        """
        pass

    async def send_email(self, request: Union[Any, dict], async_run: bool=True, **kwargs):
        """
        Send an email via SendGrid.
        """
        pass

class WorkflowContext(BaseContext):
    """Context for running system functions and workflows."""

    async def run_function(self, function_name: str, kwargs: dict, **kwargs_extra):
        """
        Runs a system function.
        """
        pass

    async def run_workflow(self, workflow_id: str, data: dict, **kwargs):
        """
        Runs a workflow by its ID.
        """
        pass

    async def safe_execute(self, func: Callable, *args, **kwargs):
        """
        Safely executes an async function with error handling and logging.
        """
        pass

class MetadataContext(BaseContext):
    """Context for organization metadata and settings."""

    async def get_config(self, api_name: str):
        """
        Get organization configuration/settings by name.
        """
        pass

class SalesforceContext(BaseContext):
    """Context for Salesforce integration operations."""

    async def query(self, query: str, **kwargs):
        """
        Execute a SOQL query against Salesforce.
        """
        pass

    async def create(self, api_name: str, data: Union[dict, list[dict]], **kwargs):
        """
        Create record(s) in Salesforce.
        """
        pass

    async def update(self, data: list[dict], **kwargs):
        """
        Update record(s) in Salesforce.
        """
        pass

class GoogleContext(BaseContext):
    """Context for Google Workspace operations."""

    async def _get_workspace(self, **kwargs):
        """
        Returns an initialized GoogleWorkspaceService instance.
        """
        pass

    async def fetch_drive_files_concurrently(self, file_ids: list[str]):
        """
        Concurrently fetches file metadata for multiple IDs.
        """
        pass

    async def export_drive_file(self, file_id: str, mime_type: str, base64_encode: bool=True, **kwargs):
        pass

    async def move_drive_file(self, file_id: str, target_folder_id: str):
        """
        Moves a Google Drive file to a new target folder.
        """
        pass

    async def create_drive_folder(self, name: str, parent_id: str=None):
        """
        Creates a new Google Drive folder.
        """
        pass

    async def upload_drive_file(self, file_name: str, file_content: bytes, mime_type: str, parent_id: str=None):
        """
        Uploads a file to Google Drive.
        """
        pass

    async def get_drive_file_content(self, file_id: str):
        """
        Returns the content of a Google Drive file.
        Automatically handles exporting Google Workspace documents to text/plain.
        """
        pass

    async def modify_gmail_labels(self, message_id: str, add_label_ids: list[str]=None, remove_label_ids: list[str]=None):
        """
        Modifies the labels on the specified Gmail message.
        """
        pass

    async def modify_gmail_thread_labels(self, thread_id: str, add_label_ids: list[str]=None, remove_label_ids: list[str]=None):
        """
        Modifies the labels on the specified Gmail thread.
        """
        pass

    async def send_email(self, data: Union[dict, Any], **kwargs):
        """
        Sends an email using standard Gmail integration, routing automatically.
        """
        pass

class AgentContext(BaseContext):
    """Context for inter-agent communication."""

    async def call(self, agent_id: str, message: str, **kwargs):
        """
        Delegates a task to another AI Agent and returns the result.
        
        Args:
            agent_id (str): The ID of the target agent to call.
            message (str): The instruction or message to send to the agent.
        """
        pass
from .stripe_context import StripeContext
from valstorm_platform.microsoft_context import MicrosoftContext

class IntegrationContext(BaseContext):
    """Context grouping all external integrations."""

    def __init__(self, platform: 'PlatformContext'):
        """
        Initialize integration sub-contexts.
        """
        pass

class UtilsContext(BaseContext):
    """General platform utilities."""

    def aware_datetime(self, dt: Union[datetime, str, None]) -> Optional[datetime]:
        pass

    def iso_datetime(self, dt: datetime) -> str:
        pass

    def phone_formatter(self, phone: Any) -> dict:
        pass

    def get_phone_fields(self, schema: dict) -> list[str]:
        pass

    def get_email_fields(self, schema: dict) -> list[str]:
        pass

    def render_template(self, template_string: str, data: dict[str, Any]) -> str:
        pass

    async def html_to_md(self, html: str, strip_tags: Optional[list[str]]=None) -> str:
        """Converts HTML to Markdown."""
        pass

    async def md_to_html(self, md: str) -> str:
        """Converts Markdown to HTML."""
        pass

    def clean_html(self, html: str) -> str:
        """Cleans HTML for markdown conversion."""
        pass

    def dump_data(self, data: Any) -> Any:
        pass

class FormulaContext(BaseContext):
    """Context for formula evaluation."""

    def calculate(self, formula: str, context: dict[str, Any]) -> Any:
        """
        Calculates a formula given a context.
        """
        pass

    async def evaluate_record(self, record: dict[str, Any], schema_api_name: str) -> dict[str, Any]:
        """
        Evaluates all formula fields for a record based on its schema.
        """
        pass

class RollupContext(BaseContext):
    from valstorm.rollup_service import RollupService
    rollup_service: RollupService = RollupService()

    async def evaluate_rollups(self, records: list[dict[str, Any]], schema: dict[str, Any], **kwargs) -> list[dict[str, Any]]:
        """
        Evaluates rollup fields for a list of records based on the provided schema.
        """
        pass

class ExceptionContext(BaseContext):
    """Access to platform-specific exceptions."""

    @property
    def S3ClientError(self):
        pass
from .parser_context import ParserContext

class PlatformContext:
    """
    Unified facade for all Valstorm platform operations.
    """

    def __init__(self, current_user: User, transaction_scope: Optional[Any]=None):
        """
        Initialize the platform context.
        """
        pass

    @property
    def models(self):
        """
        Provides access to Valstorm models.
        """
        pass

    def log(self, message: str, level: str='info'):
        """
        Centralized logging.
        """
        pass

    async def run_and_wait(self, func: Callable, *args, **kwargs) -> Any:
        """
        Safely executes a function with error handling and logging.
        """
        pass

    async def run_task(self, func: Callable, *args, **kwargs) -> Any:
        """
        Runs a function as a background task and returns the task ID.
        """
        pass

async def get_platform_context(current_user: Annotated[User, Depends(get_current_user)]) -> PlatformContext:
    """
    FastAPI dependency for injecting PlatformContext into routes.
    """
    pass
