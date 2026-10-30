from datetime import date
import unittest

from backend.schemas import AmendmentChange, DecisionStatus as S
from backend.services.amendments import change_fingerprint, plan_amendment
from backend.services.rule_engine import EngineError, evaluate_applicant, rule_fingerprint
from backend.tests.support import evidence, make_rule, profile, verified


def change(operation="REPLACE", target="rule-minimum_marks", proposed=None, when="2026-10-15", change_id="change-1"):
    return AmendmentChange.model_validate(dict(
        change_id=change_id, operation=operation, target_rule_id=target,
        proposed_rule=proposed, effective_from=when, amendment_evidence=[evidence()],
    ))


class AmendmentTests(unittest.TestCase):
    def plan(self, rules, changes, **kwargs):
        proposals = [c.proposed_rule for c in changes if c.proposed_rule is not None]
        return plan_amendment(rules, changes, scheme_id="demo", **(dict(
            verified_rule_hashes=verified(rules + proposals),
            verified_change_hashes={change_fingerprint(c) for c in changes},
        ) | kwargs))

    def assert_blocked(self, code, rules, changes, **kwargs):
        before = [r.model_dump_json() for r in rules]
        with self.assertRaises(EngineError) as error:
            self.plan(rules, changes, **kwargs)
        self.assertEqual(error.exception.code, code)
        self.assertEqual([r.model_dump_json() for r in rules], before)

    def test_replace_preserves_history_and_unrelated_rules(self):
        rules = [make_rule(), make_rule("maximum_income_inr", 250000)]
        before = [r.model_dump_json() for r in rules]
        newer = make_rule(value=60, rule_id="marks-v2", effective_from="2026-10-15")
        planned = self.plan(rules, [change(proposed=newer)])
        self.assertEqual(before, [r.model_dump_json() for r in rules])
        self.assertEqual(next(r for r in planned.rules if r.rule_id == rules[1].rule_id), rules[1])
        for day, expected in [(date(2026, 10, 14), S.FAIL), (date(2026, 10, 15), S.PASS)]:
            result = evaluate_applicant(profile(marks_percent=65), planned.rules, scheme_id="demo", as_of_date=day, verified_rule_hashes=planned.verified_rule_hashes)
            self.assertEqual(result.status, expected)

    def test_later_unrelated_change_does_not_erase_earlier_amendment(self):
        rules = [make_rule(), make_rule("maximum_income_inr", 250000)]
        first = self.plan(rules, [change(proposed=make_rule(value=60, rule_id="marks-v2", effective_from="2026-10-15"))])
        second = self.plan(list(first.rules), [change(target="rule-maximum_income_inr", proposed=make_rule("maximum_income_inr", 300000, rule_id="income-v2", effective_from="2026-10-20"), when="2026-10-20")])
        self.assertIn("marks-v2", {r.rule_id for r in second.rules})
        self.assertEqual(next(r for r in second.rules if r.rule_id == "marks-v2").effective_until, None)

    def test_add_and_revoke_and_same_day_replacement(self):
        docs = make_rule("required_documents", ["ID"], effective_from="2026-10-15")
        addition = self.plan([make_rule()], [change("ADD", None, docs)])
        self.assertEqual(len(addition.rules), 2)
        removal = self.plan(list(addition.rules), [change("REVOKE", docs.rule_id, when="2026-10-20")])
        self.assertEqual(next(r for r in removal.rules if r.rule_id == docs.rule_id).effective_until, date(2026, 10, 20))
        replacement = make_rule(rule_id="new", effective_from="2026-10-01")
        same_day = self.plan([make_rule()], [change(proposed=replacement, when="2026-10-01")])
        self.assertEqual([r.rule_id for r in same_day.rules], ["new"])
        self.assertEqual(len(self.plan([make_rule()], [change("REVOKE", when="2026-10-01")]).rules), 0)

    def test_unknown_targets_reused_ids_and_empty_batches(self):
        rules = [make_rule()]
        self.assert_blocked("EMPTY_AMENDMENT", rules, [])
        self.assert_blocked("TARGET_NOT_FOUND", rules, [change("REVOKE", "missing")])
        self.assert_blocked("RULE_ID_REUSED", rules, [change(proposed=make_rule(effective_from="2026-10-15"))])

    def test_incompatible_scope_type_and_scheme(self):
        for updates in [dict(scope_key="region_a"), dict(scheme_id="other")]:
            newer = make_rule(rule_id="v2", effective_from="2026-10-15", **updates)
            self.assert_blocked("INCOMPATIBLE_TARGET", [make_rule()], [change(proposed=newer)])
        income = make_rule("maximum_income_inr", 250000, effective_from="2026-10-15")
        self.assert_blocked("INCOMPATIBLE_TARGET", [make_rule()], [change(proposed=income)])
        self.assert_blocked("INCOMPATIBLE_TARGET", [make_rule(scheme_id="other")], [change("REVOKE")])

    def test_chronology_and_existing_end_boundary(self):
        self.assert_blocked("TARGET_NOT_ACTIVE", [make_rule()], [change("REVOKE", when="2026-09-30")])
        bounded = make_rule(effective_until="2026-10-20")
        self.assert_blocked("TARGET_NOT_ACTIVE", [bounded], [change("REVOKE", when="2026-10-20")])
        newer = make_rule(rule_id="v2", effective_from="2026-10-15")
        self.assert_blocked("REPLACEMENT_EXCEEDS_TARGET_WINDOW", [bounded], [change(proposed=newer)])

    def test_conflicts_are_blocked_including_potentially_overlapping_scopes(self):
        for scope in ["all_applicants", "region_a", "region_b"]:
            newer = make_rule(rule_id="v2", effective_from="2026-10-15", scope_key=scope)
            self.assert_blocked("OVERLAPPING_RULES", [make_rule()], [change("ADD", None, newer)])
        # Adjacent intervals are safe.
        newer = make_rule(rule_id="v2", effective_from="2026-10-15")
        planned = self.plan([make_rule(effective_until="2026-10-15")], [change("ADD", None, newer)])
        self.assertEqual(len(planned.rules), 2)

    def test_entire_batch_is_rejected_without_partial_changes(self):
        first = change(proposed=make_rule(rule_id="v2", effective_from="2026-10-15"))
        second = change("REVOKE", "missing", change_id="change-2")
        self.assert_blocked("TARGET_NOT_FOUND", [make_rule()], [first, second])
        self.assert_blocked("DUPLICATE_TARGET", [make_rule()], [first, change("REVOKE", change_id="change-2")])
        self.assert_blocked("DUPLICATE_CHANGE_ID", [make_rule()], [first, first])

    def test_verification_required_for_change_target_and_proposal(self):
        original = make_rule()
        proposal = make_rule(rule_id="v2", effective_from="2026-10-15")
        changes = [change(proposed=proposal)]
        self.assert_blocked("CHANGE_NOT_VERIFIED", [original], changes, verified_change_hashes=())
        self.assert_blocked("RULE_NOT_VERIFIED", [original], changes, verified_rule_hashes=verified([original]))
        self.assert_blocked("RULE_NOT_VERIFIED", [original], [change("REVOKE")], verified_rule_hashes=())
        # A checked change cannot be edited while retaining its attestation.
        altered = changes[0].model_copy(update={"effective_from": date(2026, 10, 16), "proposed_rule": make_rule(rule_id="v2", effective_from="2026-10-16")})
        self.assert_blocked("CHANGE_NOT_VERIFIED", [original], [altered], verified_change_hashes={change_fingerprint(changes[0])})

    def test_planned_verification_does_not_survive_mutating_output(self):
        planned = self.plan([make_rule()], [change("REVOKE")])
        changed = planned.rules[0]
        changed.min_marks_percent = 90
        self.assertNotIn(rule_fingerprint(changed), planned.verified_rule_hashes)

    def test_open_end_is_unbounded_even_on_largest_representable_date(self):
        rules = [make_rule(effective_from="9999-12-31")]
        proposal = make_rule(rule_id="v2", effective_from="9999-12-31")
        self.assert_blocked("OVERLAPPING_RULES", rules, [change("ADD", None, proposal, when="9999-12-31")])

    def test_independent_batch_changes_are_order_independent(self):
        rules = [make_rule(), make_rule("maximum_income_inr", 250000)]
        changes = [
            change(proposed=make_rule(rule_id="marks-v2", effective_from="2026-10-15")),
            change(target="rule-maximum_income_inr", proposed=make_rule("maximum_income_inr", 300000, rule_id="income-v2", effective_from="2026-10-15"), change_id="income-change"),
        ]
        self.assertEqual(self.plan(rules, changes), self.plan(rules, list(reversed(changes))))
