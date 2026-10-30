"""Deterministic, side-effect-free PREVIEW impact calculation."""
from collections import Counter
from collections.abc import Collection, Sequence
from datetime import date, datetime

from backend.schemas import (
    ApplicantProfile, DecisionStatus, DecisionTransition, ImpactCounts,
    ImpactDirection, ImpactEvent, RuleDefinition,
)
from backend.services.rule_engine import (
    EngineError, effective_rules, evaluate_applicant, rule_set_fingerprint,
)


def classify_transition(before: DecisionStatus, after: DecisionStatus) -> ImpactDirection:
    if before == after:
        return ImpactDirection.UNCHANGED
    if (before, after) == (DecisionStatus.FAIL, DecisionStatus.PASS):
        return ImpactDirection.IMPROVED
    if (before, after) == (DecisionStatus.PASS, DecisionStatus.FAIL):
        return ImpactDirection.WORSENED
    return ImpactDirection.REVIEW_REQUIRED


def preview_impact(
    profiles: Sequence[ApplicantProfile], before_rules: Sequence[RuleDefinition],
    after_rules: Sequence[RuleDefinition], *, event_id: str, workspace_id: str,
    amendment_id: str, scheme_id: str, as_of_date: date, occurred_at: datetime,
    before_verified_rule_hashes: Collection[str] = (),
    after_verified_rule_hashes: Collection[str] = (),
) -> ImpactEvent:
    """Compare the same cohort and calendar date. Never emits APPLIED.

    IDs and an aware timestamp are explicit inputs for reproducible replay;
    stable event allocation and persistence belong to the future API service.
    """
    people = [ApplicantProfile.model_validate(p.model_dump(mode="json")) for p in profiles]
    ids = [p.applicant_id for p in people]
    if len(ids) != len(set(ids)):
        raise EngineError("DUPLICATE_APPLICANT_ID", "Cohort must contain unique applicant IDs")
    if any(p.workspace_id != workspace_id for p in people):
        raise EngineError("WORKSPACE_MISMATCH", "All applicants must belong to the requested workspace")
    before_snapshot = effective_rules(before_rules, scheme_id=scheme_id, as_of_date=as_of_date)
    after_snapshot = effective_rules(after_rules, scheme_id=scheme_id, as_of_date=as_of_date)
    transitions = []
    for person in sorted(people, key=lambda p: p.applicant_id):
        before = evaluate_applicant(person, before_snapshot, scheme_id=scheme_id,
                                    as_of_date=as_of_date, verified_rule_hashes=before_verified_rule_hashes)
        after = evaluate_applicant(person, after_snapshot, scheme_id=scheme_id,
                                   as_of_date=as_of_date, verified_rule_hashes=after_verified_rule_hashes)
        transitions.append(DecisionTransition(
            applicant_id=person.applicant_id, before=before, after=after,
            direction=classify_transition(before.status, after.status),
        ))
    directions = Counter(t.direction for t in transitions)
    return ImpactEvent(
        event_id=event_id, workspace_id=workspace_id, amendment_id=amendment_id,
        event_kind="PREVIEW", occurred_at=occurred_at,
        before_rule_set_sha256=rule_set_fingerprint(before_snapshot, verified_rule_hashes=before_verified_rule_hashes),
        after_rule_set_sha256=rule_set_fingerprint(after_snapshot, verified_rule_hashes=after_verified_rule_hashes),
        counts=ImpactCounts(
            evaluated=len(transitions), changed=sum(t.before.status != t.after.status for t in transitions),
            improved=directions[ImpactDirection.IMPROVED], worsened=directions[ImpactDirection.WORSENED],
            review_required=directions[ImpactDirection.REVIEW_REQUIRED], unchanged=directions[ImpactDirection.UNCHANGED],
        ), transitions=transitions,
    )
