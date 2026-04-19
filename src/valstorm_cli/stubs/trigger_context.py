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

from .platform_context import PlatformContext, RecordContext, QueryContext, SchemaContext, CommunicationContext, WorkflowContext, MetadataContext, IntegrationContext, UtilsContext
import time
import contextvars
from typing import Dict, List, Set, Optional, Any
from uuid import uuid4
from .models import User
_active_transaction = contextvars.ContextVar('active_transaction', default=None)

class TriggerTransaction:
    """
    Singleton for the duration of the request/task.
    Enforces:
    1. Max Chain Depth (e.g., 5 nested operations)
    2. Unique Execution (Triggers run exactly once per Schema + Context)
    """

    def __init__(self, user: User, max_depth: int=25):
        pass

    def push(self, description: str) -> bool:
        pass

    def pop(self):
        pass

    def has_ran(self, schema: str, trigger_name: str, context: str) -> bool:
        pass

    def log_execution(self, schema: str, trigger_name: str, context: str):
        pass

    def is_bypassed(self, trigger_identifier: str) -> bool:
        pass

class TransactionScope:
    """
    Context Manager. Initializes or retrieves the active transaction.
    """

    def __init__(self, current_user: User):
        pass

    def __enter__(self) -> TriggerTransaction:
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass

class RecordTriggerContext:
    """
    Data Object passed to V2 Triggers.
    """

    def __init__(self, schema_api_name: str, context: str, transaction: TriggerTransaction, new_data: List[Dict]=None, old_data: List[Dict]=None):
        self.transaction = None
        self.schema = None
        self.trigger_context = None
        self.transaction_id = None
        self.user = None
        self.platform: PlatformContext = None
        self.records: RecordContext = None
        self.query: QueryContext = None
        self.schemas: SchemaContext = None
        self.communications: CommunicationContext = None
        self.workflows: WorkflowContext = None
        self.metadata: MetadataContext = None
        self.integrations: IntegrationContext = None
        self.utils: UtilsContext = None
        self.utils = None
        self.log = None
        self.new_map: Dict[str, Dict] = None
        self.old_map: Dict[str, Dict] = None
        self._changes: Dict[str, Set[str]] = None
        self._diff_calculated = None

    @property
    def changes(self) -> Dict[str, Set[str]]:
        pass

    def _calculate_diffs(self):
        pass

    def _are_equal(self, val1: Any, val2: Any) -> bool:
        pass

    def is_changed(self, record_id: str, field: str) -> bool:
        pass

    def get_list(self) -> List[Dict]:
        pass