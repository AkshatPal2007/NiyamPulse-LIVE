"""V2 rule amendment bridge — pure, side-effect-free.

This module connects the Sarvam-validated RULE_CANDIDATE facts from a
DetectedNotice to the deterministic v1 rule engine. It:

  1. Converts ExtractedFact (RULE_CANDIDATE kind) from a VALIDATED NoticeAnalysis
     into legacy AmendmentChange objects.
  2. Validates the batch through plan_amendment (no contradictions, no reuse).
  3. For every opted-in subscriber with a populated profile, evaluates the
     applicant before and after the rule change, returning a PersonalImpactRow
     per subscriber. The caller (ExamService.review) persists these as
     PERSONAL_IMPACT or POSSIBLE_IMPACT RecipientMatch rows.

IMPORTANT: This module is intentionally pure and side-effect-free. It does
not read from or write to the database. All inputs must be provided by the
caller after ownership and authorization checks.

Supported rule_types (closed set from AGENTS.md §1 invariant 5):
    minimum_marks, maximum_income_inr, application_deadline,
    age_bounds, required_documents

Any RULE_CANDIDATE fact that cannot be mapped to this closed set is
quarantined as UNSUPPORTED and the corresponding notice is not publishable
through the standard path. The caller must reject it.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta, timezone
import re
import hashlib
import json
from pydantic import TypeAdapter
from backend.services.clauses import parse_closed_clause
from typing import Any

from backend.legacy_schemas_v1 import (
    AgeBoundsRule, AmendmentChange, ApplicantProfile, ApplicationDeadlineRule,
    ChangeOperation, DecisionStatus, MaximumIncomeRule, MinimumMarksRule,
    RequiredDocumentsRule, RuleDefinition, SourceEvidence,
)
from backend.services.amendments import change_fingerprint, plan_amendment
from backend.services.rule_engine import (
    EngineError, evaluate_applicant, rule_fingerprint,
)
from backend import schemas as s


# ── closed-set rule types the bridge can process ──────────────────────────────
_SUPPORTED_RULE_TYPES = frozenset({
    "minimum_marks",
    "maximum_income_inr",
    "application_deadline",
    "age_bounds",
    "required_documents",
})


@dataclass
class PersonalImpactRow:
    """Deterministic result for one opted-in subscriber.

    before/after are always both set when produced by this bridge. The caller
    decides the RecipientRelevance based on whether the status changed.
    """
    user_id: str
    subscription_id: str
    before: DecisionStatus
    after: DecisionStatus
    before_checks: list[Any] = field(default_factory=list)
    after_checks: list[Any] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.before != self.after

    @property
    def relevance(self) -> s.RecipientRelevance:
        if self.before is None:
            return s.RecipientRelevance.GENERAL_UPDATE
        if self.changed:
            return s.RecipientRelevance.PERSONAL_IMPACT
        # Profile opted in and was evaluated — no change
        return s.RecipientRelevance.POSSIBLE_IMPACT


@dataclass
class BridgeResult:
    """Output of apply_rule_bridge — ready to be persisted by the caller."""
    # Validated amendment plan (rules after applying changes)
    after_rules: tuple[RuleDefinition, ...]
    # Verified hash set for after rules (from plan_amendment)
    after_verified_hashes: frozenset[str]
    # Snapshot hash over the complete after rule set (for audit)
    after_rule_set_sha256: str
    # Per-subscriber impact (only opted-in profiles with enough data)
    impacts: list[PersonalImpactRow]
    # v2 NoticeChange objects (schema-validated, ready to embed in NoticeUpdate)
    notice_changes: list[s.NoticeChange]
    # Rule IDs of before-rules that were revoked by this publication
    revoked_rule_ids: frozenset[str]
    # All new rule IDs introduced
    added_rule_ids: frozenset[str]
    before_rule_set_sha256: str = ""


def _build_amendment_change(
    notice_change: s.NoticeChange,
    cycle_id: str,
    evidence_anchors: list[s.EvidenceAnchor],
) -> AmendmentChange:
    """Translate a v2 NoticeChange to a legacy AmendmentChange for plan_amendment."""
    from backend.legacy_schemas_v1 import SourceEvidence

    # Convert v2 EvidenceAnchor → legacy SourceEvidence
    leg_evidence = []
    for a in evidence_anchors:
        leg_evidence.append(SourceEvidence(
            document_id=a.document_id,
            document_sha256=a.document_sha256,
            extraction_id=a.extraction_id or "unknown",
            page_number=a.page_number,
            literal_quote=a.literal_quote,
            start_char=a.start_char,
            end_char=a.end_char,
        ))

    op_map = {"ADD": ChangeOperation.ADD, "REPLACE": ChangeOperation.REPLACE,
               "REVOKE": ChangeOperation.REVOKE}
    effective_from = (
        notice_change.proposed_rule.effective_from
        if notice_change.proposed_rule is not None
        else notice_change.effective_from
    )
    if effective_from is None:
        raise EngineError(
            "BRIDGE_MISSING_EFFECTIVE_FROM",
            f"NoticeChange {notice_change.change_id} has no effective_from date",
        )
    return AmendmentChange(
        change_id=notice_change.change_id,
        operation=op_map[notice_change.operation],
        target_rule_id=notice_change.target_rule_id,
        proposed_rule=notice_change.proposed_rule,
        effective_from=effective_from,
        amendment_evidence=leg_evidence,
    )


def apply_rule_bridge(
    *,
    notice_changes: list[s.NoticeChange],
    before_rules: list[RuleDefinition],
    before_verified_hashes: frozenset[str],
    scheme_id: str,
    subscribers: list[tuple[str, str, ApplicantProfile | None]],
    as_of_date: date,
    cycle_id: str,
    verified_change_hashes: frozenset[str] = frozenset(),
    verified_proposed_rule_hashes: frozenset[str] = frozenset(),
) -> BridgeResult:
    """Run the deterministic rule bridge and return impact results.

    Args:
        notice_changes: Validated NoticeChange list from the APPROVED analysis.
        before_rules: Current rule history for this cycle (may be empty for a
            new exam cycle with no prior rules).
        before_verified_hashes: Set of verified rule fingerprints for before_rules.
        scheme_id: Exam cycle id used as the rule scheme identifier.
        subscribers: List of (user_id, subscription_id, profile_or_None).
            Profile is None if the user has not opted in to personalization.
        as_of_date: Evaluation date (typically publication date).
        cycle_id: Exam cycle identifier (used for validation only; must match
            scheme_id in practice).

    Returns:
        BridgeResult with the new rule set and per-subscriber impacts.

    Raises:
        EngineError: If any change fails the amendment planner checks.
    """
    if not notice_changes:
        raise EngineError("BRIDGE_NO_CHANGES", "At least one NoticeChange is required")

    # Build legacy AmendmentChange objects from v2 NoticeChange
    legacy_changes: list[AmendmentChange] = []
    for nc in notice_changes:
        if nc.rule_type.value not in _SUPPORTED_RULE_TYPES:
            raise EngineError(
                "BRIDGE_UNSUPPORTED_RULE_TYPE",
                f"Rule type {nc.rule_type.value!r} is not in the closed supported set",
            )
        legacy_changes.append(_build_amendment_change(nc, cycle_id, nc.evidence))

    if scheme_id != cycle_id:
        raise EngineError("BRIDGE_CYCLE_MISMATCH", "Cycle and scheme must match")
    combined_before_hashes = before_verified_hashes
    change_hashes = verified_change_hashes
    all_before_hashes = before_verified_hashes | verified_proposed_rule_hashes

    plan = plan_amendment(
        before_rules, legacy_changes,
        scheme_id=scheme_id,
        verified_rule_hashes=all_before_hashes,
        verified_change_hashes=change_hashes,
    )

    from backend.services.rule_engine import rule_set_fingerprint
    after_sha256 = rule_set_fingerprint(
        list(plan.rules), verified_rule_hashes=plan.verified_rule_hashes,
    )

    # Track structural changes
    before_ids = {r.rule_id for r in before_rules}
    after_ids = {r.rule_id for r in plan.rules}
    revoked_ids = {c.target_rule_id for c in notice_changes if c.operation in {"REPLACE","REVOKE"}}
    added_ids = after_ids - before_ids

    # Per-subscriber impact (only for opted-in profiles with data)
    impacts: list[PersonalImpactRow] = []
    for user_id, sub_id, profile in subscribers:
        if profile is None:
            continue
        try:
            before_decision = evaluate_applicant(
                profile, before_rules,
                scheme_id=scheme_id, as_of_date=as_of_date,
                verified_rule_hashes=combined_before_hashes,
            )
            after_decision = evaluate_applicant(
                profile, list(plan.rules),
                scheme_id=scheme_id, as_of_date=as_of_date,
                verified_rule_hashes=plan.verified_rule_hashes,
            )
            impacts.append(PersonalImpactRow(
                user_id=user_id,
                subscription_id=sub_id,
                before=before_decision.status,
                after=after_decision.status,
                before_checks=before_decision.checks,
                after_checks=after_decision.checks,
            ))
        except EngineError:
            # Profile data is insufficient to evaluate; skip silently
            # (this applicant will still receive a GENERAL_UPDATE notification).
            continue

    return BridgeResult(
        after_rules=plan.rules,
        after_verified_hashes=plan.verified_rule_hashes,
        after_rule_set_sha256=after_sha256,
        impacts=impacts,
        notice_changes=notice_changes,
        revoked_rule_ids=frozenset(revoked_ids),
        added_rule_ids=frozenset(added_ids),
        before_rule_set_sha256=rule_set_fingerprint(before_rules,verified_rule_hashes=before_verified_hashes),
    )


def profile_from_v2(v2_profile: s.UserProfileV2, workspace_id: str = "v2") -> ApplicantProfile | None:
    """Convert a v2 UserProfileV2 to a legacy ApplicantProfile for the engine.

    Returns None if the profile has not opted in to personalization.
    """
    if not v2_profile.personalization_opt_in:
        return None
    try:
        return ApplicantProfile(
            applicant_id=v2_profile.user_id,
            workspace_id=workspace_id,
            display_name=v2_profile.display_name or v2_profile.user_id,
            marks_percent=v2_profile.marks_percent,
            annual_household_income_inr=v2_profile.annual_household_income_inr,
            date_of_birth=v2_profile.date_of_birth,
            planned_submission_on=None,   # not in v2 profile; deadlines evaluate as UNKNOWN
            available_document_codes=list(v2_profile.available_document_codes),
            document_inventory_complete=v2_profile.document_inventory_complete,
            scope_keys=[],
            updated_at=v2_profile.updated_at,
        )
    except Exception:
        return None


# Explicit source grammar: no guessed operations, scope, effective dates or targets.
_CONTEXT = re.compile(
    r"Published: (?P<published>\d{4}-\d{2}-\d{2}) \| "
    r"Effective: (?P<effective>\d{4}-\d{2}-\d{2}) \| "
    r"Scheme: (?P<scheme>[A-Za-z0-9._:-]+) \| "
    r"Operation: (?P<operation>ADD|REPLACE|REVOKE) \| "
    r"(?:Target: (?P<target>[A-Za-z0-9._:-]+) \| )?"
    r"Scope: (?P<scope>all_applicants) \| (?P<clause>.+)", re.DOTALL,
)


def facts_to_notice_changes(*, notice_id, cycle_id, facts, evidence_anchors,
                            published_on=None, before_rules=(), observed_on=None):
    """Support only explicit closed clauses. Any unsafe member holds the whole batch.

    Arbitrary exam prose is informational or review-only; this narrow grammar is
    intentionally not an assertion that all real-world eligibility is covered.
    """
    changes, diagnostics = [], []
    for fact in facts:
        if fact.kind in {"ANNOUNCEMENT", "EXAM_DATE"}: continue
        if fact.kind == "UNSUPPORTED_REQUIREMENT":
            diagnostics.append("UNSUPPORTED_REQUIREMENT: manual source review required")
            continue
        try:
            match = _CONTEXT.fullmatch(fact.literal_quote)
            if match is None: raise ValueError("could not be mapped: explicit source dates, operation, scheme and scope are required")
            context = match.groupdict()
            published = date.fromisoformat(context['published'])
            effective = date.fromisoformat(context['effective'])
            if context['scheme'] != cycle_id or effective < published:
                raise ValueError("Source cycle/chronology mismatch")
            if observed_on is not None and published>observed_on:raise ValueError('Publication date is later than acquisition in the local calendar')
            if published_on is not None and published != published_on:
                raise ValueError("Publication date differs from source")
            anchors = [a for a in evidence_anchors if a.document_id == notice_id and a.page_number == fact.page_number and a.literal_quote == fact.literal_quote and a.extraction_id and a.start_char is not None]
            if len(anchors) != 1: raise ValueError("Exactly one verified page anchor is required")
            op, target_id = context['operation'], context['target']
            targets = [r for r in before_rules if r.rule_id == target_id]
            target = targets[0] if len(targets) == 1 else None
            if op == "ADD" and target_id is not None: raise ValueError("ADD cannot select a target")
            if op != "ADD" and (target is None or target.scheme_id != cycle_id or target.scope_key != context['scope'] or not (target.effective_from <= effective and (target.effective_until is None or effective < target.effective_until))):
                raise ValueError("Target must identify one relevant effective rule")
            identity = hashlib.sha256(json.dumps([cycle_id,anchors[0].document_sha256,anchors[0].extraction_id,fact.literal_quote],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:32]
            if op == "REVOKE":
                if context['clause'] != f"Rule type: {target.rule_type}.": raise ValueError("Revocation type does not match target")
                rule_type, proposal = target.rule_type, None
            else:
                language = 'hi' if re.search(r'[\u0900-\u097f]',context['clause']) else 'en'
                fields = parse_closed_clause(context['clause'],language)
                rule_type = fields['rule_type']
                if fact.date_value is not None and (rule_type!='application_deadline' or date.fromisoformat(fields['deadline_on'])!=fact.date_value):raise ValueError('Date value differs from literal clause')
                if target is not None and target.rule_type != rule_type: raise ValueError("Replacement must preserve type")
                leg = [SourceEvidence(document_id=a.document_id,document_sha256=a.document_sha256,extraction_id=a.extraction_id,page_number=a.page_number,literal_quote=a.literal_quote,start_char=a.start_char,end_char=a.end_char) for a in anchors]
                proposal = TypeAdapter(RuleDefinition).validate_python(dict(rule_id='rule-'+identity,scheme_id=cycle_id,scope_key=context['scope'],effective_from=effective,evidence=leg,**fields))
            changes.append(s.NoticeChange(change_id='change-'+identity,notice_id=notice_id,rule_type=rule_type,operation=op,target_rule_id=target_id,proposed_rule=proposal,effective_from=effective,evidence=anchors))
        except (ValueError,TypeError) as error:
            diagnostics.append(str(error))
    if diagnostics: return [], diagnostics
    return changes, []


def verify_change_proposals(analysis, notice, before_rules):
    """Recompute typed values/targets from frozen candidate quotes at publication.

    Caller must first verify byte hashes, immutable extraction, exact anchors and
    publisher lineage. This function does not turn evidence presence into trust.
    """
    if analysis.candidate is None: raise EngineError('RULE_SOURCE_REQUIRED','Validated source facts are required')
    recomputed, diagnostics = facts_to_notice_changes(notice_id=notice.notice_id,cycle_id=notice.cycle_id,facts=analysis.candidate.facts,evidence_anchors=analysis.evidence,published_on=notice.published_on,before_rules=before_rules,observed_on=notice.first_seen_at.astimezone(timezone(timedelta(hours=5,minutes=30))).date())
    if diagnostics or not recomputed or recomputed != analysis.notice_changes:
        raise EngineError('RULE_PROPOSAL_NOT_VERIFIED','Rule values, dates, scope or target differ from supported literal source clauses')
    legacy = [_build_amendment_change(c,notice.cycle_id,c.evidence) for c in recomputed]
    return (frozenset(change_fingerprint(c) for c in legacy),
            frozenset(rule_fingerprint(c.proposed_rule) for c in recomputed if c.proposed_rule))
