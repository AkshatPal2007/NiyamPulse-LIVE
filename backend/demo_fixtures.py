"""Reproducible, declared synthetic notices. No active-rule side effects."""
import pymupdf


def notice_text(kind="ORIGINAL", *, authority="Synthetic Scholarship Board", reference=None,
                amends=None, published=None, effective=None, body=None, scheme="scholarship-demo-2026"):
    original = kind == "ORIGINAL"
    return "\n".join([
        "NIYAMPULSE SYNTHETIC NOTICE v1",
        f"Kind: {kind}", f"Scheme: {scheme}", f"Authority: {authority}",
        f"Reference: {reference or ('SYN-ORIGINAL-01' if original else 'SYN-CORR-01')}",
        f"Published: {published or ('2026-10-01' if original else '2026-10-15')}",
        f"Amends: {amends or ('NONE' if original else 'SYN-ORIGINAL-01')}",
        f"Effective: {effective or ('2026-10-01' if original else '2026-10-15')}",
        "Language: en", "---",
        body or ("RULE marks-v1 | scope=all_applicants | Minimum qualifying marks: 70%.\n"
                 "RULE income-v1 | scope=all_applicants | Maximum annual household income: INR 250000."
                 if original else
                 "REPLACE marks-v1 WITH marks-v2 | scope=all_applicants | Minimum qualifying marks: 60%."),
    ])


def pdf_bytes(text=None, *, blank=False):
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=700, height=842)
        if not blank:
            page.insert_text((36, 48), text or notice_text(), fontsize=10)
        pdf.set_metadata({"title": "SYNTHETIC TEST ONLY - NiyamPulse", "author": "Synthetic fixture generator"})
        return pdf.tobytes(garbage=4, deflate=True, no_new_id=True)


def demo_pdfs():
    body = "\n".join([
        "RULE marks-v1 | scope=all_applicants | Minimum qualifying marks: 70%.",
        "RULE income-v1 | scope=all_applicants | Maximum annual household income: INR 250000.",
        "RULE deadline-v1 | scope=all_applicants | Application deadline: 2026-10-30.",
        "RULE age-v1 | scope=all_applicants | Age bounds: 18..25 years on 2026-10-30.",
        "RULE documents-v1 | scope=all_applicants | Required documents: ID, INCOME.",
    ])
    return {
        "synthetic_original.pdf": pdf_bytes(notice_text(body=body)),
        "synthetic_corrigendum.pdf": pdf_bytes(notice_text("CORRIGENDUM")),
        "synthetic_mismatch.pdf": pdf_bytes(notice_text("CORRIGENDUM", authority="Unmatched Synthetic Board", reference="SYN-MISMATCH-01")),
    }
