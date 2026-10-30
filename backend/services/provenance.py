"""Pure checks of literal evidence, values, source configuration and chronology."""
from datetime import timedelta, timezone

from backend.legacy_schemas_v1 import (
    DocumentKind, GateCheck, GateCheckStatus as Check, GateRecommendation,
    ReviewState, SourceGateResult, SourceMatchState,
)
from backend.services.pdf_intake import parse_notice, verify_evidence


def notice_payload(notice):
    return dict(kind=notice.kind, scheme=notice.scheme_id, authority=notice.authority,
                reference=notice.reference, published=notice.published_on,
                amends=notice.amends_reference, effective=notice.effective_from,
                language=notice.language,
                rules=[r.model_dump(mode="json") for r in notice.rules],
                changes=[c.model_dump(mode="json") for c in notice.changes])


def source_gate(notice, extraction, document, config, *, configured_origin: bool,
                original=None, original_notice=None, checked_at):
    checks = []

    def check(name, passed, detail):
        checks.append(GateCheck(check_id=name, status=Check.UNKNOWN if passed is None else Check.PASS if passed else Check.FAIL, detail=detail))

    check("configured_origin", True if configured_origin else None,
          "Matched locally configured intake/hash; this is not cryptographic authenticity" if configured_origin
          else "Upload has no independently configured acquisition origin; a supplied URL is only metadata")
    check("scheme", notice.scheme_id == config.scheme_id, "Scheme must match the workspace configuration")
    check("authority", notice.authority == config.issuing_authority, "Issuing authority must match the configured scheme authority")
    check("document_kind", notice.kind == document.kind, "Declared upload kind must match the literal notice header")
    check("literal_values_and_scope", notice_payload(notice) == notice_payload(parse_notice(extraction)),
          "Candidate values, dates, IDs, operations and scope must exactly match parsed immutable source text")
    anchors = [a for r in notice.rules for a in r.evidence]
    anchors += [a for c in notice.changes for a in c.amendment_evidence]
    anchors += [a for c in notice.changes if c.proposed_rule for a in c.proposed_rule.evidence]
    check("evidence_identity", bool(anchors) and all(verify_evidence(a, extraction) for a in anchors)
          and document.sha256 == extraction.document_sha256, "Every literal anchor must match the immutable extraction and PDF hash")
    # The demo uses India's calendar date, not a UTC reinterpretation of deadlines.
    acquired_on = document.acquired_at.astimezone(timezone(timedelta(hours=5, minutes=30))).date()
    chronological = notice.published_on <= notice.effective_from and notice.published_on <= acquired_on
    if notice.kind == DocumentKind.ORIGINAL:
        check("reference_lineage", notice.amends_reference == "NONE", "An original must explicitly declare Amends: NONE")
    elif original is None or original_notice is None:
        check("reference_lineage", None, "No explicitly reviewed original is available in this workspace")
    else:
        check("reference_lineage", notice.amends_reference == original.reference_number
              and original_notice.scheme_id == notice.scheme_id
              and original_notice.authority == notice.authority
              and original.review_state == ReviewState.APPROVED,
              "Corrigendum must name the reviewed original reference from the same scheme and authority")
        chronological = (chronological and original_notice.published_on <= notice.published_on
                         and original_notice.effective_from <= notice.effective_from)
    check("chronology", chronological, "Publication, acquisition and effective dates must be explicit and chronological")
    failed = any(c.status == Check.FAIL for c in checks)
    unknown = any(c.status == Check.UNKNOWN for c in checks)
    return SourceGateResult(
        source_match=SourceMatchState.MISMATCH if failed else SourceMatchState.MATCHED_CONFIGURED_SOURCE if configured_origin else SourceMatchState.UNVERIFIED,
        recommendation=GateRecommendation.QUARANTINE if failed else GateRecommendation.MANUAL_REVIEW if unknown else GateRecommendation.ALLOW_REVIEW,
        checks=checks, checked_at=checked_at,
    )
