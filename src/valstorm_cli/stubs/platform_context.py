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
from typing import Annotated, Any, Optional, Union, List, Dict
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
from valstorm_platform.twilio_context import TwilioContext

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

    async def hydrate_batch(self, ids: list[str]) -> dict:
        """
        Batch resolves prefixed IDs (e.g. ['cont_123', 'task_456']) into their display names and schemas.
        """
        pass

    async def merge(self, master_id: str, duplicate_ids: Union[str, list[str]], schema_api_name: Optional[str]=None, field_overrides: Optional[dict]=None) -> Any:
        """
        Merge duplicate record(s) into master record and re-link related lookup references.
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

    async def create(self, data: dict, save: bool=True) -> Any:
        """
        Create a new custom object schema.
        """
        pass

    async def create_field(self, field_data: dict, save: bool=True) -> Any:
        """
        Create a field in an existing schema.
        """
        pass

    async def delete_field(self, object_id: str, field_name: str) -> Any:
        """
        Delete a field from a schema.
        """
        pass

    async def delete(self, schema_id: str) -> Any:
        """
        Delete a custom schema.
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
    """Context for file operations (S3 and VFS)."""

    async def get_vfs_file(self, file_id: str) -> dict:
        """
        Loads full file metadata and inline text content (if text/code < 10MB) or presigned URL.
        """
        pass

    async def browse_vault(self, vault_id: str='root', bypass_cache: bool=False) -> dict:
        """
        Inspects folder contents in a vault (child vaults and files).
        """
        pass

    async def browse_path(self, string_path: str) -> dict:
        """
        Resolves human path (e.g. '/Finance/2026/') to vault contents.
        """
        pass

    async def get_tree(self, bypass_cache: bool=False) -> dict:
        """
        Returns full vault directory tree.
        """
        pass

    async def get_snapshot(self) -> dict:
        """
        Returns full hierarchy snapshot of all vaults and files.
        """
        pass

    async def move_item(self, item_id: str, to_vault_id: Optional[str]=None, from_vault_id: Optional[str]=None) -> dict:
        """
        Moves a file or vault to another vault.
        """
        pass

    async def delete_vfs_item(self, item_id: str) -> dict:
        """
        Deletes a file or vault from VFS.
        """
        pass

    @property
    def s3_bucket_name(self):
        """
        Returns the S3 bucket name.
        """
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

    async def send_sms(self, to_phone: Optional[str]=None, message: str='', **kwargs):
        """
        Send an SMS message via Twilio. Delegates to TwilioContext.
        """
        pass

    async def send_gmail(self, request: Union[Any, dict], **kwargs):
        """
        Send an email via Google Workspace / Gmail (DwD / Rep mailbox).
        """
        pass

    async def send_microsoft_email(self, request: Union[Any, dict], **kwargs):
        """
        Send an email via Microsoft 365 / Outlook (Graph API / Rep mailbox).
        """
        pass

    async def send_outlook(self, request: Union[Any, dict], **kwargs):
        """Alias for send_microsoft_email."""
        pass

    async def send_email(self, request: Union[Any, dict], provider: str='sendgrid', async_run: bool=True, **kwargs):
        """
        Send an email via specified provider ('sendgrid', 'gmail', or 'outlook').
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
from valstorm_platform.google_context import GoogleContext

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
from valstorm_platform.slack_context import SlackContext
from valstorm_platform.scraper_context import ScraperContext

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
