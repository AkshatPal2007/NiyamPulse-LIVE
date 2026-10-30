"""Actual PyMuPDF extraction and a strict v1 notice-template parser.

Only the declared template is supported until sponsor candidate extraction is
integrated. Unknown text, scans, duplicate metadata and ambiguous targets abstain.
No coordinate highlighting is claimed; verified literal page text is returned.
"""
from dataclasses import dataclass
from datetime import date
import hashlib
import re
from threading import RLock

import pymupdf
from pydantic import TypeAdapter

from backend.legacy_schemas_v1 import (
    AmendmentChange, DocumentExtraction, DocumentKind, ExtractedPage,
    RuleDefinition, SourceEvidence,
)
from backend.services.clauses import parse_closed_clause

EXTRACTOR_VERSION = f"pymupdf-{pymupdf.VersionBind}-plain-v1"
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PAGES = 20
_PDF_LOCK = RLock()  # PyMuPDF must not be used concurrently by worker threads.
_RULE = TypeAdapter(RuleDefinition)
_TOKEN = r"[A-Za-z0-9][A-Za-z0-9._:-]*"


def extract_pdf(data: bytes, document_id: str) -> DocumentExtraction:
    if not data.startswith(b"%PDF-") or len(data) > MAX_PDF_BYTES:
        raise ValueError("A PDF of at most 10 MiB is required")
    digest = hashlib.sha256(data).hexdigest()
    extraction_id = "ext-" + hashlib.sha256(f"{digest}:{EXTRACTOR_VERSION}".encode()).hexdigest()
    try:
        with _PDF_LOCK, pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass or not 1 <= pdf.page_count <= MAX_PAGES:
                raise ValueError("Encrypted PDFs and PDFs outside the 1..20 page limit are unsupported")
            pages = [ExtractedPage(page_number=i + 1, text=page.get_text("text", sort=True),
                                   width=page.rect.width, height=page.rect.height)
                     for i, page in enumerate(pdf)]
    except (pymupdf.FileDataError, RuntimeError) as error:
        raise ValueError("PDF could not be extracted") from error
    return DocumentExtraction(document_id=document_id, document_sha256=digest,
                              extraction_id=extraction_id, extractor_version=EXTRACTOR_VERSION, pages=pages)


def verify_evidence(anchor: SourceEvidence, extraction: DocumentExtraction) -> bool:
    if (anchor.document_id != extraction.document_id or anchor.document_sha256 != extraction.document_sha256
            or anchor.extraction_id != extraction.extraction_id or anchor.boxes):
        return False
    if not 1 <= anchor.page_number <= len(extraction.pages):
        return False
    page = extraction.pages[anchor.page_number - 1]
    if page.page_number != anchor.page_number:
        return False
    if anchor.start_char is None or anchor.end_char is None:
        # No offset still needs an unambiguous exact literal occurrence.
        return page.text.count(anchor.literal_quote) == 1
    return page.text[anchor.start_char:anchor.end_char] == anchor.literal_quote


@dataclass(frozen=True)
class ParsedNotice:
    kind: DocumentKind
    scheme_id: str
    authority: str
    reference: str
    published_on: date
    amends_reference: str
    effective_from: date
    language: str
    rules: tuple[RuleDefinition, ...]
    changes: tuple[AmendmentChange, ...]


def parse_notice(extraction: DocumentExtraction) -> ParsedNotice:
    lines = []
    for page in extraction.pages:
        offset = 0
        for raw in page.text.splitlines(keepends=True):
            quote = raw.rstrip("\r\n")
            if quote.strip():
                if quote != quote.strip():
                    raise ValueError("Notice lines must not have ambiguous surrounding whitespace")
                lines.append((quote, SourceEvidence(
                    document_id=extraction.document_id, document_sha256=extraction.document_sha256,
                    extraction_id=extraction.extraction_id, page_number=page.page_number,
                    literal_quote=quote, start_char=offset, end_char=offset + len(quote),
                )))
            offset += len(raw)
    if not lines:
        raise ValueError("No usable embedded text; OCR is not configured")
    if lines[0][0] not in {"NIYAMPULSE NOTICE v1", "NIYAMPULSE SYNTHETIC NOTICE v1"}:
        raise ValueError("Unsupported notice format; structured extraction requires manual review")
    metadata, metadata_anchors = {}, {}
    separator = next((i for i, (text, _) in enumerate(lines) if text == "---"), None)
    if separator is None:
        raise ValueError("Notice metadata separator is missing")
    for text, header_anchor in lines[1:separator]:
        key, divider, value = text.partition(": ")
        if not divider or not value or key in metadata:
            raise ValueError("Missing or duplicate notice metadata")
        metadata[key] = value
        metadata_anchors[key] = header_anchor
    if set(metadata) != {"Kind", "Scheme", "Authority", "Reference", "Published", "Amends", "Effective", "Language"}:
        raise ValueError("Unsupported or incomplete notice metadata")
    kind = DocumentKind(metadata["Kind"])
    effective = date.fromisoformat(metadata["Effective"])
    published = date.fromisoformat(metadata["Published"])
    language = metadata["Language"]
    if language not in {"en", "hi"} or not re.fullmatch(_TOKEN, metadata["Scheme"]):
        raise ValueError("Unsupported notice language or scheme identifier")
    rules, changes = [], []
    for index, (text, anchor) in enumerate(lines[separator + 1:]):
        evidence = [anchor, metadata_anchors["Effective"]]
        revoke = re.fullmatch(rf"REVOKE ({_TOKEN})", text)
        if revoke and kind == DocumentKind.CORRIGENDUM:
            changes.append(AmendmentChange(change_id=f"{extraction.document_id}-change-{index}",
                                           operation="REVOKE", target_rule_id=revoke[1], effective_from=effective,
                                           amendment_evidence=evidence))
            continue
        match = re.fullmatch(rf"(RULE|ADD|REPLACE) ({_TOKEN})(?: WITH ({_TOKEN}))? \| scope=({_TOKEN}) \| (.+)", text)
        if not match:
            raise ValueError("Unsupported or ambiguous condition/operation; manual review required")
        operation, first_id, replacement_id, scope, clause = match.groups()
        if ((kind == DocumentKind.ORIGINAL and operation != "RULE")
                or (kind == DocumentKind.CORRIGENDUM and operation == "RULE")
                or ((operation == "REPLACE") != (replacement_id is not None))):
            raise ValueError("Operation does not match document kind or explicit target syntax")
        rule = _RULE.validate_python(dict(
            rule_id=replacement_id or first_id, scheme_id=metadata["Scheme"], scope_key=scope,
            effective_from=effective, evidence=evidence, **parse_closed_clause(clause, language),
        ))
        if kind == DocumentKind.ORIGINAL:
            rules.append(rule)
        else:
            changes.append(AmendmentChange(
                change_id=f"{extraction.document_id}-change-{index}", operation=operation,
                target_rule_id=first_id if operation == "REPLACE" else None,
                proposed_rule=rule, effective_from=effective, amendment_evidence=evidence,
            ))
    if not rules and not changes:
        raise ValueError("No supported rules or amendment changes")
    return ParsedNotice(kind, metadata["Scheme"], metadata["Authority"], metadata["Reference"],
                        published, metadata["Amends"], effective, language, tuple(rules), tuple(changes))
