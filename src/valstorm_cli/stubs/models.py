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

from enum import Enum
from pydantic import BaseModel, EmailStr, Field, AfterValidator, ConfigDict, field_validator, model_serializer, SerializationInfo
from typing import Optional, List, Union, Literal, Dict, Any, Annotated
from datetime import datetime, timezone
from uuid import uuid4
from google.genai import types
system_fields = ['id', 'name', 'created_date', 'modified_date', 'created_by', 'modified_by', 'schema', 'owner', 'shared_with']

def ensure_utc(dt: datetime) -> datetime:
    pass

def datetime_to_z_format(dt: datetime) -> str:
    pass
AwareDatetime = Annotated[datetime, AfterValidator(ensure_utc)]

class BetterBaseModel(BaseModel):

    @model_serializer(mode='wrap')
    def serialize_model(self, handler, info: SerializationInfo):
        pass

    def _serialize_datetimes(self, obj: Any) -> Any:
        pass

class MongoQueryRequest(BaseModel):
    collection: str = Field(..., description="The target collection name (e.g., 'contact')")
    pipeline: List[Dict[str, Any]] = Field(..., description='The raw MongoDB aggregation pipeline')

class Component(BetterBaseModel):
    api_name: str = Field(default=None, json_schema_extra={'api_name': 'api_name'})

class Image(BetterBaseModel):
    url: Optional[str] = None
    alt_text: Optional[str] = None
    title: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    caption: Optional[str] = None
    credit: Optional[str] = None
    public: Optional[bool] = False

class Address(BetterBaseModel):
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    additional_info: Optional[str] = None

class OpenAiFunctionParameter(BetterBaseModel):
    type: Literal['string', 'number', 'integer', 'boolean', 'array', 'object']
    description: Optional[str] = None
    enum: Optional[List[Union[str, int, float]]] = None
    items: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, Any]] = None
    required: Optional[List[str]] = None

class OpenAiFunction(BetterBaseModel):
    name: str
    description: Optional[str] = None
    parameters: OpenAiFunctionParameter

class OpenAiFunctionTool(BetterBaseModel):
    type: Literal['function']
    function: OpenAiFunction

class OpenAiChatPayload(BetterBaseModel):
    model: str = 'gpt-3.5-turbo'
    messages: List[dict]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None
    tools: Optional[List[OpenAiFunctionTool]] = None
    response_format: Optional[Dict[str, Any]] = None

