"""Pure, uncommitted amendment planning; never a database apply operation.

The future service must verify provenance, publication chronology and explicit
human review, then atomically persist a plan with optimistic revision checking.
Callers cannot turn a plan into evidence that any of those steps happened.
"""
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from backend.legacy_schemas_v1 import AmendmentChange, ChangeOperation, RuleDefinition
from backend.services.rule_engine import (
    EngineError, content_fingerprint, rule_fingerprint, validated_rules,
)


@dataclass(frozen=True)
class AmendmentPlan:
    rules: tuple[RuleDefinition, ...]
    verified_rule_hashes: frozenset[str]


def change_fingerprint(change: AmendmentChange) -> str:
    checked = AmendmentChange.model_validate(change.model_dump(mode="json"))
    return content_fingerprint(checked.model_dump(mode="json"))


def _overlap(left: RuleDefinition, right: RuleDefinition) -> bool:
    return ((right.effective_until is None or left.effective_from < right.effective_until)
            and (left.effective_until is None or right.effective_from < left.effective_until))


def plan_amendment(
    rules: Sequence[RuleDefinition], changes: Sequence[AmendmentChange], *,
    scheme_id: str, verified_rule_hashes: Collection[str] = (),
    verified_change_hashes: Collection[str] = (),
) -> AmendmentPlan:
    """Return a fresh history or reject the entire batch; never mutate inputs.

    Attestations are supplied by a trusted upstream boundary. Rule hashes bind
    values, dates, scope and evidence; change hashes also bind revoke evidence.
    A replacement closes its target and transfers that target's verification
    only to the derived shortened interval, never to an arbitrary edited rule.
    """
    history = validated_rules(rules)
    checked_changes = [AmendmentChange.model_validate(c.model_dump(mode="json")) for c in changes]
    if not checked_changes:
        raise EngineError("EMPTY_AMENDMENT", "At least one explicit change is required")
    change_ids = [c.change_id for c in checked_changes]
    if len(change_ids) != len(set(change_ids)):
        raise EngineError("DUPLICATE_CHANGE_ID", "Change IDs must be unique")
    target_ids = [c.target_rule_id for c in checked_changes if c.target_rule_id is not None]
    if len(target_ids) != len(set(target_ids)):
        raise EngineError("DUPLICATE_TARGET", "A batch may target an existing rule only once")

    original = {r.rule_id: r for r in history}
    reserved_ids = set(original)
    trusted = set(verified_rule_hashes)
    change_trust = frozenset(verified_change_hashes)
    for change in checked_changes:
        if change_fingerprint(change) not in change_trust:
            raise EngineError("CHANGE_NOT_VERIFIED", "Change evidence and payload need upstream verification")
        target = None
        proposal = change.proposed_rule
        if change.operation != ChangeOperation.ADD:
            target = original.get(change.target_rule_id)
            if target is None:
                raise EngineError("TARGET_NOT_FOUND", "Target must identify one pre-existing rule")
            if target.scheme_id != scheme_id:
                raise EngineError("INCOMPATIBLE_TARGET", "Target belongs to another scheme")
            if rule_fingerprint(target) not in trusted:
                raise EngineError("RULE_NOT_VERIFIED", "Target is not verified")
            if (change.effective_from < target.effective_from or
                    (target.effective_until is not None and change.effective_from >= target.effective_until)):
                raise EngineError("TARGET_NOT_ACTIVE", "Target is not active on the change's effective date")

        if proposal is not None:
            if (proposal.scheme_id != scheme_id or
                    (target is not None and (proposal.rule_type != target.rule_type or proposal.scope_key != target.scope_key))):
                raise EngineError("INCOMPATIBLE_TARGET", "Replacement must preserve scheme, type and scope")
            if proposal.rule_id in reserved_ids:
                raise EngineError("RULE_ID_REUSED", "Every proposed rule needs a new ID")
            if rule_fingerprint(proposal) not in trusted:
                raise EngineError("RULE_NOT_VERIFIED", "Proposed rule is not verified")
            if (target is not None and target.effective_until is not None
                    and (proposal.effective_until is None or proposal.effective_until > target.effective_until)):
                raise EngineError("REPLACEMENT_EXCEEDS_TARGET_WINDOW", "Replacement would cross a previously established end boundary")
            reserved_ids.add(proposal.rule_id)

        if target is not None:
            history = [r for r in history if r.rule_id != target.rule_id]
            # No zero-length historical rule when the change starts on its start.
            if change.effective_from > target.effective_from:
                shortened = validated_rules([target.model_copy(update={"effective_until": change.effective_from})])[0]
                trusted.add(rule_fingerprint(shortened))
                history.append(shortened)
        if proposal is not None:
            history.append(proposal)

    history = validated_rules(history)
    relevant = [r for r in history if r.scheme_id == scheme_id]
    for index, left in enumerate(relevant):
        for right in relevant[index + 1:]:
            # Scope tokens carry no disjointness declaration. A profile may hold
            # multiple tokens, so different scopes cannot prove non-overlap.
            if left.rule_type == right.rule_type and _overlap(left, right):
                raise EngineError("OVERLAPPING_RULES", "Potentially overlapping same-type rules require review")
    return AmendmentPlan(
        rules=tuple(history),
        verified_rule_hashes=frozenset(rule_fingerprint(r) for r in history if rule_fingerprint(r) in trusted),
    )
