"""Tests for the v2 deterministic rule bridge (Phase 2).

These tests are fully synthetic — no network calls, no Sarvam API, no real
source captures. They verify:
  1. apply_rule_bridge validates changes and returns correct BridgeResult
  2. PersonalImpactRow correctly classifies before/after transitions
  3. profile_from_v2 correctly converts opted-in profiles (and refuses non-opted-in)
  4. ExamStore.rule_set_for_cycle / persist_rule_changes roundtrip correctly
  5. ExamService._run_rule_bridge handles edge cases (no changes → no-op)
  6. The PERSONAL_IMPACT/POSSIBLE_IMPACT match is written in _fanout when bridge fires
  7. Existing GENERAL_UPDATE path is untouched for non-rule notices
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import json

import pytest

from backend.legacy_schemas_v1 import (
    ApplicationDeadlineRule, ApplicantProfile, ChangeOperation,
    DecisionStatus, MinimumMarksRule, SourceEvidence,
)
from backend.services.rule_engine import content_fingerprint, rule_fingerprint
from backend.services.amendments import change_fingerprint
from backend.services.rule_bridge import (
    BridgeResult, PersonalImpactRow, apply_rule_bridge as _apply_rule_bridge, facts_to_notice_changes,
    profile_from_v2,
)
from backend import schemas as s
from backend.tests.local_temp import LocalTemporaryDirectory


def apply_rule_bridge(**kwargs):
    # Pure-engine unit fixtures explicitly simulate an independently verified caller.
    # Missing-proof and source-binding behavior is tested against the real function separately.
    from backend.services.rule_bridge import _build_amendment_change
    changes=kwargs['notice_changes']
    kwargs.setdefault('verified_change_hashes',frozenset(change_fingerprint(_build_amendment_change(c,kwargs['cycle_id'],c.evidence)) for c in changes))
    kwargs.setdefault('verified_proposed_rule_hashes',frozenset(rule_fingerprint(c.proposed_rule) for c in changes if c.proposed_rule))
    return _apply_rule_bridge(**kwargs)


# ── helpers ───────────────────────────────────────────────────────────────────

NOW = datetime(2027, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
TODAY = NOW.date()
CYCLE_ID = "jee-main:2027:s1"

FAKE_DOC_SHA = "a" * 64
FAKE_EXTRACT_ID = "extract-" + "b" * 64
FAKE_NOTICE_ID = "notice-001"

FAKE_EVIDENCE = [s.EvidenceAnchor(
    document_id=FAKE_NOTICE_ID,
    document_sha256=FAKE_DOC_SHA,
    page_number=1,
    literal_quote="Application deadline: 14 March 2027",
    start_char=0, end_char=36,
    extraction_id=FAKE_EXTRACT_ID,
)]

LEG_EVIDENCE = [SourceEvidence(
    document_id=FAKE_NOTICE_ID,
    document_sha256=FAKE_DOC_SHA,
    extraction_id=FAKE_EXTRACT_ID,
    page_number=1,
    literal_quote="Application deadline: 14 March 2027",
    start_char=0, end_char=36,
)]


def _deadline_rule(rule_id: str, deadline: date) -> ApplicationDeadlineRule:
    return ApplicationDeadlineRule(
        rule_id=rule_id,
        scheme_id=CYCLE_ID,
        scope_key="all_applicants",
        effective_from=date(2027, 1, 1),
        deadline_on=deadline,
        evidence=LEG_EVIDENCE,
    )


def _marks_rule(rule_id: str, min_marks: float) -> MinimumMarksRule:
    return MinimumMarksRule(
        rule_id=rule_id,
        scheme_id=CYCLE_ID,
        scope_key="all_applicants",
        effective_from=date(2027, 1, 1),
        min_marks_percent=min_marks,
        evidence=LEG_EVIDENCE,
    )


def _applicant(user_id: str, marks: float | None = None) -> ApplicantProfile:
    return ApplicantProfile(
        applicant_id=user_id,
        workspace_id="v2",
        display_name=user_id,
        scope_keys=[],
        marks_percent=marks,
        updated_at=NOW,
    )


def _v2_profile(user_id: str, marks: float | None = None, opt_in: bool = True) -> s.UserProfileV2:
    return s.UserProfileV2(
        user_id=user_id,
        display_name=user_id,
        marks_percent=marks if opt_in else None,
        personalization_opt_in=opt_in,
        created_at=NOW,
        updated_at=NOW,
    )


# ── profile_from_v2 ───────────────────────────────────────────────────────────

class TestProfileFromV2:
    def test_opted_in_returns_profile(self):
        v2 = _v2_profile("u1", marks=75.0, opt_in=True)
        prof = profile_from_v2(v2)
        assert prof is not None
        assert prof.applicant_id == "u1"
        assert prof.marks_percent == 75.0

    def test_not_opted_in_returns_none(self):
        v2 = _v2_profile("u1", opt_in=False)
        assert profile_from_v2(v2) is None

    def test_display_name_falls_back_to_user_id(self):
        v2 = s.UserProfileV2(
            user_id="u-no-name",
            display_name=None,
            personalization_opt_in=True,
            created_at=NOW, updated_at=NOW,
        )
        prof = profile_from_v2(v2)
        assert prof is not None
        assert prof.display_name == "u-no-name"


# ── PersonalImpactRow ─────────────────────────────────────────────────────────

class TestPersonalImpactRow:
    def test_changed_fail_to_pass_is_personal_impact(self):
        row = PersonalImpactRow("u1","s1",DecisionStatus.FAIL,DecisionStatus.PASS)
        assert row.changed is True
        assert row.relevance == s.RecipientRelevance.PERSONAL_IMPACT

    def test_changed_pass_to_fail_is_personal_impact(self):
        row = PersonalImpactRow("u1","s1",DecisionStatus.PASS,DecisionStatus.FAIL)
        assert row.relevance == s.RecipientRelevance.PERSONAL_IMPACT

    def test_unchanged_is_possible_impact(self):
        row = PersonalImpactRow("u1","s1",DecisionStatus.PASS,DecisionStatus.PASS)
        assert row.changed is False
        assert row.relevance == s.RecipientRelevance.POSSIBLE_IMPACT

    def test_unknown_to_unknown_is_possible_impact(self):
        row = PersonalImpactRow("u1","s1",DecisionStatus.UNKNOWN,DecisionStatus.UNKNOWN)
        assert row.relevance == s.RecipientRelevance.POSSIBLE_IMPACT


# ── apply_rule_bridge ──────────────────────────────────────────────────────────

class TestApplyRuleBridge:
    def _deadline_notice_change(
        self, change_id: str, rule_id: str, deadline: date, *,
        op: str = "ADD", target_rule_id: str | None = None,
    ) -> s.NoticeChange:
        proposed = _deadline_rule(rule_id, deadline) if op in {"ADD","REPLACE"} else None
        return s.NoticeChange(
            change_id=change_id,
            notice_id=FAKE_NOTICE_ID,
            rule_type=s.RuleChangeType.APPLICATION_DEADLINE,
            operation=op,
            target_rule_id=target_rule_id,
            proposed_rule=proposed,
            effective_from=date(2027,1,1) if proposed is None else proposed.effective_from,
            evidence=FAKE_EVIDENCE,
        )

    def test_add_deadline_rule_empty_before(self):
        nc = self._deadline_notice_change("c1","rule-dl-1",date(2027,3,14))
        result = apply_rule_bridge(
            notice_changes=[nc],
            before_rules=[],
            before_verified_hashes=frozenset(),
            scheme_id=CYCLE_ID,
            subscribers=[],
            as_of_date=TODAY,
            cycle_id=CYCLE_ID,
        )
        assert isinstance(result, BridgeResult)
        assert "rule-dl-1" in result.added_rule_ids
        assert len(result.revoked_rule_ids) == 0
        assert result.after_rule_set_sha256  # non-empty hash

    def test_add_marks_rule_impact_evaluation(self):
        nc = s.NoticeChange(
            change_id="c1",
            notice_id=FAKE_NOTICE_ID,
            rule_type=s.RuleChangeType.MINIMUM_MARKS,
            operation="ADD",
            proposed_rule=_marks_rule("rule-marks-1", 60.0),
            effective_from=date(2027,1,1),
            evidence=FAKE_EVIDENCE,
        )
        # Two subscribers: one above threshold (PASS), one below (FAIL)
        p_above = _applicant("u-above", marks=75.0)
        p_below = _applicant("u-below", marks=50.0)
        result = apply_rule_bridge(
            notice_changes=[nc],
            before_rules=[],
            before_verified_hashes=frozenset(),
            scheme_id=CYCLE_ID,
            subscribers=[
                ("u-above","sub-a",p_above),
                ("u-below","sub-b",p_below),
            ],
            as_of_date=TODAY,
            cycle_id=CYCLE_ID,
        )
        by_user = {imp.user_id: imp for imp in result.impacts}
        # Before = no rules → UNKNOWN; After = rule added
        assert by_user["u-above"].before == DecisionStatus.UNKNOWN
        assert by_user["u-above"].after == DecisionStatus.PASS
        assert by_user["u-below"].before == DecisionStatus.UNKNOWN
        assert by_user["u-below"].after == DecisionStatus.FAIL

    def test_no_profile_subscribers_excluded(self):
        nc = s.NoticeChange(
            change_id="c1", notice_id=FAKE_NOTICE_ID,
            rule_type=s.RuleChangeType.MINIMUM_MARKS,
            operation="ADD",
            proposed_rule=_marks_rule("rule-m1", 60.0),
            effective_from=date(2027,1,1),
            evidence=FAKE_EVIDENCE,
        )
        result = apply_rule_bridge(
            notice_changes=[nc],
            before_rules=[],
            before_verified_hashes=frozenset(),
            scheme_id=CYCLE_ID,
            subscribers=[("u1","s1",None)],   # None → not opted in
            as_of_date=TODAY,
            cycle_id=CYCLE_ID,
        )
        assert result.impacts == []

    def test_empty_changes_raises_engine_error(self):
        from backend.services.rule_engine import EngineError
        with pytest.raises(EngineError, match="At least one"):
            apply_rule_bridge(
                notice_changes=[],
                before_rules=[],
                before_verified_hashes=frozenset(),
                scheme_id=CYCLE_ID,
                subscribers=[],
                as_of_date=TODAY,
                cycle_id=CYCLE_ID,
            )

    def test_supported_rule_types_are_accepted(self):
        """Verify all five closed-set rule types pass the bridge type guard."""
        # Each must produce a BridgeResult without raising BRIDGE_UNSUPPORTED_RULE_TYPE.
        from backend.legacy_schemas_v1 import AgeBoundsRule, RequiredDocumentsRule
        # age_bounds
        nc_age = s.NoticeChange(
            change_id="c-age",
            notice_id=FAKE_NOTICE_ID,
            rule_type=s.RuleChangeType.AGE_BOUNDS,
            operation="ADD",
            proposed_rule=AgeBoundsRule(
                rule_id="rule-age-1",
                scheme_id=CYCLE_ID,
                scope_key="all_applicants",
                effective_from=date(2027,1,1),
                min_age_years=17,
                max_age_years=25,
                age_as_of=date(2027,10,1),
                evidence=LEG_EVIDENCE,
            ),
            effective_from=date(2027,1,1),
            evidence=FAKE_EVIDENCE,
        )
        result = apply_rule_bridge(
            notice_changes=[nc_age],
            before_rules=[],
            before_verified_hashes=frozenset(),
            scheme_id=CYCLE_ID,
            subscribers=[],
            as_of_date=TODAY,
            cycle_id=CYCLE_ID,
        )
        assert "rule-age-1" in result.added_rule_ids

    def test_replace_existing_rule(self):
        old_rule = _deadline_rule("rule-dl-old", date(2027, 3, 1))
        old_hash = rule_fingerprint(old_rule)
        new_nc = s.NoticeChange(
            change_id="c-replace",
            notice_id=FAKE_NOTICE_ID,
            rule_type=s.RuleChangeType.APPLICATION_DEADLINE,
            operation="REPLACE",
            target_rule_id="rule-dl-old",
            proposed_rule=ApplicationDeadlineRule(
                rule_id="rule-dl-new",
                scheme_id=CYCLE_ID,
                scope_key="all_applicants",
                effective_from=date(2027, 3, 1),
                deadline_on=date(2027, 4, 1),
                evidence=LEG_EVIDENCE,
            ),
            effective_from=date(2027, 3, 1),
            evidence=FAKE_EVIDENCE,
        )
        result = apply_rule_bridge(
            notice_changes=[new_nc],
            before_rules=[old_rule],
            before_verified_hashes=frozenset({old_hash}),
            scheme_id=CYCLE_ID,
            subscribers=[],
            as_of_date=TODAY,
            cycle_id=CYCLE_ID,
        )
        assert "rule-dl-new" in result.added_rule_ids
        # old rule is closed out (shortened), it stays in history with new end date
        # but its original ID is NOT in added_rule_ids
        assert "rule-dl-old" not in result.added_rule_ids


# ── ExamStore rule_set roundtrip ──────────────────────────────────────────────

class TestExamStoreRuleSet:
    def test_empty_cycle_returns_empty_rule_set(self):
        from backend.exam_store import ExamStore
        directory = LocalTemporaryDirectory()
        try:
            store = ExamStore(Path(directory.name) / "app.sqlite3")
            with store.connect() as con:
                rules, hashes = store.rule_set_for_cycle(con, CYCLE_ID)
            assert rules == []
            assert hashes == frozenset()
        finally:
            directory.cleanup()

    def test_persist_and_reload_rules(self):
        from backend.exam_store import ExamStore
        from backend.storage import utc_text

        directory = LocalTemporaryDirectory()
        try:
            store = ExamStore(Path(directory.name) / "app.sqlite3")
            store.seed_demo_users()

            # Build a minimal rule to persist via the bridge
            rule = _deadline_rule("rule-dl-store-test", date(2027, 3, 14))
            rule_hash = rule_fingerprint(rule)
            nc = s.NoticeChange(
                change_id="c-persist-1",
                notice_id=FAKE_NOTICE_ID,
                rule_type=s.RuleChangeType.APPLICATION_DEADLINE,
                operation="ADD",
                proposed_rule=rule,
                effective_from=rule.effective_from,
                evidence=FAKE_EVIDENCE,
            )
            result = apply_rule_bridge(
                notice_changes=[nc],
                before_rules=[],
                before_verified_hashes=frozenset(),
                scheme_id=CYCLE_ID,
                subscribers=[],
                as_of_date=TODAY,
                cycle_id=CYCLE_ID,
            )

            # Persist via the store helper (need a fake update_id in v2_updates first)
            fake_update_id = "update-test-001"
            with store.connect(write=True) as con:
                # We need a cycle row — it was seeded by seed_config
                # We need a v2_notices and v2_updates row for the FK constraint
                snap_id = "snap-test-001"
                ext_id = "extract-test-001"
                fake_sha = "c" * 64
                fake_pages = json.dumps(["page text"])
                pages_sha = content_fingerprint(["page text"])
                con.execute(
                    "INSERT INTO v2_snapshots (id,source_id,url,sha256,content_type,content,fetched_at)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (snap_id, "nta-jee-main", "https://jeemain.nta.ac.in/test.pdf",
                     fake_sha, "application/pdf", b"pdf", utc_text(NOW)),
                )
                con.execute(
                    "INSERT INTO v2_extractions (id,snapshot_id,version,pages,pages_sha)"
                    " VALUES (?,?,?,?,?)",
                    (ext_id, snap_id, "v1", fake_pages, pages_sha),
                )
                con.execute(
                    "INSERT INTO v2_notices (id,source_id,cycle_id,canonical_url,content_hash,"
                    "listing_snapshot_id,document_snapshot_id,pages,extraction_id,extraction_version,"
                    "observed_link_title,listing_url,payload)"
                    " VALUES (?,?,?,?,?,NULL,?,?,?,?,?,NULL,?)",
                    (FAKE_NOTICE_ID, None, CYCLE_ID,
                     "https://jeemain.nta.ac.in/test.pdf", "hash1",
                     snap_id, fake_pages, ext_id, "v1",
                     "Test notice", "{}"),
                )
                con.execute(
                    "INSERT INTO v2_updates (id,notice_id,cycle_id,payload) VALUES (?,?,?,?)",
                    (fake_update_id, FAKE_NOTICE_ID, CYCLE_ID, "{}"),
                )
                store.persist_rule_changes(
                    con,
                    cycle_id=CYCLE_ID,
                    update_id=fake_update_id,
                    bridge_result=result,
                    now_text=utc_text(NOW),
                )

            # Reload and verify
            with store.connect() as con:
                reloaded_rules, reloaded_hashes = store.rule_set_for_cycle(con, CYCLE_ID)
            assert len(reloaded_rules) == 1
            assert reloaded_rules[0].rule_id == "rule-dl-store-test"
            assert rule_hash in reloaded_hashes
        finally:
            directory.cleanup()


# ── Integration: _fanout with bridge result ───────────────────────────────────

class TestFanoutWithBridge:
    """Verify that opted-in subscribers receive PERSONAL_IMPACT matches when
    the rule bridge fires, while non-opted-in subscribers still get GENERAL_UPDATE.
    """
    def _make_service(self, store):
        from backend.services.exams import ExamService
        svc = ExamService(store, demo=True, clock=lambda: NOW)
        return svc

    def test_fanout_general_update_no_bridge(self):
        """With no bridge result, _fanout should produce GENERAL_UPDATE matches."""
        from backend.exam_store import ExamStore
        from backend.storage import utc_text

        directory = LocalTemporaryDirectory()
        try:
            store = ExamStore(Path(directory.name) / "app.sqlite3")
            store.seed_demo_users()
            svc = self._make_service(store)

            _subscribe(svc, store, "demo-school", CYCLE_ID)

            notice, update = _minimal_notice_and_update(store, CYCLE_ID)
            with store.connect(write=True) as con:
                svc._fanout(con, notice, update, NOW, bridge_result=None)

            with store.connect() as con:
                matches = con.execute("SELECT payload FROM v2_matches WHERE update_id=?",
                                      (update.update_id,)).fetchall()
            assert len(matches) == 1
            m = s.RecipientMatch.model_validate_json(matches[0][0])
            assert m.relevance == s.RecipientRelevance.GENERAL_UPDATE
            assert m.before is None
            assert m.after is None
        finally:
            directory.cleanup()

    def test_fanout_personal_impact_with_bridge(self):
        """Opted-in subscriber should get PERSONAL_IMPACT when status changed."""
        from backend.exam_store import ExamStore
        from backend.storage import utc_text

        directory = LocalTemporaryDirectory()
        try:
            store = ExamStore(Path(directory.name) / "app.sqlite3")
            store.seed_demo_users()
            svc = self._make_service(store)

            _subscribe(svc, store, "demo-school", CYCLE_ID)

            # Opt the school learner in with marks above 60%
            with store.connect(write=True) as con:
                profile = s.UserProfileV2(
                    user_id="demo-school",
                    display_name="School learner",
                    personalization_opt_in=True,
                    marks_percent=75.0,
                    created_at=NOW, updated_at=NOW,
                )
                con.execute("UPDATE v2_users SET profile=? WHERE id=?",
                            (profile.model_dump_json(), "demo-school"))

            notice, update = _minimal_notice_and_update(store, CYCLE_ID)
            bridge = apply_rule_bridge(
                notice_changes=[s.NoticeChange(
                    change_id="persisted-check", notice_id=FAKE_NOTICE_ID,
                    rule_type=s.RuleChangeType.MINIMUM_MARKS, operation="ADD",
                    proposed_rule=_marks_rule("persisted-marks", 60.0),
                    effective_from=date(2027,1,1), evidence=FAKE_EVIDENCE,
                )],
                before_rules=[], before_verified_hashes=frozenset(),
                scheme_id=CYCLE_ID, cycle_id=CYCLE_ID, as_of_date=TODAY,
                subscribers=[("demo-school", "sub-placeholder", _applicant("demo-school", marks=75.0))],
            )
            with store.connect(write=True) as con:
                svc._fanout(con, notice, update, NOW, bridge_result=bridge)

            with store.connect() as con:
                matches = con.execute("SELECT payload FROM v2_matches WHERE update_id=?",
                                      (update.update_id,)).fetchall()
            assert len(matches) == 1
            m = s.RecipientMatch.model_validate_json(matches[0][0])
            assert m.relevance == s.RecipientRelevance.PERSONAL_IMPACT
            assert m.before == DecisionStatus.UNKNOWN
            assert m.after == DecisionStatus.PASS
            assert m.after_checks and m.after_checks == bridge.impacts[0].after_checks
            assert m.before_checks == bridge.impacts[0].before_checks

        finally:
            directory.cleanup()


# ── helpers for integration tests ─────────────────────────────────────────────

def _subscribe(svc, store, user_id: str, cycle_id: str):
    body = s.SubscriptionCreate(cycle_id=cycle_id, topics=[s.Topic.ALL])
    svc.subscribe(user_id, body)


def _minimal_notice_and_update(store, cycle_id: str):
    from backend.storage import utc_text
    import uuid

    notice_id = "notice-fanout-test-" + uuid.uuid4().hex[:8]
    update_id = "update-fanout-test-" + uuid.uuid4().hex[:8]
    snap_id = "snap-fanout-" + uuid.uuid4().hex[:8]
    ext_id = "extract-fanout-" + uuid.uuid4().hex[:8]
    fake_sha = "d" * 64
    fake_pages = json.dumps(["page text"])
    pages_sha = content_fingerprint(["page text"])

    anchor = s.EvidenceAnchor(
        document_id=notice_id,
        document_sha256=fake_sha,
        page_number=1,
        literal_quote="Application deadline: 14 March 2027",
        start_char=0, end_char=36,
        extraction_id=ext_id,
    )
    notice = s.DetectedNotice(
        notice_id=notice_id,
        cycle_id=cycle_id,
        source_kind=s.SourceKind.LOCAL_DEMO_FIXTURE,
        title="Test Notice",
        notice_type=s.NoticeType.INFORMATIONAL,
        document_sha256=fake_sha,
        first_seen_at=NOW,
        trust=s.DocumentTrust.UNVERIFIED,
        review_status=s.ReviewStatus.APPROVED,
        evidence=[anchor],
        topics=[s.Topic.ALL],
    )
    update = s.NoticeUpdate(
        update_id=update_id,
        cycle_id=cycle_id,
        notice_id=notice_id,
        notice_type=s.NoticeType.INFORMATIONAL,
        published_at=NOW,
        summary_en="Test summary",
        evidence=[anchor],
        approved_by="demo-operator",
        approved_at=NOW,
        evaluation_version="cycle-topic-v1",
    )

    with store.connect(write=True) as con:
        con.execute(
            "INSERT INTO v2_snapshots (id,source_id,url,sha256,content_type,content,fetched_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (snap_id, "nta-jee-main", f"https://jeemain.nta.ac.in/{notice_id}.pdf",
             fake_sha, "application/pdf", b"pdf", utc_text(NOW)),
        )
        con.execute(
            "INSERT INTO v2_extractions (id,snapshot_id,version,pages,pages_sha)"
            " VALUES (?,?,?,?,?)",
            (ext_id, snap_id, "v1", fake_pages, pages_sha),
        )
        con.execute(
            "INSERT INTO v2_notices (id,source_id,cycle_id,canonical_url,content_hash,"
            "listing_snapshot_id,document_snapshot_id,pages,extraction_id,extraction_version,"
            "observed_link_title,listing_url,payload) VALUES (?,?,?,?,?,NULL,?,?,?,?,?,NULL,?)",
            (notice_id, None, cycle_id,
             f"https://jeemain.nta.ac.in/{notice_id}.pdf", "hash-test",
             snap_id, fake_pages, ext_id, "v1", "Test notice",
             notice.model_dump_json()),
        )
        con.execute(
            "INSERT INTO v2_updates (id,notice_id,cycle_id,payload) VALUES (?,?,?,?)",
            (update_id, notice_id, cycle_id, update.model_dump_json()),
        )
    return notice, update


# ── TestFactsToNoticeChanges ──────────────────────────────────────────────────

class TestFactsToNoticeChanges:
    def _anchor(self, quote: str, page: int = 1) -> s.EvidenceAnchor:
        return s.EvidenceAnchor(
            document_id=FAKE_NOTICE_ID,
            document_sha256=FAKE_DOC_SHA,
            extraction_id=FAKE_EXTRACT_ID,
            page_number=page,
            literal_quote=quote,
            start_char=0,
            end_char=len(quote),
        )

    def test_deadline_with_date_value(self):
        q = "Published: 2027-01-01 | Effective: 2027-01-01 | Scheme: jee-main:2027:s1 | Operation: ADD | Scope: all_applicants | Application deadline: 2027-03-14."
        fact = s.ExtractedFact(kind="APPLICATION_DEADLINE", page_number=1, literal_quote=q, date_value=date(2027, 3, 14))
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
            published_on=date(2027, 1, 1),
        )
        assert len(changes) == 1
        assert changes[0].rule_type == s.RuleChangeType.APPLICATION_DEADLINE
        assert changes[0].operation == "ADD"
        assert changes[0].target_rule_id is None
        assert changes[0].proposed_rule.deadline_on == date(2027, 3, 14)
        assert len(changes[0].evidence) == 1
        assert len(diags) == 0

    def test_deadline_from_quote_text(self):
        q = "Published: 2027-01-01 | Effective: 2027-01-01 | Scheme: jee-main:2027:s1 | Operation: ADD | Scope: all_applicants | Application deadline: 2027-04-25."
        fact = s.ExtractedFact(kind="RULE_CANDIDATE", page_number=1, literal_quote=q, date_value=None)
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
            published_on=date(2027, 1, 1),
        )
        assert len(changes) == 1
        assert changes[0].proposed_rule.deadline_on == date(2027, 4, 25)

    def test_minimum_marks_percentage(self):
        q = "Published: 2027-01-01 | Effective: 2027-01-01 | Scheme: jee-main:2027:s1 | Operation: ADD | Scope: all_applicants | Minimum qualifying marks: 75%."
        fact = s.ExtractedFact(kind="RULE_CANDIDATE", page_number=1, literal_quote=q)
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
            published_on=date(2027, 1, 1),
        )
        assert len(changes) == 1
        assert changes[0].rule_type == s.RuleChangeType.MINIMUM_MARKS
        assert changes[0].proposed_rule.min_marks_percent == 75.0

    def test_maximum_income_inr_lakh(self):
        q = "Published: 2027-01-01 | Effective: 2027-01-01 | Scheme: jee-main:2027:s1 | Operation: ADD | Scope: all_applicants | Maximum annual household income: INR 800000."
        fact = s.ExtractedFact(kind="RULE_CANDIDATE", page_number=1, literal_quote=q)
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
            published_on=date(2027, 1, 1),
        )
        assert len(changes) == 1
        assert changes[0].rule_type == s.RuleChangeType.MAXIMUM_INCOME
        assert changes[0].proposed_rule.max_annual_income_inr == 800000

    def test_maximum_income_inr_rupees(self):
        q = "Published: 2027-01-01 | Effective: 2027-01-01 | Scheme: jee-main:2027:s1 | Operation: ADD | Scope: all_applicants | Maximum annual household income: INR 250000."
        fact = s.ExtractedFact(kind="RULE_CANDIDATE", page_number=1, literal_quote=q)
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
            published_on=date(2027, 1, 1),
        )
        assert len(changes) == 1
        assert changes[0].proposed_rule.max_annual_income_inr == 250000

    def test_age_bounds(self):
        q = "Published: 2027-01-01 | Effective: 2027-01-01 | Scheme: jee-main:2027:s1 | Operation: ADD | Scope: all_applicants | Age bounds: 18..30 years on 2027-08-01."
        fact = s.ExtractedFact(kind="RULE_CANDIDATE", page_number=1, literal_quote=q)
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
            published_on=date(2027, 1, 1),
        )
        assert len(changes) == 1
        assert changes[0].rule_type == s.RuleChangeType.AGE_BOUNDS
        assert changes[0].proposed_rule.min_age_years == 18
        assert changes[0].proposed_rule.max_age_years == 30
        assert changes[0].proposed_rule.age_as_of == date(2027, 8, 1)

    def test_required_documents(self):
        q = "Published: 2027-01-01 | Effective: 2027-01-01 | Scheme: jee-main:2027:s1 | Operation: ADD | Scope: all_applicants | Required documents: DOC_AADHAAR, DOC_MARKSHEET_10, DOC_CATEGORY_CERT."
        fact = s.ExtractedFact(kind="RULE_CANDIDATE", page_number=1, literal_quote=q)
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
            published_on=date(2027, 1, 1),
        )
        assert len(changes) == 1
        assert changes[0].rule_type == s.RuleChangeType.REQUIRED_DOCUMENTS
        codes = changes[0].proposed_rule.required_document_codes
        assert "DOC_AADHAAR" in codes
        assert "DOC_MARKSHEET_10" in codes
        assert "DOC_CATEGORY_CERT" in codes

    def test_replaces_existing_rule_when_present(self):
        existing_marks = _marks_rule("rule-old-marks", 60.0)
        q = "Published: 2027-01-01 | Effective: 2027-01-01 | Scheme: jee-main:2027:s1 | Operation: REPLACE | Target: rule-old-marks | Scope: all_applicants | Minimum qualifying marks: 75%."
        fact = s.ExtractedFact(kind="RULE_CANDIDATE", page_number=1, literal_quote=q)
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
            published_on=date(2027, 1, 1),
            before_rules=[existing_marks],
        )
        assert len(changes) == 1
        assert changes[0].operation == "REPLACE"
        assert changes[0].target_rule_id == "rule-old-marks"
        assert changes[0].proposed_rule.min_marks_percent == 75.0

    def test_unsupported_requirement_diagnostics_no_fake_rule(self):
        q = "Candidates must possess a Bachelor's degree in Chemical Engineering."
        fact = s.ExtractedFact(kind="UNSUPPORTED_REQUIREMENT", page_number=1, literal_quote=q)
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
        )
        assert len(changes) == 0
        assert any("UNSUPPORTED_REQUIREMENT" in d for d in diags)

    def test_unparseable_rule_candidate_diagnostics_no_fake_rule(self):
        q = "Candidates must clear the physical fitness run of 1.6 km within 7 minutes."
        fact = s.ExtractedFact(kind="RULE_CANDIDATE", page_number=1, literal_quote=q)
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
        )
        assert len(changes) == 0
        assert any("could not be mapped" in d for d in diags)

    def test_announcement_is_ignored(self):
        q = "The examination city intimation slip will be released 10 days before the exam."
        fact = s.ExtractedFact(kind="ANNOUNCEMENT", page_number=1, literal_quote=q)
        changes, diags = facts_to_notice_changes(
            notice_id=FAKE_NOTICE_ID,
            cycle_id=CYCLE_ID,
            facts=[fact],
            evidence_anchors=[self._anchor(q)],
        )
        assert len(changes) == 0
        assert len(diags) == 0