class GeminiFinalChatPayload(BetterBaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    model: str = 'gemini-flash-lite-latest'
    contents: Union[types.ContentListUnion, types.ContentListUnionDict]
    config: Optional[Dict] = None
    functions: Optional[List[str]] = None
    thinking_config: Optional[Dict] = None

class GeminiChatPayload(BetterBaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    model: str = 'gemini-flash-lite-latest'
    contents: Union[types.ContentListUnion, types.ContentListUnionDict]
    config: Optional[Dict] = None
    functions: Optional[List[str]] = None
    thinking_config: Optional[Dict] = None
    files: Optional[list[dict]] | Optional[dict] | Optional[str] = None

class FunctionCallPayload(BetterBaseModel):
    function_name: str
    kwargs: Dict[str, Any]

class PromptTemplatePayload(BetterBaseModel):
    id: str

class AssignmentPayload(BetterBaseModel):
    target_variable: str
    action: Literal['set', 'increment', 'decrement', 'append_to_list', 'remove_from_list']
    value: Any

class ReturnPayload(BetterBaseModel):
    output_type: Literal['default', 'custom', 'pure'] = 'default'
    status_code: int = 200
    content_type: str = 'application/json'
    content: Optional[Any] = None

class ConditionPayload(BetterBaseModel):
    """Defines a single comparison, like 'variable equals value'."""
    variable: str
    operator: Literal['equals', 'not_equals', 'greater_than', 'less_than', 'greater_than_or_equal_to', 'less_than_or_equal_to', 'contains', 'not_contains', 'exists', 'does_not_exist', 'starts_with', 'ends_with']
    value: Any

class ConditionGroupPayload(BetterBaseModel):
    """A list of conditions that are all evaluated with AND logic."""
    conditions: List[ConditionPayload]

class DecisionRulePayload(BetterBaseModel):
    """
    A single decision path (an 'if' or 'elif' branch). It contains groups of 
    conditions. The groups are evaluated with OR logic.
    """
    path_handle: str = Field(..., description='The unique identifier for the output handle on the frontend node.')
    groups: List[ConditionGroupPayload] = Field(default=[], description='A list of condition groups. If any group evaluates to true, this path is chosen.')
    logic_mode: Literal['builder', 'custom'] = 'builder'
    custom_logic: Optional[str] = Field(default=None, description="A custom logic string like '((1 AND 2) OR 3)'.")
DecisionPayload = List[DecisionRulePayload]

class WorkflowStep(BetterBaseModel):
    step_name: str = Field(..., description='A unique name for this step to be referenced later.')
    step_type: Literal['gemini_call', 'function_call', 'openai_call', 'gemini_template', 'openai_template', 'loop', 'assignment', 'return', 'decision', 'trigger']
    run: bool = True
    payload: Optional[Union[GeminiChatPayload, FunctionCallPayload, OpenAiChatPayload, PromptTemplatePayload, List[AssignmentPayload], ReturnPayload, DecisionPayload]] = None
    inputs: Optional[Dict[str, Any]] = None
    loop_body: Optional[List['WorkflowStep']] = None
    node_id: Optional[str] = None
WorkflowStep.model_rebuild()

class WorkflowEdge(BetterBaseModel):
    source: str
    sourceHandle: Optional[str] = None
    target: str

class WorkflowPayload(BetterBaseModel):
    id: Optional[str] = None
    steps: Optional[List[WorkflowStep]] = None
    inputs: Optional[Dict[str, Any]] = None
    edges: Optional[List[WorkflowEdge]] = []

class AiPrompt(BetterBaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    tag: Optional[List[Dict[str, Any]]] = None
    provider: Literal['OpenAI', 'Gemini'] = 'Gemini'
    model: Optional[str] = 'gemini-2.5-flash-lite-preview-06-17'
    prompts: List[Union[str, Dict[str, Any]]] = []
    general_config: Optional[Dict[str, Any]] = None
    inputs: Optional[List] = []

class MergeRecordsRequest(BetterBaseModel):
    schema_api_name: str
    master_record: str
    selected_records: list[str]

class Phone(BetterBaseModel):
    friendly_number: str = ''
    country_code: str = ''
    phone_number: str = ''
    extension: str = ''
    data: Optional[dict] = {}

    @field_validator('country_code', mode='before')
    @classmethod
    def normalize_country_code(cls, v: Any) -> str:
        pass

    @field_validator('phone_number', 'extension', mode='before')
    @classmethod
    def force_string(cls, v: Any) -> str:
        pass

class Lookup(BetterBaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    schema_id: Optional[str] = None
    schema_api_name: Optional[str] = None
    schema_title: Optional[str] = None

class StrictLookup(BetterBaseModel):
    id: str
    name: str
    schema_id: str
    schema_api_name: str
    schema_title: str

class UserLookup(BetterBaseModel):
    id: str
    name: str
    schema_id: str = 'f5e6501e-f157-4c35-9a04-f9e00db883f4'
    schema_api_name: str = 'user'
    schema_title: str = 'User'

class SharingAccess(str, Enum):
    READ = 'read'
    EDIT = 'edit'
    DELETE = 'delete'

class Sharing(BetterBaseModel):
    user: Optional[UserLookup] = Field(default=None, json_schema_extra={'format': 'lookup', 'schema': 'user', 'title': 'User'})
    access: SharingAccess = Field(default=SharingAccess.READ, title='Access Level')

class SystemLookup(BetterBaseModel):
    id: str = 'System'
    name: str = 'System'
    schema_id: str = 'f5e6501e-f157-4c35-9a04-f9e00db883f4'
    schema_api_name: str = 'user'
    schema_title: str = 'User'

class ReadNotificationData(BetterBaseModel):
    id: str
    type: str = 'send read'
    old_type: str
    user_id: str
    org_id: str

class ReadNotifcation(BetterBaseModel):
    type: str = ('send read',)
    user_id: str
    org_id: str
    data: ReadNotificationData

class CallStatus(str, Enum):
    available = 'available'
    busy = 'busy'
    offline = 'offline'
    on_call = 'on_call'
    do_not_disturb = 'do_not_disturb'
    away = 'away'
    unknown = 'unknown'

class CallAvailability(BetterBaseModel):
    call_status: CallStatus = CallStatus.offline
    available_for_mobile_calls: bool = False
    available_for_web_calls: bool = False
    allow_mobile_calls: bool = True
    allow_web_calls: bool = True
    allow_multiple_incoming_calls: bool = False
    allow_multiple_incoming_mobile_calls: bool = False
    has_mobile_app: bool = False
    max_simultaneous_calls: Optional[int] = 1
    priority: int = 1
    skills: Optional[List[str]] = []

class Availability(BetterBaseModel):
    sunday_start_time: Optional[str] = None
    sunday_end_time: Optional[str] = None
    monday_start_time: Optional[str] = '09:00'
    monday_end_time: Optional[str] = '17:00'
    tuesday_start_time: Optional[str] = '09:00'
    tuesday_end_time: Optional[str] = '17:00'
    wednesday_start_time: Optional[str] = '09:00'
    wednesday_end_time: Optional[str] = '17:00'
    thursday_start_time: Optional[str] = '09:00'
    thursday_end_time: Optional[str] = '17:00'
    friday_start_time: Optional[str] = '09:00'
    friday_end_time: Optional[str] = '17:00'
    saturday_start_time: Optional[str] = None
    saturday_end_time: Optional[str] = None
    sunday: bool = False
    monday: bool = True
    tuesday: bool = True
    wednesday: bool = True
    thursday: bool = True
    friday: bool = True
    saturday: bool = False
    do_not_disturb: bool = False
    holidays: Optional[List[datetime]] = None
    time_zone: Optional[str] = 'America/New_York'

class AvailabilityStatus(str, Enum):
    online = 'online'
    busy = 'busy'
    offline = 'offline'

class UserAvailability(Availability):
    status: AvailabilityStatus = AvailabilityStatus.offline
    current_location: Optional[str] = None
    active_devices: Optional[List[str]] = []
    on_vacation: bool = False
    vacation_start: Optional[datetime] = None
    vacation_end: Optional[datetime] = None
    last_available_at: Optional[datetime] = None
    last_unavailable_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    auto_away_timeout_minutes: Optional[int] = 30
    call_availability: CallAvailability = CallAvailability()

class LicenseFeature(str, Enum):
    AI = 'ai'
    GEMINI = 'gemini'
    OPENAI = 'openai'
    VALPHONE = 'valphone'
    VALRM = 'valrm'
    OUTBOUND_CALLS = 'outbound_calls'
    INBOUND_CALLS = 'inbound_calls'
    OUTBOUND_TEXTS = 'outbound_texts'
    INBOUND_TEXTS = 'inbound_texts'
    BULK_TEXT_SEND = 'bulk_text_send'
    BULK_EMAIL_SEND = 'bulk_email_send'
    LIVE_CHAT = 'live_chat'

class UserLicense(BetterBaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    modified_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    created_by: dict = {}
    modified_by: dict = {}
    name: str
    description: Optional[str] = None
    is_active: bool = True
    max_users: Optional[int] = None
    max_storage_gb: Optional[int] = None
    max_api_calls_per_day: Optional[int] = None
    max_integrations: Optional[int] = None
    features: List[LicenseFeature] = []

class User(BetterBaseModel):
    id: str
    created_by: dict = {}
    modified_by: dict = {}
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    is_account_owner: bool = False
    is_account_admin: bool = False
    name: Optional[str] = None
    organization_id: str
    organization_name: str
    permissions: List[str] = []
    settings: dict = {}
    notifications: dict = {}
    notification_token: Optional[str] = ''
    notification_token_datetime: Optional[datetime] = None
    notification_token_active: bool = False
    phone: Optional[Phone] = None
    organizations: list = []
    do_not_disturb: bool = False
    role: Optional[dict] = None
    manager: Optional[dict] = None
    availability: Optional[UserAvailability] = UserAvailability()
    integration_user: Optional[bool] = False
    is_impersonating: bool = False
    license: Optional[UserLicense] = None
    ui_access: bool = True
    profile_picture: Optional[Image] = None
    vacation: Optional[List[datetime]] = []
    activation_code: Optional[str] = None
    email_addresses: Optional[List[str]] = []
    mfa_required: bool = True
    shared_with: Optional[list] = Field(default_factory=list, json_schema_extra={'system': True, 'title': 'Shared With', 'type': 'list', 'format': 'sharing'})

class UserCreate(User):
    id: str = Field(default_factory=lambda: str(uuid4()))
    password: str

class OrganizationBase(BetterBaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    created_date: Optional[str] = datetime.now().isoformat()
    modified_date: Optional[str] = datetime.now().isoformat()
    is_active: bool = True

class Organization(OrganizationBase):
    id: str
    is_active: bool = True
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    created_by: SystemLookup | UserLookup | Lookup | Dict
    modified_by: SystemLookup | UserLookup | Lookup | Dict
    website: Optional[str] = None
    description: Optional[str] = None
    address: dict = {}
    shipping_address: dict = {}
    company_hours: Optional[Availability] = Availability()
    settings: Optional[dict] = {}
    company_holidays: Optional[List[datetime]] = []
    shared_with: Optional[list] = Field(default_factory=list, json_schema_extra={'system': True, 'title': 'Shared With', 'type': 'list', 'format': 'sharing'})

class StandardBase(BetterBaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    created_date: datetime
    modified_date: datetime
    created_by: dict = Field(default=None, json_schema_extra={'default': None, 'format': 'lookup', 'modify': False, 'schema': 'user', 'system': True, 'title': 'Created By', 'type': 'json'})
    modified_by: dict = Field(default=None, json_schema_extra={'default': None, 'format': 'lookup', 'modify': False, 'schema': 'user', 'system': True, 'title': 'Modified By', 'type': 'json'})

class ObjectFieldPermissions(BaseModel):
    model_config = ConfigDict(extra='allow')
    create: bool = False
    read: bool = False
    update: bool = False
    delete: bool = False

class ObjectPermissions(BaseModel):
    model_config = ConfigDict(extra='allow')
    create: bool = False
    read: bool = False
    update: bool = False
    delete: bool = False
    object_field_permissions: Dict[str, ObjectFieldPermissions] = Field(default_factory=dict)

class PermissionMap(BaseModel):
    model_config = ConfigDict(extra='allow')
    object_permissions: Dict[str, ObjectPermissions] = Field(default_factory=dict)

class Permission(StandardBase):
    model_config = ConfigDict(extra='allow')
    object_field_permissions: Optional[dict] = {}
    object_permissions: Optional[dict] = {}
    app: dict = {}
    shared_with: Optional[list] = Field(default_factory=list, json_schema_extra={'system': True, 'title': 'Shared With', 'type': 'list', 'format': 'sharing'})

class StandardOwnership(StandardBase):
    owner: str = Field(default=None, json_schema_extra={'default': None, 'format': 'lookup', 'modify': False, 'schema': 'user', 'system': True, 'title': 'Owner', 'type': 'string', 'api_name': 'owner'})
    shared_with: Optional[list] = Field(default_factory=list, json_schema_extra={'system': True, 'title': 'Shared With', 'type': 'list', 'format': 'sharing'})

class App(StandardBase):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    created_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    modified_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    created_by: Lookup
    modified_by: Lookup
    version: str = '1.0.0'
    schemas: Optional[List] = []
    records: Optional[Dict] = []
    settings: Optional[Dict] = {}
    owner: str
    app_admins: Optional[List[str]] = []
    active: bool = True
    installed: bool = False
    marketplace: bool = False
    onboarded: bool = False
    shared_with: Optional[list] = Field(default_factory=list, json_schema_extra={'system': True, 'title': 'Shared With', 'type': 'list', 'format': 'sharing'})

class IntegratedApp(StandardBase):
    authentication_url: Optional[str] = None
    token_url: Optional[str] = None
    authentication_protocol: Optional[str] = None
    config: dict = {}
    git_tracking: bool = False
    use_config: bool = False
    scopes: list = []
    internal: bool = False
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    access_token_minutes: Optional[int] = None
    refresh_token_days: Optional[int] = None
    organization: Optional[str] = None

class AuthCredential(StandardBase):
    user: UserLookup
    integrated_app: Lookup
    data: dict = {}
    headers: Optional[dict] = {}
    api_key: Optional[str] = None

class Token(BetterBaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TwoFAResponse(BetterBaseModel):
    detail: str = '2FA Required'
    two_fa_required: bool = True
    email: str

class Verify2FAPayload(BetterBaseModel):
    email: str
    code: str

class RefreshToken(BetterBaseModel):
    refresh_token: str

class AccessToken(BetterBaseModel):
    access_token: str

class AuthorizationCode(BetterBaseModel):
    redirect_url: str

class OauthCodeInput(BetterBaseModel):
    client_id: str
    state: Optional[str] = None

class CodeUrl(BetterBaseModel):
    code_url: str

class OauthRequestToken(BetterBaseModel):
    client_id: str
    client_secret: str
    grant_type: str
    code: str
    redirect_uri: str
    run_as: Optional[str] = None

class OauthAuthorizeInput(BetterBaseModel):
    client_id: str
    redirect_uri: str
    response_type: str
    state: Optional[str] = None
    scope: Optional[str] = None
    code_challenge: Optional[str] = None

class AcceptActivationInvite(BetterBaseModel):
    activation_code: str
    organization_id: str
    user_id: str

class SendNotificationSetting(BetterBaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    data: dict = {}

class NotificationSubscriber(BetterBaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    modified_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    created_by: SystemLookup | UserLookup | Lookup
    modified_by: SystemLookup | UserLookup | Lookup
    name: str
    user: UserLookup
    active: bool = True
    notification_setting: Lookup
    record_id: Optional[str] = None
    object: Optional[Lookup] = None

class NotificationSetting(BetterBaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    modified_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    created_by: SystemLookup | UserLookup | Lookup
    modified_by: SystemLookup | UserLookup | Lookup
    name: str
    channel: str
    type: str
    data: dict
    users: Optional[list] = []
    groups: Optional[list] = []
    create_subscribers: bool = False
    save: bool = False
    notify: bool = True
    record_alerts: bool = False
    object: Optional[dict] = None
    push_to_mobile: bool = False
    all_users: bool = False
    add_record_owner: bool = False
    add_owner_manager: bool = False
    display_template: Optional[str] = None
    title_template: Optional[str] = None
    action_url: Optional[str] = None
    parent_schema_api_name: Optional[str] = None
    child_collection_key: Optional[str] = None
    icon: Optional[str] = None
    notify_sender: bool = False
    sender: Optional[Lookup] = None
    subscriber_creation_function: Optional[Lookup] = None
    subscriber_creation_automation: Optional[Lookup] = None
    push_to_web: bool = False

class Notification(BetterBaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    modified_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    created_by: SystemLookup | UserLookup | Lookup = SystemLookup()
    modified_by: SystemLookup | UserLookup | Lookup = SystemLookup()
    name: str
    channel: str
    type: str
    data: dict
    read: bool = False
    user: UserLookup
    object: Optional[Lookup] = None
    record_id: Optional[str] = None
    body: Optional[str] = None
    title: Optional[str] = None
    notification_setting: Optional[Lookup] = None
    notify: bool = True
    save: bool = True

class WebNotificationData(BaseModel):
    title: str
    body: str
    url: Optional[str] = '/'
    icon: Optional[str] = '/icon.png'
    image: Optional[str] = ''
    tag: Optional[str] = ''
    tab: Optional[str] = ''
    sound: Optional[str] = 'default'

class WebNotificationMessage(BaseModel):
    token: str
    data: WebNotificationData

class WebNotification(BaseModel):
    message: WebNotificationMessage

class PushNotificationBody(BetterBaseModel):
    body: str
    title: str

class IosNotificationHeaders(BetterBaseModel):
    apns_priority: str = '5'

class IosAps(BetterBaseModel):
    alert: PushNotificationBody
    badge: int = 0
    sound: str = 'default'

class IosNotificationPayload(BetterBaseModel):
    aps: IosAps

class IosNotificationApns(BetterBaseModel):
    headers: dict = {}
    payload: IosNotificationPayload

class WebPushHeaders(BetterBaseModel):
    Urgency: str = 'normal'

class WebPushNotificationBody(BetterBaseModel):
    headers: WebPushHeaders = WebPushHeaders()

class AndroidNotification(BetterBaseModel):
    title: str
    body: str
    icon: str = 'https://valstorm.com/valphone-192.png'
    color: str = '#FFFFFF'
    sound: str = 'default'

class AndroidPushNotification(BetterBaseModel):
    ttl: str = ('86400s',)
    data: dict = ({},)
    priority: str = ('normal',)
    notification: AndroidNotification

class PushNotificationMessage(BetterBaseModel):
    token: str
    notification: PushNotificationBody
    webpush: WebPushNotificationBody = WebPushNotificationBody()
    apns: Optional[IosNotificationApns] = None
    android: Optional[AndroidPushNotification] = None
    data: dict = {}

class PushNotification(BetterBaseModel):
    message: PushNotificationMessage

class DynamicNotificationRequest(BetterBaseModel):
    title: str
    body: str
    type: str = 'dynamic'
    user_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = {}
    save: bool = True
    notify: bool = True
    push_to_mobile: bool = False
    record_id: Optional[str] = None

class DynamicNotification(DynamicNotificationRequest):
    organization_id: str

class EmailTemplate(BetterBaseModel):
    subject: str
    to_address: list[str]
    from_address: str
    merge_fields: dict = None
    html_message: str = None
    text_message: str = None
    attachments: Optional[List[str]] = None

class GmailSendRequest(BetterBaseModel):
    to: List[str] | str
    from_email: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    reply_to: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    html_content: Optional[str] = None
    template_id: Optional[str] | Optional[dict] = None
    merge_data: Optional[Dict[str, Any]] = None
    attachments: Optional[List[str]] = None

    @field_validator('to', mode='before')
    @classmethod
    def convert_to_list(cls, v):
        pass

class Log(BetterBaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    modified_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    created_by: UserLookup
    modified_by: UserLookup
    name: str
    header: dict = {}
    log: Optional[str] = None
    status: str
    status_code: str
    method: str
    path: str
    query_parameter: dict = {}
    start_time: datetime = datetime.now()
    process_time: Optional[float] = None
    end_time: datetime
    request_data: Optional[str] = None
    ip_address: str
    user_agent: str

class BulkSend(BetterBaseModel):
    campaign: str
    template: Optional[str] = None
    file: Optional[str] = None
    action: str
    schedule_date_time: str
    phone_field: Optional[str] = None
    email_field: Optional[str] = None
    from_number: Optional[str] = None
    from_email: Optional[str] = None
    provider: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    attachments: Optional[List[str]] = None
    automation: Optional[str] = None

class ScheduleTriggerSetting(BetterBaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    created_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    modified_date: AwareDatetime = Field(default_factory=datetime.utcnow)
    created_by: UserLookup
    modified_by: UserLookup
    running_user: Optional[UserLookup] | Optional[dict] = None
    cron_schedule: str
    active: bool = True
    data: Optional[dict] = None
    function: Optional[dict] = None
    automation: Optional[dict] = None

class AcceptedResponse(BetterBaseModel):
    detail: str

class MagicCodeRequest(BetterBaseModel):
    email: str
    client_id: Optional[str] = None

class CreateServiceRequest(BaseModel):
    """
    Schema for creating a Twilio Conversational Intelligence Service.
    Corresponds to the 'Request body parameters' in the Twilio documentation.
    """
    UniqueName: str
    FriendlyName: Optional[str] = None
    AutoTranscribe: Optional[bool] = None
    DataLogging: Optional[bool] = None
    LanguageCode: Optional[str] = 'en-US'
    AutoRedaction: Optional[bool] = None
    MediaRedaction: Optional[bool] = None
    WebhookUrl: Optional[str] = None
    WebhookHttpMethod: Optional[str] = 'POST'
    EncryptionCredentialSid: Optional[str] = None

class CreateTwilioRecordingTranscriptionRequest(BaseModel):
    """
    Schema for creating a Twilio Recording Transcription.
    """
    recording_sid: str
    service_sid: str

class SendGridAsmSettings(BaseModel):
    group_id: int
    groups_to_display: Optional[List[int]] = None

class SendGridFooterSettings(BaseModel):
    enable: bool = False
    text: Optional[str] = None
    html: Optional[str] = None

class SendGridEnable(BaseModel):
    enable: bool = False

class SendGridMailSettings(BaseModel):
    footer_settings: SendGridFooterSettings = SendGridFooterSettings()
    sandbox_mode: SendGridEnable = SendGridEnable()
    bypass_list_management: SendGridEnable = SendGridEnable()
    bypass_spam_management: SendGridEnable = SendGridEnable()
    bypass_bounce_management: SendGridEnable = SendGridEnable()
    bypass_unsubscribe_management: SendGridEnable = SendGridEnable()

class SendGridTrackingSettings(BaseModel):
    click_tracking: bool = True
    open_tracking: bool = True
    subscription_tracking: bool = False
    ganalytics: Optional[Dict[str, Any]] = None

class SendGridAttachment(BaseModel):
    file_content: str
    file_name: str
    file_type: Optional[str] = None
    disposition: Optional[str] = 'attachment'

class SendGridEmailRequest(BaseModel):
    to_emails: List[str]
    from_email: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    reply_to: Optional[str] = None
    subject: str
    plain_text_content: str
    html_content: Optional[str] = None
    template_id: Optional[str] | Optional[dict] = None
    merge_data: Optional[Dict[str, Any]] = None
    file_attachments: Optional[List[str]] = None
    attachments: Optional[List[SendGridAttachment]] = None
    mail_settings: Optional[SendGridMailSettings] = None
    tracking_settings: Optional[SendGridTrackingSettings] = None
    asm_settings: Optional[SendGridAsmSettings] = None

    @field_validator('to_emails', 'cc', 'bcc', mode='before')
    @classmethod
    def convert_str_to_list(cls, v):
        pass

    @field_validator('file_attachments', 'attachments', mode='before')
    @classmethod
    def convert_single_item_to_list(cls, v):
        pass

class TwilioSMS(BaseModel):
    from_number: Optional[str] | Optional[dict] = None
    to: Optional[str] = None
    body: Optional[str] = ''
    template_id: Optional[str] | Optional[dict] = None
    merge_data: Optional[Dict[str, Any]] | Optional[str] = None
    conversation_sid: Optional[str] = None
    media_sid: Optional[str] = None
    media: Optional[list] = None
    automated: bool = True
    use_conversations: bool = True
    run_date_time: Optional[datetime] = None
    contact: Optional[dict] = None
    phone: Optional[dict] = None
    conversation: Optional[dict] = None
    participant: Optional[dict] = None
    scheduled_item_id: Optional[str] = None
    campaign_id: Optional[str] = None

class Function(BetterBaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    created_date: datetime = Field(default_factory=datetime.utcnow)
    modified_date: datetime = Field(default_factory=datetime.utcnow)
    created_by: dict | UserLookup | str = ''
    modified_by: dict | UserLookup | str = ''
    file_name: str
    app: dict | Lookup | str = ''
    code: str = ''