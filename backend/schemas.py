"""NiyamPulse v2 shared DTOs: exam monitoring, subscriptions, alerts, impact.

Native target: Python 3.12 + Pydantic v2. Models are contracts, not implemented
crawlers, policy decisions, eligibility evaluators, or notification delivery.

Existing v1 contracts are retained in backend.legacy_schemas_v1 and re-exported
at the bottom for gradual migration. Do NOT delete the legacy file until the
Codex repository has passed its migration tests.

    py -3.12 -m backend.schemas
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, EmailStr, SecretStr,
    field_validator, model_validator,
)

from . import legacy_schemas_v1 as legacy

SCHEMA_VERSION = "2.0.0"
DISCLAIMER = "Decision support only; not official eligibility or application confirmation."

Id = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1, max_length=500)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)


class Audience(str, Enum):
    SCHOOL = "SCHOOL"
    ENGINEERING = "ENGINEERING"
    GENERAL = "GENERAL"


class ExamFamily(str, Enum):
    SCHOOL_ENTRANCE = "SCHOOL_ENTRANCE"
    DEFENCE_ENTRANCE = "DEFENCE_ENTRANCE"
    ENGINEERING_POSTGRAD = "ENGINEERING_POSTGRAD"
    GOVERNMENT_RECRUITMENT = "GOVERNMENT_RECRUITMENT"


class Language(str, Enum):
    EN = "en"
    HI = "hi"


class SourceKind(str, Enum):
    OFFICIAL_WEB_LISTING = "OFFICIAL_WEB_LISTING"
    ADMIN_UPLOAD = "ADMIN_UPLOAD"
    LOCAL_DEMO_FIXTURE = "LOCAL_DEMO_FIXTURE"


class SourceReadiness(str, Enum):
    LISTING_VERIFIED_ADAPTER_UNTESTED = "LISTING_VERIFIED_ADAPTER_UNTESTED"
    ADAPTER_TESTED = "ADAPTER_TESTED"
    DISABLED = "DISABLED"


class NoticeType(str, Enum):
    ORIGINAL = "ORIGINAL"
    CORRIGENDUM = "CORRIGENDUM"
    DEADLINE = "DEADLINE"
    EXAM_DATE = "EXAM_DATE"
    ADMIT_CARD = "ADMIT_CARD"
    ANSWER_KEY = "ANSWER_KEY"
    RESULT = "RESULT"
    SYLLABUS = "SYLLABUS"
    APPLICATION_CORRECTION = "APPLICATION_CORRECTION"
    INFORMATIONAL = "INFORMATIONAL"
    UNKNOWN = "UNKNOWN"


class RuleChangeType(str, Enum):
    MINIMUM_MARKS = "minimum_marks"
    MAXIMUM_INCOME = "maximum_income_inr"
    APPLICATION_DEADLINE = "application_deadline"
    AGE_BOUNDS = "age_bounds"
    REQUIRED_DOCUMENTS = "required_documents"


class DocumentTrust(str, Enum):
    MATCHED_CONFIGURED_SOURCE = "MATCHED_CONFIGURED_SOURCE"  # NOT authenticity certification
    UNVERIFIED = "UNVERIFIED"
    MISMATCH = "MISMATCH"


class ReviewStatus(str, Enum):
    DETECTED = "DETECTED"
    PROCESSING = "PROCESSING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ApplicationStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    INTERESTED = "INTERESTED"
    PLANNING_TO_APPLY = "PLANNING_TO_APPLY"
    APPLIED_SELF_REPORTED = "APPLIED_SELF_REPORTED"
    NO_LONGER_INTERESTED = "NO_LONGER_INTERESTED"


class Topic(str, Enum):
    ALL = "ALL"
    REGISTRATION = "REGISTRATION"
    ELIGIBILITY = "ELIGIBILITY"
    EXAM_SCHEDULE = "EXAM_SCHEDULE"
    ADMIT_CARD = "ADMIT_CARD"
    ANSWER_KEY = "ANSWER_KEY"
    RESULTS = "RESULTS"
    SYLLABUS = "SYLLABUS"
    OTHER = "OTHER"


class RecipientRelevance(str, Enum):
    GENERAL_UPDATE = "GENERAL_UPDATE"
    PERSONAL_IMPACT = "PERSONAL_IMPACT"
    POSSIBLE_IMPACT = "POSSIBLE_IMPACT"
    UNKNOWN = "UNKNOWN"


class DeliveryState(str, Enum):
    QUEUED = "QUEUED"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"


class ExamCatalogEntry(StrictModel):
    exam_id: Id
    display_name: NonEmpty
    exam_family: ExamFamily
    audiences: list[Audience] = Field(min_length=1)
    organizer: NonEmpty
    description: str = Field(default="", max_length=1200)
    active: bool = True
    source_ids: list[Id] = Field(default_factory=list)

    @field_validator("audiences")
    @classmethod
    def audiences_unique(cls, value: list[Audience]) -> list[Audience]:
        if len(set(value)) != len(value):
            raise ValueError("audiences must be unique")
        return value


class ExamCycle(StrictModel):
    cycle_id: Id
    exam_id: Id
    year: int = Field(ge=2020, le=2100)
    phase: str | None = Field(default=None, max_length=100)  # e.g. session 1 / paper 2
    display_name: NonEmpty
    is_active: bool = True


class OfficialSource(StrictModel):
    source_id: Id
    organization: NonEmpty
    source_kind: Literal["OFFICIAL_WEB_LISTING"] = "OFFICIAL_WEB_LISTING"
    listing_url: HttpUrl
    allowed_hosts: list[str] = Field(min_length=1)
    readiness: SourceReadiness = SourceReadiness.LISTING_VERIFIED_ADAPTER_UNTESTED
    adapter_name: str | None = None
    enabled: bool = False
    poll_interval_minutes: int = Field(default=60, ge=15, le=10080)
    notes: str = Field(default="", max_length=2000)

    @field_validator("allowed_hosts")
    @classmethod
    def no_wildcard_hosts(cls, hosts: list[str]) -> list[str]:
        normalized = [h.strip().lower() for h in hosts]
        if not all(h and "*" not in h and ":" not in h and "/" not in h for h in normalized):
            raise ValueError("allowed_hosts require exact hostname entries")
        if len(set(normalized)) != len(normalized):
            raise ValueError("allowed_hosts must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_source_readiness(self) -> "OfficialSource":
        if self.enabled and self.readiness != SourceReadiness.ADAPTER_TESTED:
            raise ValueError("web source cannot be enabled until its adapter is tested")
        if self.enabled and not self.adapter_name:
            raise ValueError("enabled web source requires adapter_name")
        if self.listing_url.host.lower() not in self.allowed_hosts:
            raise ValueError("listing host must be present in allowed_hosts")
        return self


class UserProfileV2(StrictModel):
    user_id: Id
    preferred_language: Language = Language.EN
    display_name: str | None = Field(default=None, max_length=120)
    # All personal relevance inputs are optional and self-reported.
    date_of_birth: date | None = None
    marks_percent: float | None = Field(default=None, ge=0, le=100)
    annual_household_income_inr: int | None = Field(default=None, ge=0)
    available_document_codes: list[str] = Field(default_factory=list)
    document_inventory_complete: bool = False
    personalization_opt_in: bool = False
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def opt_in_for_personal_data(self) -> "UserProfileV2":
        if not self.personalization_opt_in and any([
            self.date_of_birth is not None, self.marks_percent is not None,
            self.annual_household_income_inr is not None,
            bool(self.available_document_codes), self.document_inventory_complete,
        ]):
            raise ValueError("personal relevance fields require explicit personalization_opt_in")
        return self


class ExamSubscription(StrictModel):
    subscription_id: Id
    user_id: Id
    cycle_id: Id
    topics: list[Topic] = Field(default_factory=lambda: [Topic.ALL], min_length=1)
    application_status: ApplicationStatus = ApplicationStatus.UNKNOWN
    notifications_enabled: bool = True
    subscribed_at: AwareDatetime

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, topics: list[Topic]) -> list[Topic]:
        if len(set(topics)) != len(topics):
            raise ValueError("topics must be unique")
        if Topic.ALL in topics and len(topics) > 1:
            raise ValueError("ALL topic must not be combined with other topics")
        return topics


class EvidenceAnchor(StrictModel):
    document_id: Id
    document_sha256: Sha256
    page_number: int = Field(ge=1)
    literal_quote: str = Field(min_length=1, max_length=4000)
    # Coordinates optional, never fabricated; 1-based page numbers.
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=1)
    extraction_id: Id | None = None

    @model_validator(mode="after")
    def offsets_consistent(self) -> "EvidenceAnchor":
        if (self.start_char is None) != (self.end_char is None):
            raise ValueError("both offsets required or neither")
        if self.start_char is not None and self.end_char <= self.start_char:
            raise ValueError("end_char must be greater than start_char")
        return self


class DetectedNotice(StrictModel):
    notice_id: Id
    cycle_id: Id
    source_id: Id | None = None
    source_kind: SourceKind
    title: NonEmpty
    notice_type: NoticeType = NoticeType.UNKNOWN
    source_url: HttpUrl | None = None
    document_sha256: Sha256
    published_on: date | None = None
    first_seen_at: AwareDatetime
    trust: DocumentTrust = DocumentTrust.UNVERIFIED
    review_status: ReviewStatus = ReviewStatus.DETECTED
    evidence: list[EvidenceAnchor] = Field(default_factory=list)
    reference_numbers: list[str] = Field(default_factory=list)
    revision: int = Field(default=0, ge=0)
    topics: list[Topic] = Field(default_factory=lambda: [Topic.OTHER], min_length=1)
    processing_mode: Literal["SOURCE_EXCERPT", "OFFLINE_REPLAY", "SARVAM_105B", "NEEDS_EXTRACTION"] = "NEEDS_EXTRACTION"
    diagnostics: list[str] = Field(default_factory=list)
    requires_rule_validation: bool = False

    @model_validator(mode="after")
    def url_required_for_web_notice(self) -> "DetectedNotice":
        if self.source_kind == SourceKind.OFFICIAL_WEB_LISTING:
            if self.source_url is None or self.source_id is None:
                raise ValueError("web notice requires source_url and source_id")
        if self.trust == DocumentTrust.MISMATCH and self.review_status == ReviewStatus.APPROVED:
            raise ValueError("mismatched source cannot be approved")
        return self


class NoticeChange(StrictModel):
    change_id: Id
    notice_id: Id
    rule_type: RuleChangeType
    operation: Literal["ADD", "REPLACE", "REVOKE"]
    target_rule_id: Id | None = None
    # The actual validated rule object is the legacy closed-set RuleDefinition;
    # the exam cycle maps to legacy RuleBase.scheme_id.
    proposed_rule: legacy.RuleDefinition | None = None
    effective_from: date | None = None
    evidence: list[EvidenceAnchor] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_change(self) -> "NoticeChange":
        if self.operation in {"REPLACE", "REVOKE"} and not self.target_rule_id:
            raise ValueError("REPLACE and REVOKE require target_rule_id")
        if self.operation in {"ADD", "REPLACE"} and self.proposed_rule is None:
            raise ValueError("ADD/REPLACE require proposed_rule")
        if self.operation == "REVOKE" and self.proposed_rule is not None:
            raise ValueError("REVOKE must not have proposed_rule")
        if self.operation == "ADD" and self.target_rule_id is not None:
            raise ValueError("ADD must not target an existing rule")
        if self.proposed_rule is not None:
            if self.proposed_rule.rule_type != self.rule_type.value:
                raise ValueError("rule_type must match proposed_rule")
            if self.effective_from != self.proposed_rule.effective_from:
                raise ValueError("effective_from must match proposed_rule")
        return self


class NoticeReviewDecision(StrictModel):
    notice_id: Id
    reviewer_id: Id
    action: Literal["APPROVE", "QUARANTINE", "REJECT"]
    reason: NonEmpty
    reviewed_at: AwareDatetime
    expected_revision: int = Field(ge=0)


class NoticeUpdate(StrictModel):
    update_id: Id
    cycle_id: Id
    notice_id: Id
    notice_type: NoticeType
    published_at: AwareDatetime
    summary_en: str = Field(min_length=1, max_length=2500)
    summary_hi: str | None = Field(default=None, max_length=2500)
    evidence: list[EvidenceAnchor] = Field(min_length=1)
    rule_changes: list[NoticeChange] = Field(default_factory=list)
    approved_by: Id
    approved_at: AwareDatetime
    evaluation_version: str = Field(min_length=1)
    rule_set_sha256: Sha256 | None = None


class RecipientMatch(StrictModel):
    match_id: Id
    update_id: Id
    user_id: Id
    subscription_id: Id
    relevance: RecipientRelevance
    reason_codes: list[str] = Field(min_length=1)
    before: legacy.DecisionStatus | None = None
    after: legacy.DecisionStatus | None = None
    before_checks: list[legacy.RuleCheck] = Field(default_factory=list)
    after_checks: list[legacy.RuleCheck] = Field(default_factory=list)
    # Only populate before/after when checks have actually run on the
    # applicable scoped rule set; never fabricate official eligibility.

    @model_validator(mode="after")
    def has_decision_pair_or_neither(self) -> "RecipientMatch":
        if (self.before is None) != (self.after is None):
            raise ValueError("before and after decision must both be present or both absent")
        if self.relevance == RecipientRelevance.PERSONAL_IMPACT and self.before is None:
            raise ValueError("PERSONAL_IMPACT requires computed before/after decisions")
        if self.relevance == RecipientRelevance.PERSONAL_IMPACT and self.before == self.after:
            raise ValueError("PERSONAL_IMPACT requires a status change")
        return self


class InAppNotification(StrictModel):
    notification_id: Id
    user_id: Id
    match_id: Id
    update_id: Id
    cycle_id: Id
    delivery: DeliveryState = DeliveryState.QUEUED
    headline: NonEmpty
    body: str = Field(min_length=1, max_length=1600)
    language: Language
    created_at: AwareDatetime
    delivered_at: AwareDatetime | None = None
    read_at: AwareDatetime | None = None
    official_source_url: HttpUrl | None = None
    evidence: list[EvidenceAnchor] = Field(min_length=1)
    disclaimer: Literal["Decision support only; not official approval.", "Decision support only; not official eligibility or application confirmation."] = DISCLAIMER

    @model_validator(mode="after")
    def delivery_timestamps(self) -> "InAppNotification":
        if self.delivery in {DeliveryState.DELIVERED, DeliveryState.READ} and not self.delivered_at:
            raise ValueError("DELIVERED/READ requires delivered_at")
        if self.delivery == DeliveryState.READ and not self.read_at:
            raise ValueError("READ requires read_at")
        if self.read_at and self.delivered_at and self.read_at < self.delivered_at:
            raise ValueError("read_at cannot precede delivered_at")
        return self


class AdminDashboardTotals(StrictModel):
    monitored_sources: int = Field(ge=0)
    active_exam_cycles: int = Field(ge=0)
    registered_users: int = Field(ge=0)
    active_subscriptions: int = Field(ge=0)
    notices_detected: int = Field(ge=0)
    notices_pending_review: int = Field(ge=0)
    approved_updates: int = Field(ge=0)
    matched_recipients: int = Field(ge=0)
    notifications_delivered: int = Field(ge=0)
    notifications_failed: int = Field(ge=0)
    notifications_read: int = Field(default=0, ge=0)
    # All values must come from database aggregates; no placeholder metrics.


class AdminDashboardResponse(StrictModel):
    schema_version: Literal["2.0.0"] = SCHEMA_VERSION
    generated_at: AwareDatetime
    totals: AdminDashboardTotals
    recent_updates: list[NoticeUpdate] = Field(default_factory=list)
    source_health: dict[str, str] = Field(default_factory=dict)
    source_checks: list[SourceHealth] = Field(default_factory=list)
    by_cycle: list[CycleTotals] = Field(default_factory=list)
    synthetic_demo: bool = True
    monitor_running: bool = False


class CatalogResponse(StrictModel):
    schema_version: Literal["2.0.0"] = SCHEMA_VERSION
    exams: list[ExamCatalogEntry]
    cycles: list[ExamCycle]
    coverage: dict[str, Literal["CATALOG_ONLY", "SOURCE_CONFIGURED", "LIVE_MONITORED"]] = Field(default_factory=dict)


class NotificationsResponse(StrictModel):
    schema_version: Literal["2.0.0"] = SCHEMA_VERSION
    notifications: list[InAppNotification]
    next_cursor: str | None = None
    unread_count: int = Field(default=0, ge=0)


class ApiError(StrictModel):
    code: NonEmpty
    message: NonEmpty
    request_id: Id | None = None
    details: dict[str, str] = Field(default_factory=dict)


class SubscriptionCreate(StrictModel):
    cycle_id: Id
    topics: list[Topic] = Field(default_factory=lambda: [Topic.ALL], min_length=1)
    application_status: ApplicationStatus = ApplicationStatus.INTERESTED

    @field_validator("topics")
    @classmethod
    def topics_valid(cls, value):
        return ExamSubscription.validate_topics(value)


class SubscriptionPatch(StrictModel):
    topics: list[Topic] | None = Field(default=None, min_length=1)
    application_status: ApplicationStatus | None = None
    notifications_enabled: bool | None = None

    @field_validator("topics")
    @classmethod
    def topics_valid(cls, value):
        return ExamSubscription.validate_topics(value) if value is not None else value


class ProfilePatch(StrictModel):
    preferred_language: Language | None = None
    display_name: str | None = Field(default=None, max_length=120)
    personalization_opt_in: bool | None = None
    date_of_birth: date | None = None
    marks_percent: float | None = Field(default=None, ge=0, le=100)
    annual_household_income_inr: int | None = Field(default=None, ge=0)
    available_document_codes: list[str] | None = None
    document_inventory_complete: bool | None = None


class DemoSessionRequest(StrictModel):
    persona: Literal["school", "engineering", "operator"]


class SessionResponse(StrictModel):
    access_token: NonEmpty
    user_id: Id
    display_name: str
    role: Literal["USER", "ADMIN"]
    demo_mode: Literal[True] = True
    expires_at: AwareDatetime


class SourceHealth(StrictModel):
    source_id: Id
    status: Literal["DISABLED", "NEVER_CHECKED", "LIVE_OK", "ERROR", "OFFLINE_REPLAY"] = "DISABLED"
    last_attempt_at: AwareDatetime | None = None
    last_success_at: AwareDatetime | None = None
    last_error: str | None = None
    last_http_status: int | None = None
    last_new_notices: int = Field(default=0, ge=0)
    pending_extractions: int = Field(default=0, ge=0)
    total_notices: int = Field(default=0, ge=0)
    robots_status: str | None = None
    next_due_at: AwareDatetime | None = None


class CycleTotals(StrictModel):
    cycle_id: Id
    subscriptions: int = Field(ge=0)
    updates: int = Field(ge=0)
    notifications: int = Field(ge=0)


class MonitorCheckRequest(StrictModel):
    dry_run: bool = True


class MonitorCheckResult(StrictModel):
    schema_version: Literal["2.0.0"] = SCHEMA_VERSION
    source_id: Id
    checked_at: AwareDatetime
    dry_run: bool
    mode: Literal["LIVE", "OFFLINE_REPLAY"]
    listing_sha256: Sha256 | None = None
    discovered_links: int = Field(default=0, ge=0)
    created_notices: int = Field(default=0, ge=0)
    duplicates: int = Field(default=0, ge=0)
    pending_extractions: int = Field(default=0, ge=0)
    unmapped: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ExtractedFact(StrictModel):
    kind: Literal["ANNOUNCEMENT", "APPLICATION_DEADLINE", "EXAM_DATE", "RULE_CANDIDATE", "UNSUPPORTED_REQUIREMENT"]
    page_number: int = Field(ge=1)
    literal_quote: str = Field(min_length=12, max_length=600)
    date_value: date | None = None


class SarvamCandidate(StrictModel):
    cycle_id: Id
    notice_type: NoticeType
    topics: list[Topic] = Field(min_length=1, max_length=7)
    facts: list[ExtractedFact] = Field(min_length=1, max_length=6)
    requires_rule_validation: bool


class AnalysisRequest(StrictModel):
    expected_revision: int = Field(ge=0)


class NoticeAnalysis(StrictModel):
    analysis_id: Id
    notice_id: Id
    provider: Literal["SARVAM_105B"] = "SARVAM_105B"
    model: str = "sarvam-105b"
    prompt_version: str
    guard_version: str | None = None
    created_at: AwareDatetime
    status: Literal["VALIDATED", "GUARD_REJECTED"]
    cache_hit: bool = False
    input_sha256: Sha256
    extraction_id: Id
    pages_processed: list[int]
    total_pages: int = Field(ge=1)
    coverage_complete: bool
    candidate: SarvamCandidate | None = None
    summary_en: str | None = Field(default=None, max_length=2500)
    summary_hi: str | None = Field(default=None, max_length=2500)
    summary_method: Literal["EXTRACTIVE_EN_CONTROLLED_HI"] = "EXTRACTIVE_EN_CONTROLLED_HI"
    evidence: list[EvidenceAnchor] = Field(default_factory=list)
    notice_changes: list[NoticeChange] = Field(default_factory=list)
    rule_set_revision: int = Field(default=0, ge=0)
    diagnostics: list[str] = Field(default_factory=list)


class CreditBalanceReport(StrictModel):
    credits: str = Field(pattern=r"^\d{1,7}(?:\.\d{1,2})?$")


class CreditSafety(StrictModel):
    floor_hundredths: int = 50000
    reported_balance_hundredths: int | None = None
    estimated_remaining_hundredths: int | None = None
    reported_at: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    paid_requests_allowed: bool = False
    note: str = "Manual organisation balance snapshot; not a live provider balance. Other keys/products share these credits. Expires after 15 minutes."


class SarvamHealth(StrictModel):
    status: Literal["NOT_CONFIGURED", "NOT_TESTED", "LIVE_OK", "ERROR"]
    model: str = "sarvam-105b"
    budget_limit_paise: int | None = Field(ge=0)
    reserved_paise: int = Field(ge=0)
    requests: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    last_success_at: AwareDatetime | None = None
    last_error_code: str | None = None
    budget_note: str = "Conservative local reservations, not provider-billed spend."
    credit_safety: CreditSafety = Field(default_factory=CreditSafety)


class OcrResult(StrictModel):
    notice_id: Id
    job_id: str | None = None
    status: Literal["PENDING", "COMPLETED"]
    cache_hit: bool
    pages: int = Field(ge=0)
    extraction_id: Id | None = None
    provider: Literal["SARVAM_VISION"] = "SARVAM_VISION"


class ProcessingJob(StrictModel):
    notice_id: Id
    status: Literal['QUEUED','LEASED','RETRY','PAUSED','REVIEW_READY','HELD','COMPLETE']
    attempts: int = Field(ge=0)
    next_attempt_at: AwareDatetime
    lease_until: AwareDatetime | None = None
    last_error: str | None = None
    updated_at: AwareDatetime


class ProcessingQueue(StrictModel):
    jobs: list[ProcessingJob] = Field(default_factory=list)
    counts: dict[str,int] = Field(default_factory=dict)
    worker_active: bool = False


class NoticeDetail(StrictModel):
    analysis: NoticeAnalysis | None = None
    notice: DetectedNotice
    extracted_pages: list[str]
    source_listing_url: HttpUrl | None = None
    observed_link_title: str
    extraction_version: NonEmpty


class InboxItem(StrictModel):
    notification: InAppNotification
    match: RecipientMatch
    update: NoticeUpdate
    notice: DetectedNotice


class PlatformStatus(StrictModel):
    schema_version: Literal["2.0.0"] = SCHEMA_VERSION
    demo_mode: bool
    sarvam_status: Literal["NOT_CONFIGURED", "NOT_TESTED", "LIVE_OK", "ERROR"]
    disclaimer: str = DISCLAIMER


class RegisterRequest(StrictModel):
    email: EmailStr
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    adult_confirmed: bool

    @field_validator('adult_confirmed', mode='before')
    @classmethod
    def adult_registration(cls, value):
        if type(value) is not bool or not value:
            raise ValueError('Registration requires an adult account holder; guardians can follow exams without storing child details')
        return value


class PasswordRequestModel(StrictModel):
    # Passwords are opaque secrets. The general DTO whitespace normalization
    # must not silently change a password chosen by its owner.
    model_config = ConfigDict(extra='forbid',validate_assignment=True,str_strip_whitespace=False)


class LoginRequest(PasswordRequestModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class EmailRequest(StrictModel):
    email: EmailStr


class CompleteAccountRequest(PasswordRequestModel):
    token: SecretStr = Field(min_length=32, max_length=128)
    password: SecretStr = Field(min_length=15, max_length=128)


class PasswordChangeRequest(PasswordRequestModel):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=15, max_length=128)


class AccountDeletionRequest(PasswordRequestModel):
    password: SecretStr = Field(min_length=1, max_length=128)


class AuthConfig(StrictModel):
    registration_available: bool
    email_delivery_configured: bool
    deployment_mode: Literal['local','production']
    adult_accounts_only: bool = True
    support_email: EmailStr | None = None


class VoiceSearchResult(StrictModel):
    transcript: str = Field(max_length=4000)
    language_code: str
    exam_ids: list[Id] = Field(default_factory=list)
    action_taken: Literal[False] = False


class NoticeAudio(StrictModel):
    text: str
    audio_base64: str
    content_type: Literal['audio/wav'] = 'audio/wav'
    cache_hit: bool
    model: Literal['bulbul:v4-flash'] = 'bulbul:v4-flash'


class EvaluationReport(StrictModel):
    run_id: Id
    created_at: AwareDatetime
    dataset_label: Literal['DECLARED_SYNTHETIC_TEXT'] = 'DECLARED_SYNTHETIC_TEXT'
    dataset_sha256: Sha256
    engine_version: str
    cases: int = Field(ge=1)
    profiles: int = Field(ge=1)
    correct_transitions: int = Field(ge=0)
    counts_match: bool
    deterministic_replay: bool
    limitations: list[str]


class ServiceHealth(StrictModel):
    schema_version: Literal['2.0.0'] = SCHEMA_VERSION
    status: Literal['OK', 'NOT_READY']
    checks: dict[str, bool]
    monitoring_enabled: bool


class EmailActionResponse(StrictModel):
    status: Literal['REQUEST_ACCEPTED'] = 'REQUEST_ACCEPTED'
    message: str = 'If the address can receive this request, check its inbox. Delivery may take a few minutes.'


class AuthSession(StrictModel):
    user_id: Id
    email: EmailStr
    display_name: str
    role: Literal['USER','ADMIN']
    email_verified: bool
    expires_at: AwareDatetime
    csrf_token: str


class PublicUpdate(StrictModel):
    update_id: Id
    notice_id: Id
    cycle_id: Id
    title: str
    notice_type: NoticeType
    topics: list[Topic]
    publisher: str
    source_url: HttpUrl
    published_at: AwareDatetime
    first_seen_at: AwareDatetime
    source_published_on: date | None = None
    summary_en: str
    summary_hi: str | None = None
    evidence: list[EvidenceAnchor]


class PublicUpdatesResponse(StrictModel):
    updates: list[PublicUpdate] = Field(default_factory=list)
    total: int = Field(ge=0)


class PublicSource(StrictModel):
    source_id: Id
    publisher: str
    listing_url: HttpUrl
    enabled: bool
    last_success_at: AwareDatetime | None = None
    status: Literal['LIVE_MONITORED','SOURCE_CONFIGURED','UNAVAILABLE','CATALOG_ONLY']


# Gradual migration: the legacy names remain importable for code that already
# uses `from backend.schemas import ApplicantProfile`, etc. New code should use
# the explicit v2 names for v2 concepts and the shared legacy rule engine DTOs.
SourceEvidence = legacy.SourceEvidence
SourceDocument = legacy.SourceDocument
RuleDefinition = legacy.RuleDefinition
DecisionStatus = legacy.DecisionStatus
ApplicantDecision = legacy.ApplicantDecision
AmendmentRecord = legacy.AmendmentRecord
ApplicantProfile = legacy.ApplicantProfile
ImpactEvent = legacy.ImpactEvent
VerifiedExplanation = legacy.VerifiedExplanation


if __name__ == "__main__":
    for model in (
        ExamCatalogEntry, ExamCycle, OfficialSource, UserProfileV2,
        ExamSubscription, DetectedNotice, NoticeChange, NoticeUpdate,
        RecipientMatch, InAppNotification, AdminDashboardResponse,
        CatalogResponse, NotificationsResponse,
    ):
        _ = model.model_json_schema()
    print(f"NiyamPulse v{SCHEMA_VERSION}: Pydantic imports and JSON Schema generation OK")


def __getattr__(name: str):
    """Forward remaining v1 symbols without changing their payloads."""
    if not name.startswith("_") and hasattr(legacy, name):
        return getattr(legacy, name)
    raise AttributeError(name)
