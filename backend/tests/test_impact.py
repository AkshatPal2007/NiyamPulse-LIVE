from datetime import date, datetime, timezone
import itertools
import unittest

from backend.legacy_schemas_v1 import DecisionStatus as S, ImpactDirection as D, ImpactEvent
from backend.services.impact import classify_transition, preview_impact
from backend.services.rule_engine import EngineError
from backend.tests.support import make_rule, profile, verified


class ImpactTests(unittest.TestCase):
    def preview(self, profiles, before, after, **overrides):
        args = dict(event_id="synthetic-preview", workspace_id="workspace-demo", amendment_id="synthetic-amendment",
                    scheme_id="demo", as_of_date=date(2026, 10, 30), occurred_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
                    before_verified_rule_hashes=verified(before), after_verified_rule_hashes=verified(after))
        return preview_impact(profiles, before, after, **(args | overrides))

    def test_all_sixteen_transition_directions(self):
        for before, after in itertools.product(S, repeat=2):
            expected = D.UNCHANGED if before == after else D.IMPROVED if (before, after) == (S.FAIL, S.PASS) else D.WORSENED if (before, after) == (S.PASS, S.FAIL) else D.REVIEW_REQUIRED
            self.assertEqual(classify_transition(before, after), expected)

    def test_real_counts_checks_and_round_trip(self):
        before, after = [make_rule(value=80)], [make_rule(value=70, rule_id="v2")]
        people = [profile(applicant_id="improved", marks_percent=75), profile(applicant_id="still-fail", marks_percent=65), profile(applicant_id="unknown", marks_percent=None), profile(applicant_id="still-pass", marks_percent=90)]
        result = self.preview(people, before, after)
        self.assertEqual(result.event_kind, "PREVIEW")
        self.assertEqual(result.counts.model_dump(), dict(evaluated=4, changed=1, improved=1, worsened=0, review_required=0, unchanged=3))
        self.assertNotEqual(result.transitions[1].before.checks, result.transitions[1].after.checks)
        self.assertEqual(result, ImpactEvent.model_validate_json(result.model_dump_json()))
        self.assertEqual(result, self.preview(list(reversed(people)), before, after))

    def test_worsened_unknown_and_conflict_counts(self):
        for before, after, direction in [([make_rule(value=70)], [make_rule(value=80)], D.WORSENED), ([], [make_rule()], D.REVIEW_REQUIRED), ([make_rule()], [make_rule(), make_rule(rule_id="duplicate-type")], D.REVIEW_REQUIRED)]:
            event = self.preview([profile()], before, after)
            self.assertEqual(event.transitions[0].direction, direction)
            self.assertEqual(event.counts.changed, 1)

    def test_duplicate_and_cross_workspace_profiles_rejected(self):
        for people, code in [([profile(), profile()], "DUPLICATE_APPLICANT_ID"), ([profile(workspace_id="other")], "WORKSPACE_MISMATCH")]:
            with self.assertRaises(EngineError) as error:
                self.preview(people, [], [])
            self.assertEqual(error.exception.code, code)

    def test_empty_cohort_and_naive_timestamp(self):
        event = self.preview([], [], [])
        self.assertEqual(event.counts.evaluated, 0)
        self.assertEqual(event.counts.changed, 0)
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self.preview([], [], [], occurred_at=datetime(2026, 10, 30))
