from datetime import datetime, timezone
import hashlib
import unittest

from backend.schemas import SourceDocument, DocumentKind
from backend.services.pdf_intake import extract_pdf, parse_notice, verify_evidence
from backend.tests.pdf_support import notice_text, pdf_bytes


class PDFPipelineTests(unittest.TestCase):
    def document(self, data, kind="ORIGINAL"):
        return SourceDocument(document_id="pdf-test", workspace_id="workspace-demo", filename="synthetic.pdf",
                              sha256=hashlib.sha256(data).hexdigest(), kind=kind,
                              acquired_at=datetime(2026, 10, 30, tzinfo=timezone.utc), synthetic=True)

    def test_actual_pdf_to_rules_and_evidence(self):
        data = pdf_bytes()
        extraction = extract_pdf(data, "pdf-test")
        parsed = parse_notice(extraction)
        self.assertEqual(parsed.kind, DocumentKind.ORIGINAL)
        self.assertEqual(len(parsed.rules), 2)
        self.assertEqual(parsed.rules[0].min_marks_percent, 70)
        for rule in parsed.rules:
            self.assertTrue(verify_evidence(rule.evidence[0], extraction))
            self.assertEqual(rule.evidence[0].page_number, 1)
            self.assertEqual(rule.evidence[0].boxes, [])
            self.assertTrue(any(rule.effective_from.isoformat() in a.literal_quote for a in rule.evidence))
        self.assertEqual(extraction.document_sha256, hashlib.sha256(data).hexdigest())

    def test_corrigendum_parses_explicit_target(self):
        parsed = parse_notice(extract_pdf(pdf_bytes(notice_text("CORRIGENDUM")), "corr"))
        self.assertEqual(parsed.changes[0].target_rule_id, "marks-v1")
        self.assertEqual(parsed.changes[0].proposed_rule.min_marks_percent, 60)

    def test_tampered_quote_hash_page_offsets_and_boxes_rejected(self):
        extraction = extract_pdf(pdf_bytes(), "pdf-test")
        anchor = parse_notice(extraction).rules[0].evidence[0]
        for changes in [dict(literal_quote="Minimum qualifying marks: 99%."), dict(document_sha256="a" * 64), dict(document_id="other"), dict(extraction_id="other"), dict(page_number=2), dict(start_char=0, end_char=2), dict(boxes=[dict(x0=0.1,y0=0.1,x1=0.2,y1=0.2)])]:
            with self.subTest(changes=changes):
                self.assertFalse(verify_evidence(type(anchor).model_validate(anchor.model_dump() | changes), extraction))

    def test_unsupported_scanned_and_malformed_inputs_abstain(self):
        for data in [pdf_bytes(blank=True), pdf_bytes(notice_text(body="RULE unsupported | scope=all_applicants | All students approved.")), pdf_bytes(notice_text(effective="30/10/2026"))]:
            with self.assertRaises(ValueError):
                parse_notice(extract_pdf(data, "pdf-test"))
        with self.assertRaises(ValueError):
            extract_pdf(b"not a PDF", "pdf-test")
