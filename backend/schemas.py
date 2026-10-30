"""NiyamPulse LIVE: v1 shared API/data contracts.

Python 3.12 + Pydantic 2.x. This module defines contracts, NOT business
logic. In particular it does not certify sources, resolve amendments,
evaluate rules, or generate verified explanations.

Run a schema smoke check from the repository root:
    py -3.12 -m pip install "pydantic>=2.9,<3"
    py -3.12 -m backend.schemas
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

SCHEMA_VERSION = "1.1.0"
DISCLAIMER = "Decision support only; not official approval."


class ContractModel(BaseModel):
    """Reject undeclared properties and normalize incidental whitespace."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )


Id = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]
DocCode = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1)]


class DecisionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


class RuleType(str, Enum):
    MINIMUM_MARKS = "minimum_marks"
    MAXIMUM_INCOME = "maximum_income_inr"
    APPLICATION_DEADLINE = "application_deadline"
    AGE_BOUNDS = "age_bounds"
    REQUIRED_DOCUMENTS = "required_documents"


class DocumentKind(str, Enum):
    ORIGINAL = "ORIGINAL"
    CORRIGENDUM = "CORRIGENDUM"


class ExtractionState(str, Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class IntakeState(str, Enum):
    RECEIVED = "RECEIVED"
    EXTRACTING = "EXTRACTING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    READY_TO_APPLY = "READY_TO_APPLY"
    APPLIED = "APPLIED"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"


class GateCheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class SourceMatchState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    MATCHED_CONFIGURED_SOURCE = "MATCHED_CONFIGURED_SOURCE"
    MISMATCH = "MISMATCH"


class GateRecommendation(str, Enum):
    MANUAL_REVIEW = "MANUAL_REVIEW"
    QUARANTINE = "QUARANTINE"
    ALLOW_REVIEW = "ALLOW_REVIEW"


class ReviewState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ChangeOperation(str, Enum):
    ADD = "ADD"
    REPLACE = "REPLACE"
    REVOKE = "REVOKE"


class ImpactDirection(str, Enum):
    IMPROVED = "IMPROVED"
    WORSENED = "WORSENED"
    UNCHANGED = "UNCHANGED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class SourceBox(ContractModel):
    """Normalized PDF page box; origin top-left, values in [0, 1]."""

    x0: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def bounds_are_ordered(self) -> "SourceBox":
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("source box must have positive width and height")
        return self


class SourceEvidence(ContractModel):
    """Literal anchor into an immutable extraction of a particular PDF."""

    document_id: Id
    document_sha256: Sha256
    extraction_id: Id
    page_number: int = Field(ge=1, description="1-based PDF page index")
    literal_quote: NonEmpty = Field(max_length=4000)
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=1)
    boxes: list[SourceBox] = Field(default_factory=list)

    @model_validator(mode="after")
    def offset_pair_is_valid(self) -> "SourceEvidence":
        if (self.start_char is None) != (self.end_char is None):
            raise ValueError("start_char and end_char must both be set or both absent")
        if self.start_char is not None and self.end_char <= self.start_char:
            raise ValueError("end_char must be greater than start_char")
        return self


class SourceDocument(ContractModel):
    document_id: Id
    workspace_id: Id
    filename: NonEmpty
    sha256: Sha256
    kind: DocumentKind
    language: Literal["en", "hi", "mixed", "other", "unknown"] = "unknown"
    published_on: date | None = None
    acquired_at: AwareDatetime
    source_url: HttpUrl | None = None
    issuing_authority: str | None = None
    reference_number: str | None = None
    extraction_state: ExtractionState = ExtractionState.PENDING
    extraction_id: Id | None = None
    intake_state: IntakeState = IntakeState.RECEIVED
    acquisition_channel: Literal["UPLOAD", "LOCAL_WATCH"] = "UPLOAD"
    processing_mode: Literal["LOCAL_PDF", "CACHED_EXTRACTION"] = "LOCAL_PDF"
    synthetic: bool = False
    diagnostics: list[str] = Field(default_factory=list)
    source_gate: SourceGateResult | None = None
    review_state: ReviewState = ReviewState.PENDING
    reviewed_by: str | None = None
    reviewed_at: AwareDatetime | None = None


