import hashlib
import json
from pathlib import Path
import unittest

from backend.synthetic_demo import FIXTURE_ROOT, load_case, parse_synthetic_clause, replay_case


class SyntheticPipelineTests(unittest.TestCase):
    def test_three_pairs_match_independent_gold_labels(self):
        paths = sorted(FIXTURE_ROOT.glob("*.json"))
        self.assertGreaterEqual(len(paths), 3)
        languages = set()
        for path in paths:
            raw = json.loads(path.read_text(encoding="utf-8"))
            languages.add(raw["language"])
            with self.subTest(case=path.stem):
                event = replay_case(path)
                expected = raw["gold"]
                actual = {t.applicant_id: [t.before.status.value, t.after.status.value, t.direction.value] for t in event.transitions}
                self.assertEqual(actual, expected["transitions"])
                self.assertEqual(event.counts.model_dump(), expected["counts"])
                self.assertEqual(event.event_kind, "PREVIEW")
                self.assertEqual(event, replay_case(path))
        self.assertTrue({"en", "hi"}.issubset(languages))

    def test_actual_source_hashes_quotes_and_page_offsets(self):
        for path in FIXTURE_ROOT.glob("*.json"):
            case = load_case(path)
            for rule in case.rules + tuple(c.proposed_rule for c in case.changes if c.proposed_rule):
                for anchor in rule.evidence:
                    doc = case.documents[anchor.document_id]
                    self.assertEqual(anchor.document_sha256, hashlib.sha256(doc).hexdigest())
                    text = doc.decode("utf-8")
                    self.assertEqual(text[anchor.start_char:anchor.end_char], anchor.literal_quote)
                    self.assertEqual(anchor.page_number, 1)
                    self.assertEqual(anchor.boxes, [])

    def test_unsupported_or_ambiguous_clause_is_rejected(self):
        for text in ["Minimum qualifying marks: 70% or 80%.", "All students approved.", "न्यूनतम अंक: अस्पष्ट।", "Maximum annual household income: INR 12.5."]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_synthetic_clause(text, "en" if text.isascii() else "hi")

    def test_engine_still_requires_verification_for_parsed_fixture_rules(self):
        from backend.services.rule_engine import evaluate_applicant
        from backend.legacy_schemas_v1 import DecisionStatus
        case = load_case(FIXTURE_ROOT / "marks_relaxed_en.json")
        result = evaluate_applicant(case.profiles[0], case.rules, scheme_id=case.scheme_id, as_of_date=case.as_of_date)
        self.assertEqual(result.status, DecisionStatus.UNKNOWN)
