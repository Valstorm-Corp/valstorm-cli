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

import time
import contextvars
from typing import Dict, List, Set, Optional, Any
from uuid import uuid4
from valstorm_platform.models import User
from valstorm.dependencies import add_log
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
        """Increases Chain Depth. Returns False if max nesting reached."""
        pass

    def pop(self):
        """Decrements Chain Depth."""
        pass

    def has_ran(self, schema: str, trigger_name: str, context: str) -> bool:
        """Checks if this specific trigger has already executed for this context."""
        pass

    def log_execution(self, schema: str, trigger_name: str, context: str):
        """Registers that a trigger is about to run."""
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
        pass

    @property
    def changes(self) -> Dict[str, Set[str]]:
        pass

    def _calculate_diffs(self):
        pass

    def _are_equal(self, val1: Any, val2: Any) -> bool:
        """
        Deep comparison that treats None and missing keys as equivalent.
        Also handles Pydantic models vs dicts.
        """
        pass

    def is_changed(self, record_id: str, field: str) -> bool:
        pass

    async def get_schema_from_id_async(self, record_id: str, db) -> Optional[str]:
        """
        Extracts the schema api name from a flat prefixed string ID, supporting custom dynamic prefixes.
        E.g., "cst1_pCV6UUEoHNHgbfIE" -> "custom_object_1"
        """
        pass

    def get_schema_from_id(self, record_id: str) -> Optional[str]:
        pass

    def get_list(self) -> List[Dict]:
        pass