class RuleBase(ContractModel):
    rule_id: Id
    scheme_id: Id
    scope_key: NonEmpty = "all_applicants"
    effective_from: date
    effective_until: date | None = None  # Exclusive boundary
    evidence: list[SourceEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def validity_window(self) -> "RuleBase":
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("effective_until must be after effective_from")
        return self


class MinimumMarksRule(RuleBase):
    rule_type: Literal["minimum_marks"] = "minimum_marks"
    min_marks_percent: float = Field(ge=0, le=100)


class MaximumIncomeRule(RuleBase):
    rule_type: Literal["maximum_income_inr"] = "maximum_income_inr"
    max_annual_income_inr: int = Field(ge=0)


class ApplicationDeadlineRule(RuleBase):
    rule_type: Literal["application_deadline"] = "application_deadline"
    deadline_on: date


class AgeBoundsRule(RuleBase):
    rule_type: Literal["age_bounds"] = "age_bounds"
    min_age_years: int = Field(ge=0, le=130)
    max_age_years: int = Field(ge=0, le=130)
    age_as_of: date

    @model_validator(mode="after")
    def age_range_is_valid(self) -> "AgeBoundsRule":
        if self.max_age_years < self.min_age_years:
            raise ValueError("max_age_years must be >= min_age_years")
        return self


class RequiredDocumentsRule(RuleBase):
    rule_type: Literal["required_documents"] = "required_documents"
    required_document_codes: list[DocCode] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_codes(self) -> "RequiredDocumentsRule":
        if len(self.required_document_codes) != len(set(self.required_document_codes)):
            raise ValueError("required_document_codes must be unique")
        return self


RuleDefinition: TypeAlias = Annotated[
    MinimumMarksRule
    | MaximumIncomeRule
    | ApplicationDeadlineRule
    | AgeBoundsRule
    | RequiredDocumentsRule,
    Field(discriminator="rule_type"),
]


class GateCheck(ContractModel):
    check_id: Id
    status: GateCheckStatus
    detail: NonEmpty


class SourceGateResult(ContractModel):
    """Source matched != proven authentic. Service layer must enforce gates."""

    source_match: SourceMatchState
    recommendation: GateRecommendation
    checks: list[GateCheck] = Field(min_length=1)
    checked_at: AwareDatetime

    @model_validator(mode="after")
    def gate_is_consistent(self) -> "SourceGateResult":
        if any(c.status == GateCheckStatus.FAIL for c in self.checks):
            if self.recommendation != GateRecommendation.QUARANTINE:
                raise ValueError("failed gate check requires QUARANTINE")
        if self.recommendation == GateRecommendation.ALLOW_REVIEW:
            if self.source_match != SourceMatchState.MATCHED_CONFIGURED_SOURCE:
                raise ValueError("ALLOW_REVIEW requires matched configured source")
            if any(c.status != GateCheckStatus.PASS for c in self.checks):
                raise ValueError("ALLOW_REVIEW requires every check to PASS")
        return self


class AmendmentChange(ContractModel):
    change_id: Id
    operation: ChangeOperation
    target_rule_id: Id | None = None
    proposed_rule: RuleDefinition | None = None
    effective_from: date
    amendment_evidence: list[SourceEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def operation_payload_matches(self) -> "AmendmentChange":
        if self.operation == ChangeOperation.ADD:
            if self.target_rule_id is not None or self.proposed_rule is None:
                raise ValueError("ADD requires proposed_rule and no target_rule_id")
        elif self.operation == ChangeOperation.REPLACE:
            if self.target_rule_id is None or self.proposed_rule is None:
                raise ValueError("REPLACE requires target_rule_id and proposed_rule")
        elif self.operation == ChangeOperation.REVOKE:
            if self.target_rule_id is None or self.proposed_rule is not None:
                raise ValueError("REVOKE requires target_rule_id and no proposed_rule")
        if self.proposed_rule is not None and self.proposed_rule.effective_from != self.effective_from:
            raise ValueError("proposed rule and change effective_from must match")
        return self


class AmendmentRecord(ContractModel):
    amendment_id: Id
    workspace_id: Id
    original_document_id: Id
    corrigendum_document_id: Id
    published_on: date | None = None
    intake_state: IntakeState = IntakeState.RECEIVED
    review_state: ReviewState = ReviewState.PENDING
    source_gate: SourceGateResult | None = None
    changes: list[AmendmentChange] = Field(default_factory=list)
    reviewed_by: str | None = None
    reviewed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def applied_requires_review_and_gate(self) -> "AmendmentRecord":
        if self.intake_state == IntakeState.APPLIED:
            if self.review_state != ReviewState.APPROVED:
                raise ValueError("APPLIED requires approved review")
            if self.source_gate is None or self.source_gate.recommendation != GateRecommendation.ALLOW_REVIEW:
                raise ValueError("APPLIED requires passing source gate")
        return self


class ApplicantProfile(ContractModel):
    applicant_id: Id
    workspace_id: Id
    display_name: NonEmpty
    scope_keys: list[NonEmpty] = Field(default_factory=lambda: ["all_applicants"])
    marks_percent: float | None = Field(default=None, ge=0, le=100)
    annual_household_income_inr: int | None = Field(default=None, ge=0)
    date_of_birth: date | None = None
    planned_submission_on: date | None = None
    available_document_codes: list[DocCode] = Field(default_factory=list)
    document_inventory_complete: bool = False
    updated_at: AwareDatetime


class RuleCheck(ContractModel):
    rule_id: Id
    rule_type: RuleType
    status: DecisionStatus
    reason_code: NonEmpty
    observed_value: str | None = None
    expected_value: NonEmpty
    evidence: list[SourceEvidence] = Field(default_factory=list)


class ApplicantDecision(ContractModel):
    applicant_id: Id
    as_of_date: date
    status: DecisionStatus
    checks: list[RuleCheck] = Field(default_factory=list)
    engine_version: NonEmpty
    rule_set_sha256: Sha256
    disclaimer: Literal["Decision support only; not official approval."] = DISCLAIMER


class DecisionTransition(ContractModel):
    applicant_id: Id
    before: ApplicantDecision
    after: ApplicantDecision
    direction: ImpactDirection

    @model_validator(mode="after")
    def same_applicant(self) -> "DecisionTransition":
        if self.before.applicant_id != self.applicant_id or self.after.applicant_id != self.applicant_id:
            raise ValueError("before/after must refer to the same applicant")
        if self.direction == ImpactDirection.IMPROVED:
            if (self.before.status, self.after.status) != (DecisionStatus.FAIL, DecisionStatus.PASS):
                raise ValueError("IMPROVED means an overall FAIL -> PASS transition")
        if self.direction == ImpactDirection.WORSENED:
            if (self.before.status, self.after.status) != (DecisionStatus.PASS, DecisionStatus.FAIL):
                raise ValueError("WORSENED means an overall PASS -> FAIL transition")
        if self.direction == ImpactDirection.UNCHANGED and self.before.status != self.after.status:
            raise ValueError("UNCHANGED requires identical overall statuses")
        return self


class ImpactCounts(ContractModel):
    evaluated: int = Field(ge=0)
    changed: int = Field(ge=0)
    improved: int = Field(ge=0)
    worsened: int = Field(ge=0)
    review_required: int = Field(ge=0)
    unchanged: int = Field(ge=0)

    @model_validator(mode="after")
    def partition_is_consistent(self) -> "ImpactCounts":
        if self.improved + self.worsened + self.review_required + self.unchanged != self.evaluated:
            raise ValueError("direction counts must sum to evaluated")
        if self.changed > self.evaluated:
            raise ValueError("changed cannot exceed evaluated")
        return self


class ImpactEvent(ContractModel):
    event_id: Id
    workspace_id: Id
    amendment_id: Id
    event_kind: Literal["PREVIEW", "APPLIED"]
    occurred_at: AwareDatetime
    before_rule_set_sha256: Sha256
    after_rule_set_sha256: Sha256
    counts: ImpactCounts
    transitions: list[DecisionTransition] = Field(default_factory=list)

    @model_validator(mode="after")
    def counts_match_transitions(self) -> "ImpactEvent":
        if len(self.transitions) != self.counts.evaluated:
            raise ValueError("transitions length must match counts.evaluated")
        directions = [t.direction for t in self.transitions]
        for value, count in (
            (ImpactDirection.IMPROVED, self.counts.improved),
            (ImpactDirection.WORSENED, self.counts.worsened),
            (ImpactDirection.REVIEW_REQUIRED, self.counts.review_required),
            (ImpactDirection.UNCHANGED, self.counts.unchanged),
        ):
            if directions.count(value) != count:
                raise ValueError(f"count for {value.value} differs from transitions")
        actual_changed = sum(t.before.status != t.after.status for t in self.transitions)
        if actual_changed != self.counts.changed:
            raise ValueError("changed must equal count of overall status transitions")
        return self


class EvidenceSentence(ContractModel):
    sentence_id: Id
    text: NonEmpty
    supporting_rule_ids: list[Id] = Field(min_length=1)
    evidence: list[SourceEvidence] = Field(min_length=1)


class VerifiedExplanation(ContractModel):
    applicant_id: Id
    language: Literal["en", "hi"]
    sentences: list[EvidenceSentence] = Field(min_length=1)
    decision_rule_set_sha256: Sha256
    numeric_and_date_tokens_checked: bool = False
    audio_asset_id: Id | None = None
    disclaimer: Literal["Decision support only; not official approval."] = DISCLAIMER

    @model_validator(mode="after")
    def audio_requires_numeric_guard(self) -> "VerifiedExplanation":
        if self.audio_asset_id is not None and not self.numeric_and_date_tokens_checked:
            raise ValueError("audio cannot be attached until numeric/date validation passes")
        return self


class WorkspaceState(ContractModel):
    schema_version: Literal["1.1.0"] = SCHEMA_VERSION
    workspace_id: Id
    revision: int = Field(ge=0)
    documents: list[SourceDocument] = Field(default_factory=list)
    amendments: list[AmendmentRecord] = Field(default_factory=list)
    active_rules: list[RuleDefinition] = Field(default_factory=list)
    profiles: list[ApplicantProfile] = Field(default_factory=list)
    decisions: list[ApplicantDecision] = Field(default_factory=list)
    latest_event: ImpactEvent | None = None
    scheme_id: Id | None = None
    as_of_date: date | None = None
    synthetic: bool = False
    watcher: WatcherHealth = Field(default_factory=lambda: WatcherHealth())


class TimelineSnapshot(ContractModel):
    schema_version: Literal["1.1.0"] = SCHEMA_VERSION
    workspace_id: Id
    as_of_date: date
    # When provided, exclude documents not known by this timestamp.
    known_at: AwareDatetime | None = None
    rule_set_sha256: Sha256
    effective_rules: list[RuleDefinition] = Field(default_factory=list)
    decisions: list[ApplicantDecision] = Field(default_factory=list)


class EventFeedResponse(ContractModel):
    schema_version: Literal["1.1.0"] = SCHEMA_VERSION
    workspace_id: Id
    events: list[ImpactEvent] = Field(default_factory=list)
    next_cursor: str | None = None


class ExplanationRequest(ContractModel):
    applicant_id: Id
    language: Literal["en", "hi"] = "hi"
    question: str | None = Field(default=None, max_length=500)
    expected_rule_set_sha256: Sha256


class EvaluationMetric(ContractModel):
    metric_id: Id
    correct: int = Field(ge=0)
    total: int = Field(ge=0)
    # Percentage is derived in frontend (correct/total); no invented score.

    @model_validator(mode="after")
    def numerator_lte_denominator(self) -> "EvaluationMetric":
        if self.correct > self.total:
            raise ValueError("correct cannot exceed total")
        return self


class EvaluationScorecard(ContractModel):
    schema_version: Literal["1.1.0"] = SCHEMA_VERSION
    run_id: Id
    dataset_id: Id
    synthetic: Literal[True] = True
    completed_at: AwareDatetime
    pipeline_revision: NonEmpty
    metrics: list[EvaluationMetric] = Field(min_length=1)
    baseline_metrics: list[EvaluationMetric] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ApplyAmendmentRequest(ContractModel):
    expected_workspace_revision: int = Field(ge=0)
    reviewed_by: NonEmpty
    confirm_source_review: Literal[True]


class PreviewAmendmentResponse(ContractModel):
    schema_version: Literal["1.1.0"] = SCHEMA_VERSION
    amendment: AmendmentRecord
    impact: ImpactEvent | None = None
    can_apply: bool
    blockers: list[str] = Field(default_factory=list)


class ApplyAmendmentResponse(ContractModel):
    schema_version: Literal["1.1.0"] = SCHEMA_VERSION
    workspace_revision: int = Field(ge=0)
    event: ImpactEvent


class ImportDocumentResponse(ContractModel):
    schema_version: Literal["1.1.0"] = SCHEMA_VERSION
    document: SourceDocument
    amendment_id: Id | None = None


class TranscriptResponse(ContractModel):
    schema_version: Literal["1.1.0"] = SCHEMA_VERSION
    language: str
    transcript: str
    provider: Literal["sarvam_saaras_v4", "offline_demo"]


class ApiError(ContractModel):
    error_code: Id
    message: NonEmpty
    request_id: Id | None = None
    details: dict[str, str] = Field(default_factory=dict)


class HealthResponse(ContractModel):
    status: Literal["ok"] = "ok"
    schema_version: Literal["1.1.0"] = SCHEMA_VERSION


class WatcherHealth(ContractModel):
    enabled: bool = False
    running: bool = False
    watched_directory: str | None = None
    last_scan_at: AwareDatetime | None = None
    last_error: str | None = None


class ExtractedPage(ContractModel):
    # Frozen extraction text must retain newlines and incidental whitespace.
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)
    page_number: int = Field(ge=1)
    text: str
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class DocumentExtraction(ContractModel):
    document_id: Id
    document_sha256: Sha256
    extraction_id: Id
    extractor_version: NonEmpty
    pages: list[ExtractedPage] = Field(min_length=1)


class ReviewOriginalRequest(ApplyAmendmentRequest):
    """Explicitly review a verified original; bootstrap only an empty rule history."""


if __name__ == "__main__":
    import json

    print(f"NiyamPulse schemas v{SCHEMA_VERSION}: import OK")
    print(json.dumps(WorkspaceState.model_json_schema(), indent=2)[:200])
