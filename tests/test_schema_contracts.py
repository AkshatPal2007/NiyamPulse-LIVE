"""Contract-only smoke tests. Not proof of actual crawler or app behavior."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.schemas import (
    AdminDashboardTotals, ApplicationStatus, Audience, CatalogResponse,
    DetectedNotice, DocumentTrust, ExamCatalogEntry, ExamCycle,
    ExamSubscription, InAppNotification, Language, NoticeType,
    OfficialSource, RecipientMatch, RecipientRelevance, ReviewStatus,
    SourceKind, SourceReadiness, Topic, UserProfileV2,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)


def test_catalog_and_sources_load_as_strict_schemas() -> None:
    catalog = json.loads((ROOT / "config" / "exam_catalog.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config" / "source_registry.json").read_text(encoding="utf-8"))
    exams = [ExamCatalogEntry.model_validate(v) for v in catalog["exams"]]
    cycles = [ExamCycle.model_validate(v) for v in catalog["cycles"]]
    parsed_sources = [OfficialSource.model_validate(v) for v in sources["sources"]]
    _ = CatalogResponse(exams=exams, cycles=cycles)
    exam_ids = {e.exam_id for e in exams}
    source_ids = {s.source_id for s in parsed_sources}
    assert len(exam_ids) == len(exams)
    assert all(c.exam_id in exam_ids for c in cycles)
    assert all(set(e.source_ids).issubset(source_ids) for e in exams)
    assert not any(s.enabled for s in parsed_sources), "untested sources must start disabled"
    assert {"jee-main", "neet-ug", "nda-na", "gate", "upsc-ese", "ssc-je"}.issubset(exam_ids)


def test_active_monitor_requires_tested_adapter() -> None:
    with pytest.raises(ValidationError):
        OfficialSource(source_id="source-1", organization="Exam Authority", listing_url="https://example.org/notices",
                       allowed_hosts=["example.org"], readiness=SourceReadiness.LISTING_VERIFIED_ADAPTER_UNTESTED,
                       enabled=True, adapter_name="adapter")
    with pytest.raises(ValidationError):
        OfficialSource(source_id="source-2", organization="Exam Authority", listing_url="https://evil.org/notices",
                       allowed_hosts=["example.org"])


def test_user_can_subscribe_without_sensitive_profile() -> None:
    profile = UserProfileV2(user_id="u1", preferred_language=Language.HI, created_at=NOW, updated_at=NOW)
    assert not profile.personalization_opt_in and profile.date_of_birth is None
    sub = ExamSubscription(subscription_id="sub1", user_id="u1", cycle_id="neet-ug:2027",
                           application_status=ApplicationStatus.INTERESTED, subscribed_at=NOW)
    assert sub.topics == [Topic.ALL]
    with pytest.raises(ValidationError):
        UserProfileV2(user_id="u1", date_of_birth="2008-01-01", created_at=NOW, updated_at=NOW)


def test_subscription_topic_all_exclusive() -> None:
    with pytest.raises(ValidationError):
        ExamSubscription(subscription_id="sub1", user_id="u1", cycle_id="gate:2027",
                         topics=[Topic.ALL, Topic.EXAM_SCHEDULE], subscribed_at=NOW)


def test_notice_mismatch_cannot_be_approved() -> None:
    with pytest.raises(ValidationError):
        DetectedNotice(notice_id="n1", cycle_id="gate:2027", source_kind=SourceKind.LOCAL_DEMO_FIXTURE,
                       title="Synthetic", document_sha256="a" * 64, first_seen_at=NOW,
                       trust=DocumentTrust.MISMATCH, review_status=ReviewStatus.APPROVED)
    with pytest.raises(ValidationError):
        DetectedNotice(notice_id="n1", cycle_id="gate:2027", source_kind=SourceKind.OFFICIAL_WEB_LISTING,
                       title="Source", document_sha256="a" * 64, first_seen_at=NOW)


def test_personal_impact_requires_a_real_status_change() -> None:
    with pytest.raises(ValidationError):
        RecipientMatch(match_id="m1", update_id="up1", user_id="u1", subscription_id="s1",
                       relevance=RecipientRelevance.PERSONAL_IMPACT, reason_codes=["rule_changed"])
    with pytest.raises(ValidationError):
        RecipientMatch(match_id="m1", update_id="up1", user_id="u1", subscription_id="s1",
                       relevance=RecipientRelevance.PERSONAL_IMPACT, reason_codes=["rule_changed"],
                       before="PASS", after="PASS")
    match = RecipientMatch(match_id="m1", update_id="up1", user_id="u1", subscription_id="s1",
                           relevance=RecipientRelevance.GENERAL_UPDATE, reason_codes=["subscribed_to_exam"])
    assert match.before is None


def test_read_requires_timestamps() -> None:
    from backend.schemas import EvidenceAnchor
    evidence = EvidenceAnchor(document_id="doc1", document_sha256="a" * 64, page_number=1,
                              literal_quote="Synthetic reference")
    with pytest.raises(ValidationError):
        InAppNotification(notification_id="x1", user_id="u1", match_id="m1", update_id="up1",
                          cycle_id="gate:2027", headline="Test", body="Test body",
                          language="hi", created_at=NOW, delivery="READ", evidence=[evidence])


def test_dashboard_counters_reject_negative() -> None:
    with pytest.raises(ValidationError):
        AdminDashboardTotals(monitored_sources=-1, active_exam_cycles=0, registered_users=0,
                             active_subscriptions=0, notices_detected=0, notices_pending_review=0,
                             approved_updates=0, matched_recipients=0, notifications_delivered=0,
                             notifications_failed=0)
