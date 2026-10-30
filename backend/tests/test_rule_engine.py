from datetime import date
import itertools
import unittest

from pydantic import ValidationError

from backend.schemas import ApplicantProfile, DecisionStatus as S
from backend.services.rule_engine import (
    EngineError, aggregate_status, evaluate_applicant, rule_fingerprint,
    rule_set_fingerprint,
)
from backend.tests.support import make_rule, profile, verified


DAY = date(2026, 10, 30)


class RuleEngineTests(unittest.TestCase):
    def decide(self, rules, applicant=None, on=DAY, trusted=True):
        return evaluate_applicant(
            applicant or profile(), rules, scheme_id="demo", as_of_date=on,
            verified_rule_hashes=verified(rules) if trusted else (),
        )

    def test_empty_and_unverified_are_unknown(self):
        self.assertEqual(self.decide([]).status, S.UNKNOWN)
        rule = make_rule()
        result = self.decide([rule], trusted=False)
        self.assertEqual(result.status, S.UNKNOWN)
        self.assertEqual(result.checks[0].reason_code, "SOURCE_NOT_VERIFIED")
        self.assertEqual(result.checks[0].evidence, rule.evidence)

    def test_every_aggregation_combination(self):
        self.assertEqual(aggregate_status([]), S.UNKNOWN)
        for size in range(1, 5):
            for statuses in itertools.product(S, repeat=size):
                expected = next(s for s in (S.CONFLICT, S.FAIL, S.UNKNOWN, S.PASS) if s in statuses)
                self.assertEqual(aggregate_status(statuses), expected)

    def test_marks_and_income_boundaries_and_missing(self):
        for kind, field, threshold, cases in (
            ("minimum_marks", "marks_percent", 70, [(69.99, S.FAIL), (70, S.PASS), (70.01, S.PASS), (None, S.UNKNOWN)]),
            ("maximum_income_inr", "annual_household_income_inr", 250000, [(250001, S.FAIL), (250000, S.PASS), (0, S.PASS), (None, S.UNKNOWN)]),
        ):
            rule = make_rule(kind, threshold)
            for value, expected in cases:
                with self.subTest(kind=kind, value=value):
                    result = self.decide([rule], profile(**{field: value}))
                    self.assertEqual(result.status, expected)
                    self.assertTrue(result.checks[0].reason_code)
                    self.assertEqual(result.checks[0].evidence, rule.evidence)

    def test_deadline_is_inclusive_date_only(self):
        rule = make_rule("application_deadline", "2026-10-30")
        for value, status in [("2026-10-29", S.PASS), ("2026-10-30", S.PASS), ("2026-10-31", S.FAIL), (None, S.UNKNOWN)]:
            self.assertEqual(self.decide([rule], profile(planned_submission_on=value)).status, status)

    def test_age_on_anchor_and_inclusive_bounds(self):
        rule = make_rule("age_bounds", (18, 25, "2026-10-30"))
        for born, status in [("2008-10-30", S.PASS), ("2008-10-31", S.FAIL), ("2000-10-31", S.PASS), ("2000-10-30", S.FAIL), (None, S.UNKNOWN), ("2027-01-01", S.UNKNOWN)]:
            self.assertEqual(self.decide([rule], profile(date_of_birth=born)).status, status)

    def test_leap_day_birthday_uses_march_first_in_non_leap_year(self):
        for anchor, expected in [("2026-02-28", S.FAIL), ("2026-03-01", S.PASS)]:
            rule = make_rule("age_bounds", (18, 25, anchor))
            self.assertEqual(self.decide([rule], profile(date_of_birth="2008-02-29")).status, expected)

    def test_document_inventory_distinguishes_missing_from_unknown(self):
        rule = make_rule("required_documents", ["ID", "INCOME"])
        for codes, complete, status in [([], False, S.UNKNOWN), ([], True, S.FAIL), (["ID"], False, S.UNKNOWN), (["ID"], True, S.FAIL), (["ID", "INCOME"], False, S.PASS)]:
            self.assertEqual(self.decide([rule], profile(available_document_codes=codes, document_inventory_complete=complete)).status, status)

    def test_effective_windows_scheme_and_scope(self):
        rule = make_rule(effective_from="2026-10-15", effective_until="2026-10-30")
        for day, status in [(date(2026, 10, 14), S.UNKNOWN), (date(2026, 10, 15), S.PASS), (DAY, S.UNKNOWN)]:
            self.assertEqual(self.decide([rule], on=day).status, status)
        self.assertEqual(self.decide([make_rule(scheme_id="other")]).status, S.UNKNOWN)
        scoped = make_rule(scope_key="region_a")
        self.assertEqual(self.decide([scoped]).status, S.UNKNOWN)
        self.assertEqual(self.decide([scoped], profile(scope_keys=["region_a"])).status, S.PASS)
        self.assertEqual(self.decide([make_rule()], profile(scope_keys=[])).status, S.PASS)

    def test_conflict_overrides_failure_and_only_relevant_rules_conflict(self):
        rules = [make_rule(rule_id="m1"), make_rule(value=80, rule_id="m2"), make_rule("maximum_income_inr", 0)]
        result = self.decide(rules)
        self.assertEqual(result.status, S.CONFLICT)
        self.assertEqual([c.status for c in result.checks].count(S.CONFLICT), 2)
        self.assertEqual(len(result.checks), 3)
        rules[1] = make_rule(rule_id="m2", scope_key="other")
        self.assertEqual(self.decide(rules).status, S.FAIL)

    def test_missing_information_does_not_mask_proven_failure(self):
        rules = [make_rule(), make_rule("maximum_income_inr", 100)]
        result = self.decide(rules, profile(marks_percent=None))
        self.assertEqual(result.status, S.FAIL)
        self.assertEqual({c.status for c in result.checks}, {S.FAIL, S.UNKNOWN})

    def test_verification_is_bound_to_full_rule_content(self):
        rule = make_rule()
        changed = make_rule(value=90)
        result = evaluate_applicant(profile(), [changed], scheme_id="demo", as_of_date=DAY, verified_rule_hashes=verified([rule]))
        self.assertEqual(result.status, S.UNKNOWN)
        self.assertNotEqual(rule_fingerprint(rule), rule_fingerprint(changed))

    def test_unverified_failure_is_unknown_and_multi_scope_overlap_is_conflict(self):
        self.assertEqual(self.decide([make_rule(value=90)], trusted=False).status, S.UNKNOWN)
        rules = [make_rule(rule_id="region-a", scope_key="region_a"), make_rule(rule_id="region-b", scope_key="region_b")]
        self.assertEqual(self.decide(rules, profile(scope_keys=["region_a", "region_b"])).status, S.CONFLICT)
        self.assertEqual(self.decide(rules, profile(scope_keys=["region_a"])).status, S.PASS)

    def test_hashes_and_output_are_deterministic_and_trust_sensitive(self):
        rules = [make_rule(), make_rule("required_documents", ["ID", "INCOME"])]
        trust = verified(rules)
        self.assertEqual(self.decide(rules), self.decide(list(reversed(rules))))
        self.assertEqual(rule_set_fingerprint(rules, verified_rule_hashes=trust), rule_set_fingerprint(list(reversed(rules)), verified_rule_hashes=trust))
        self.assertNotEqual(rule_set_fingerprint(rules), rule_set_fingerprint(rules, verified_rule_hashes=trust))
        decision = self.decide(rules)
        self.assertEqual(decision.disclaimer, "Decision support only; not official approval.")
        self.assertEqual(decision, type(decision).model_validate_json(decision.model_dump_json()))

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaises(EngineError) as error:
            self.decide([make_rule(), make_rule()])
        self.assertEqual(error.exception.code, "DUPLICATE_RULE_ID")

    def test_mutated_models_are_revalidated_and_inputs_not_modified(self):
        rule = make_rule()
        original = rule.model_dump_json()
        decision = self.decide([rule])
        decision.checks[0].evidence.clear()
        self.assertEqual(rule.model_dump_json(), original)
        rule.evidence.clear()
        with self.assertRaises(ValidationError):
            self.decide([rule])

    def test_schema_rejects_unsupported_rules_and_fractional_income(self):
        from pydantic import TypeAdapter
        from backend.schemas import RuleDefinition
        payload = make_rule().model_dump(mode="json")
        payload["rule_type"] = "caste_exception"
        with self.assertRaises(ValidationError):
            TypeAdapter(RuleDefinition).validate_python(payload)
        with self.assertRaises(ValidationError):
            profile(annual_household_income_inr=1.25)


if __name__ == "__main__":
    unittest.main()
