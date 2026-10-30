"""Deterministic decision support for the five v1 rule types.

Verification hashes must come from a trusted caller that has checked source
evidence and lineage. An empty set is deliberately the safe default. This
module never verifies a PDF or treats evidence presence as verification.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Sequence
from datetime import date
import hashlib
import json

from pydantic import TypeAdapter

from backend.schemas import (
    ApplicantDecision, ApplicantProfile, DecisionStatus, RuleCheck,
    RuleDefinition, RuleType,
)

ENGINE_VERSION = "1.0.0"
_RULES = TypeAdapter(list[RuleDefinition])


class EngineError(ValueError):
    """Domain error; a future HTTP adapter must translate it to ApiError."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def content_fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validated_rules(rules: Sequence[RuleDefinition]) -> list[RuleDefinition]:
    # Reparse dumps: Pydantic models contain mutable lists, and model_copy(update=)
    # bypasses validation. Never let those shortcuts bypass a domain boundary.
    copies = _RULES.validate_python([r.model_dump(mode="json") for r in rules])
    ids = [r.rule_id for r in copies]
    if len(set(ids)) != len(ids):
        raise EngineError("DUPLICATE_RULE_ID", "Rule IDs must be unique across the supplied history")
    return sorted(copies, key=lambda r: r.rule_id)


def rule_fingerprint(rule: RuleDefinition) -> str:
    return content_fingerprint(validated_rules([rule])[0].model_dump(mode="json"))


def rule_set_fingerprint(
    rules: Sequence[RuleDefinition], *, verified_rule_hashes: Collection[str] = (),
) -> str:
    """Order-independent snapshot hash, including the supplied verification state."""
    trusted = frozenset(verified_rule_hashes)
    return content_fingerprint([
        {"rule": r.model_dump(mode="json"), "verified": rule_fingerprint(r) in trusted}
        for r in validated_rules(rules)
    ])


def effective_rules(
    rules: Sequence[RuleDefinition], *, scheme_id: str, as_of_date: date,
) -> list[RuleDefinition]:
    return [r for r in validated_rules(rules)
            if r.scheme_id == scheme_id and r.effective_from <= as_of_date
            and (r.effective_until is None or as_of_date < r.effective_until)]


def aggregate_status(statuses: Iterable[DecisionStatus]) -> DecisionStatus:
    present = set(statuses)
    return next((s for s in (DecisionStatus.CONFLICT, DecisionStatus.FAIL,
                            DecisionStatus.UNKNOWN, DecisionStatus.PASS)
                 if s in present), DecisionStatus.UNKNOWN)


def _expected(rule: RuleDefinition) -> str:
    match rule.rule_type:
        case "minimum_marks":
            return f">= {rule.min_marks_percent:g}%"
        case "maximum_income_inr":
            return f"<= INR {rule.max_annual_income_inr}"
        case "application_deadline":
            return f"<= {rule.deadline_on.isoformat()}"
        case "age_bounds":
            return f"{rule.min_age_years}..{rule.max_age_years} years on {rule.age_as_of.isoformat()}"
        case "required_documents":
            return ", ".join(sorted(rule.required_document_codes))
    raise EngineError("UNSUPPORTED_RULE_TYPE", "Unsupported rule type")


def _condition(rule: RuleDefinition, applicant: ApplicantProfile) -> tuple[DecisionStatus, str, str | None]:
    """Only called for a verified, unambiguous, applicable rule."""
    match rule.rule_type:
        case "minimum_marks":
            value = applicant.marks_percent
            passed = value is not None and value >= rule.min_marks_percent
            observed = None if value is None else f"{value:g}%"
        case "maximum_income_inr":
            value = applicant.annual_household_income_inr
            passed = value is not None and value <= rule.max_annual_income_inr
            observed = None if value is None else f"INR {value}"
        case "application_deadline":
            value = applicant.planned_submission_on
            passed = value is not None and value <= rule.deadline_on
            observed = None if value is None else value.isoformat()
        case "age_bounds":
            value = applicant.date_of_birth
            if value is not None and value > rule.age_as_of:
                return DecisionStatus.UNKNOWN, "BIRTH_DATE_AFTER_AGE_ANCHOR", value.isoformat()
            age = None if value is None else (
                rule.age_as_of.year - value.year
                - ((rule.age_as_of.month, rule.age_as_of.day) < (value.month, value.day))
            )
            passed = age is not None and rule.min_age_years <= age <= rule.max_age_years
            observed = None if age is None else str(age)
        case "required_documents":
            missing = set(rule.required_document_codes) - set(applicant.available_document_codes)
            observed = ", ".join(sorted(set(applicant.available_document_codes))) or "none recorded"
            if missing:
                if not applicant.document_inventory_complete:
                    return DecisionStatus.UNKNOWN, "DOCUMENT_INVENTORY_INCOMPLETE", observed
                return DecisionStatus.FAIL, "REQUIRED_DOCUMENTS_MISSING", observed
            return DecisionStatus.PASS, "REQUIRED_DOCUMENTS_PRESENT", observed
        case _:
            raise EngineError("UNSUPPORTED_RULE_TYPE", "Unsupported rule type")
    if value is None:
        return DecisionStatus.UNKNOWN, "PROFILE_VALUE_MISSING", None
    return (DecisionStatus.PASS, "CONDITION_MET", observed) if passed else (
        DecisionStatus.FAIL, "CONDITION_NOT_MET", observed)


def evaluate_applicant(
    applicant: ApplicantProfile, rules: Sequence[RuleDefinition], *,
    scheme_id: str, as_of_date: date, verified_rule_hashes: Collection[str] = (),
) -> ApplicantDecision:
    applicant = ApplicantProfile.model_validate(applicant.model_dump(mode="json"))
    snapshot = effective_rules(rules, scheme_id=scheme_id, as_of_date=as_of_date)
    relevant = [r for r in snapshot if r.scope_key == "all_applicants" or r.scope_key in applicant.scope_keys]
    trusted = frozenset(verified_rule_hashes)
    verified_ids = {r.rule_id for r in relevant if rule_fingerprint(r) in trusted}
    per_type = Counter(r.rule_type for r in relevant if r.rule_id in verified_ids)
    checks = []
    for rule in relevant:
        if rule.rule_id not in verified_ids:
            status, reason, observed = DecisionStatus.UNKNOWN, "SOURCE_NOT_VERIFIED", None
        elif per_type[rule.rule_type] > 1:
            status, reason, observed = DecisionStatus.CONFLICT, "OVERLAPPING_APPLICABLE_RULES", None
        else:
            status, reason, observed = _condition(rule, applicant)
        checks.append(RuleCheck(
            rule_id=rule.rule_id, rule_type=RuleType(rule.rule_type), status=status,
            reason_code=reason, observed_value=observed, expected_value=_expected(rule),
            evidence=rule.evidence,
        ))
    return ApplicantDecision(
        applicant_id=applicant.applicant_id, as_of_date=as_of_date,
        status=aggregate_status(c.status for c in checks), checks=checks,
        engine_version=ENGINE_VERSION,
        rule_set_sha256=rule_set_fingerprint(snapshot, verified_rule_hashes=trusted),
    )
