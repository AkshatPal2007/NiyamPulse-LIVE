"""Transactional intake/review/apply orchestration over the pure Phase 1 engine."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from backend.legacy_schemas_v1 import (
    AmendmentChange, AmendmentRecord, ApplyAmendmentResponse, DocumentKind, ExtractionState,
    GateCheck, GateCheckStatus, GateRecommendation, ImpactEvent, ImportDocumentResponse,
    IntakeState, PreviewAmendmentResponse, ReviewState, SourceDocument, SourceMatchState,
    TimelineSnapshot,
)
from backend.services.amendments import change_fingerprint, plan_amendment
from backend.services.impact import preview_impact
from backend.services.pdf_intake import EXTRACTOR_VERSION, MAX_PDF_BYTES, extract_pdf, parse_notice
from backend.services.provenance import source_gate
from backend.services.rule_engine import EngineError, effective_rules, evaluate_applicant, rule_fingerprint, rule_set_fingerprint
from backend.storage import ServiceError, json_models, utc_text


class WorkspaceService:
    def __init__(self, store, clock=None):
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def import_pdf(self, workspace_id, data, *, filename, kind, source_url=None, origin_path=None):
        if len(data) > MAX_PDF_BYTES:
            raise ServiceError(413, "PDF_TOO_LARGE", "PDF exceeds the 10 MiB intake limit")
        if not data.startswith(b"%PDF-"):
            raise ServiceError(415, "PDF_REQUIRED", "A PDF file is required")
        digest = hashlib.sha256(data).hexdigest()
        with self.store.connect(write=True) as con:
            config = self.store.config(workspace_id, con)
            duplicate = con.execute("SELECT id FROM documents WHERE workspace=? AND sha=?", (workspace_id, digest)).fetchone()
            if duplicate:
                doc = self.store.document(workspace_id, duplicate[0], con)
                amendment = con.execute("SELECT id FROM amendments WHERE document_id=?", (doc.document_id,)).fetchone()
                # Never silently upgrade trust or change a prior acquisition's kind.
                return ImportDocumentResponse(document=doc, amendment_id=amendment[0] if amendment else None)
            doc = SourceDocument(
                document_id=f"doc-{uuid.uuid4().hex}", workspace_id=workspace_id,
                filename=Path(filename or "notice.pdf").name, sha256=digest, kind=kind,
                acquired_at=self.clock(), source_url=source_url, synthetic=config.synthetic,
                acquisition_channel="LOCAL_WATCH" if origin_path else "UPLOAD",
            )
            con.execute("INSERT OR IGNORE INTO pdf_sources VALUES (?,?)", (digest, data))
            con.execute("INSERT INTO documents VALUES (?,?,?,?,?)", (doc.document_id, workspace_id, digest, doc.model_dump_json(), str(Path(origin_path).resolve()) if origin_path else None))
            con.execute("INSERT INTO document_states VALUES (?,?)", (doc.document_id, doc.model_dump_json()))
            amendment_id = None
            if doc.kind == DocumentKind.CORRIGENDUM:
                amendment_id = f"amend-{uuid.uuid4().hex}"
                amendment = AmendmentRecord(amendment_id=amendment_id, workspace_id=workspace_id,
                                             original_document_id="unresolved-original", corrigendum_document_id=doc.document_id)
                con.execute("INSERT INTO amendments VALUES (?,?,?,?)", (amendment_id, workspace_id, doc.document_id, amendment.model_dump_json()))
            return ImportDocumentResponse(document=doc, amendment_id=amendment_id)

    def _save_document(self, con, document):
        con.execute("UPDATE document_states SET payload=? WHERE id=?", (document.model_dump_json(), document.document_id))

    def _save_amendment(self, con, amendment):
        con.execute("UPDATE amendments SET payload=? WHERE id=?", (amendment.model_dump_json(), amendment.amendment_id))

    def _configured_origin(self, con, document, config):
        row = con.execute("SELECT acquisition,origin_path FROM documents WHERE id=?", (document.document_id,)).fetchone()
        acquisition = SourceDocument.model_validate_json(row["acquisition"])
        if acquisition.sha256 in config.configured_hashes:
            return True
        return bool(config.intake_directory and acquisition.acquisition_channel == "LOCAL_WATCH" and row["origin_path"]
                    and Path(row["origin_path"]).resolve().parent == Path(config.intake_directory).resolve())

    def _assess(self, con, workspace_id, document_id, now):
        row = self.store.row(con, workspace_id)
        config = self.store.config(workspace_id, con)
        doc = self.store.document(workspace_id, document_id, con)
        extraction = self.store.extraction(workspace_id, document_id, con)
        notice = parse_notice(extraction)
        doc.issuing_authority, doc.reference_number = notice.authority, notice.reference
        doc.published_on, doc.language = notice.published_on, notice.language
        original, original_notice = None, None
        if row["baseline_document_id"]:
            original = self.store.document(workspace_id, row["baseline_document_id"], con)
            original_notice = parse_notice(self.store.extraction(workspace_id, original.document_id, con))
        gate = source_gate(notice, extraction, doc, config,
                           configured_origin=self._configured_origin(con, doc, config),
                           original=original, original_notice=original_notice, checked_at=now)
        trust = set(json.loads(row["trust"]))
        changes = list(notice.changes) if doc.kind == DocumentKind.CORRIGENDUM else [
            AmendmentChange(change_id=f"baseline-{i}", operation="ADD", proposed_rule=r,
                            effective_from=r.effective_from, amendment_evidence=r.evidence)
            for i, r in enumerate(notice.rules)
        ]
        plan = None
        if gate.recommendation == GateRecommendation.ALLOW_REVIEW:
            proposals = [c.proposed_rule for c in changes if c.proposed_rule]
            try:
                if doc.kind == DocumentKind.ORIGINAL and row["baseline_document_id"]:
                    raise EngineError("BASELINE_EXISTS", "Only an empty workspace can accept an original baseline")
                plan = plan_amendment(self.store.history(row), changes, scheme_id=config.scheme_id,
                                      verified_rule_hashes=trust | {rule_fingerprint(r) for r in proposals},
                                      verified_change_hashes={change_fingerprint(c) for c in changes})
            except EngineError as error:
                gate = gate.model_copy(update={
                    "recommendation": GateRecommendation.QUARANTINE,
                    "checks": gate.checks + [GateCheck(check_id="rule_precedence", status=GateCheckStatus.FAIL, detail=f"{error.code}: {error}")],
                })
        doc.source_gate = gate
        doc.intake_state = (IntakeState.READY_TO_APPLY if gate.recommendation == GateRecommendation.ALLOW_REVIEW
                            else IntakeState.QUARANTINED if gate.recommendation == GateRecommendation.QUARANTINE else IntakeState.NEEDS_REVIEW)
        amendment = None
        if doc.kind == DocumentKind.CORRIGENDUM:
            found = con.execute("SELECT id FROM amendments WHERE document_id=?", (doc.document_id,)).fetchone()
            amendment = self.store.amendment(workspace_id, found[0], con)
            amendment.original_document_id = original.document_id if original else "unresolved-original"
            amendment.published_on, amendment.changes, amendment.source_gate = notice.published_on, list(notice.changes), gate
            amendment.intake_state = doc.intake_state
        return doc, amendment, plan

    def process(self, workspace_id, document_id):
        with self.store.connect(write=True) as con:
            doc = self.store.document(workspace_id, document_id, con)
            if doc.extraction_state != ExtractionState.PENDING:
                return
            doc.intake_state = IntakeState.EXTRACTING
            self._save_document(con, doc)
            try:
                data = self.store.pdf(workspace_id, document_id, con)
                cached = con.execute("SELECT id FROM extractions WHERE sha=? AND version=?", (doc.sha256, EXTRACTOR_VERSION)).fetchone()
                if cached:
                    doc.extraction_id, doc.processing_mode = cached[0], "CACHED_EXTRACTION"
                else:
                    extraction = extract_pdf(data, "content")
                    payload = extraction.model_dump_json()
                    con.execute("INSERT INTO extractions VALUES (?,?,?,?,?)", (extraction.extraction_id, doc.sha256, EXTRACTOR_VERSION, payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()))
                    doc.extraction_id = extraction.extraction_id
                doc.extraction_state = ExtractionState.COMPLETE
                self._save_document(con, doc)
                doc, amendment, _ = self._assess(con, workspace_id, document_id, self.clock())
                if amendment:
                    self._save_amendment(con, amendment)
            except (ValueError, ServiceError) as error:
                # Parser/validation failure cannot activate even a subset of rules.
                doc = self.store.document(workspace_id, document_id, con)
                doc.intake_state = IntakeState.NEEDS_REVIEW if doc.extraction_state == ExtractionState.COMPLETE else IntakeState.FAILED
                if doc.extraction_state != ExtractionState.COMPLETE:
                    doc.extraction_state = ExtractionState.FAILED
                doc.diagnostics = [str(error)]
                found = con.execute("SELECT id FROM amendments WHERE document_id=?", (document_id,)).fetchone()
                if found:
                    amendment = self.store.amendment(workspace_id, found[0], con)
                    amendment.intake_state = doc.intake_state
                    self._save_amendment(con, amendment)
            self._save_document(con, doc)

    def resume_pending(self):
        with self.store.connect() as con:
            pending = [(r["workspace"], r["id"]) for r in con.execute("SELECT d.workspace,d.id,s.payload FROM documents d JOIN document_states s ON s.id=d.id")
                       if SourceDocument.model_validate_json(r["payload"]).extraction_state == ExtractionState.PENDING]
        for workspace_id, document_id in pending:
            self.process(workspace_id, document_id)

    def _impact(self, row, config, plan, amendment_id, now):
        return preview_impact(config.profiles, self.store.history(row), plan.rules,
                              event_id=f"preview-{amendment_id}-{row['revision']}", workspace_id=config.workspace_id,
                              amendment_id=amendment_id, scheme_id=config.scheme_id, as_of_date=config.evaluation_date,
                              occurred_at=now, before_verified_rule_hashes=json.loads(row["trust"]),
                              after_verified_rule_hashes=plan.verified_rule_hashes)

    def preview(self, workspace_id, amendment_id):
        with self.store.connect(write=True) as con:
            row = self.store.row(con, workspace_id)
            config = self.store.config(workspace_id, con)
            existing = self.store.amendment(workspace_id, amendment_id, con)
            if existing.intake_state == IntakeState.APPLIED:
                return PreviewAmendmentResponse(amendment=existing, can_apply=False, blockers=["Amendment already applied"])
            try:
                doc, amendment, plan = self._assess(con, workspace_id, existing.corrigendum_document_id, self.clock())
            except (ValueError, ServiceError) as error:
                return PreviewAmendmentResponse(amendment=existing, can_apply=False, blockers=[str(error)])
            self._save_document(con, doc)
            self._save_amendment(con, amendment)
            blockers = [c.detail for c in amendment.source_gate.checks if c.status != GateCheckStatus.PASS]
            return PreviewAmendmentResponse(amendment=amendment, impact=self._impact(row, config, plan, amendment_id, self.clock()) if plan else None,
                                             can_apply=plan is not None, blockers=blockers)

    def _check_revision(self, row, expected):
        if row["revision"] != expected:
            raise ServiceError(409, "STALE_REVISION", "Workspace changed; refresh and review the current preview")

    def _commit(self, con, row, config, plan, decisions, now, baseline_id=None):
        revision = row["revision"] + 1
        history, trust = json_models(plan.rules), json.dumps(sorted(plan.verified_rule_hashes))
        decision_json = json_models(decisions)
        result = con.execute("UPDATE workspaces SET revision=?,history=?,trust=?,decisions=?,baseline_document_id=? WHERE id=? AND revision=?",
                             (revision, history, trust, decision_json, baseline_id or row["baseline_document_id"], config.workspace_id, row["revision"]))
        if result.rowcount != 1:
            raise ServiceError(409, "STALE_REVISION", "Workspace changed while applying")
        con.execute("INSERT INTO snapshots VALUES (?,?,?,?,?,?)", (config.workspace_id, revision, utc_text(now), history, trust, decision_json))
        return revision

    def review_original(self, workspace_id, document_id, request):
        from backend.legacy_schemas_v1 import ReviewOriginalRequest
        request = ReviewOriginalRequest.model_validate(request.model_dump(mode="json"))
        with self.store.connect(write=True) as con:
            row = self.store.row(con, workspace_id)
            self._check_revision(row, request.expected_workspace_revision)
            doc = self.store.document(workspace_id, document_id, con)
            if doc.kind != DocumentKind.ORIGINAL or row["baseline_document_id"]:
                raise ServiceError(409, "ORIGINAL_REVIEW_BLOCKED", "Original review can bootstrap only an empty workspace")
            try:
                doc, _, plan = self._assess(con, workspace_id, document_id, self.clock())
            except ValueError as error:
                raise ServiceError(409, "ORIGINAL_REVIEW_BLOCKED", str(error)) from error
            if plan is None:
                raise ServiceError(409, "SOURCE_GATE_BLOCKED", "Original has unresolved source or evidence checks")
            now = self.clock()
            config = self.store.config(workspace_id, con)
            decisions = [evaluate_applicant(p, plan.rules, scheme_id=config.scheme_id, as_of_date=config.evaluation_date,
                                            verified_rule_hashes=plan.verified_rule_hashes) for p in config.profiles]
            doc.review_state, doc.reviewed_by, doc.reviewed_at, doc.intake_state = ReviewState.APPROVED, request.reviewed_by, now, IntakeState.APPLIED
            self._save_document(con, doc)
            self._commit(con, row, config, plan, decisions, now, document_id)
        return self.store.state(workspace_id)

    def apply(self, workspace_id, amendment_id, request):
        from backend.legacy_schemas_v1 import ApplyAmendmentRequest
        request = ApplyAmendmentRequest.model_validate(request.model_dump(mode="json"))
        with self.store.connect(write=True) as con:
            row = self.store.row(con, workspace_id)
            self._check_revision(row, request.expected_workspace_revision)
            config = self.store.config(workspace_id, con)
            existing = self.store.amendment(workspace_id, amendment_id, con)
            if existing.intake_state == IntakeState.APPLIED:
                raise ServiceError(409, "ALREADY_APPLIED", "Amendment was already applied")
            now = self.clock()
            try:
                doc, amendment, plan = self._assess(con, workspace_id, existing.corrigendum_document_id, now)
            except ValueError as error:
                raise ServiceError(409, "SOURCE_GATE_BLOCKED", str(error)) from error
            if plan is None:
                raise ServiceError(409, "SOURCE_GATE_BLOCKED", "Amendment has unresolved source, evidence or precedence checks")
            preview = self._impact(row, config, plan, amendment_id, now)
            event = ImpactEvent.model_validate(preview.model_dump(mode="json") | {"event_kind":"APPLIED", "event_id":f"event-{uuid.uuid4().hex}"})
            amendment.review_state, amendment.reviewed_by, amendment.reviewed_at = ReviewState.APPROVED, request.reviewed_by, now
            amendment.intake_state = IntakeState.APPLIED
            doc.review_state, doc.reviewed_by, doc.reviewed_at, doc.intake_state = ReviewState.APPROVED, request.reviewed_by, now, IntakeState.APPLIED
            self._save_document(con, doc)
            self._save_amendment(con, amendment)
            revision = self._commit(con, row, config, plan, [t.after for t in event.transitions], now)
            con.execute("INSERT INTO events(id,workspace,payload) VALUES (?,?,?)", (event.event_id, workspace_id, event.model_dump_json()))
            return ApplyAmendmentResponse(workspace_revision=revision, event=event)

    def timeline(self, workspace_id, as_of_date, known_at=None):
        with self.store.connect() as con:
            row = self.store.row(con, workspace_id)
            config = self.store.config(workspace_id, con)
            history, trust = self.store.history(row), json.loads(row["trust"])
            if known_at is not None:
                try:
                    known_text = utc_text(known_at)
                except ValueError as error:
                    raise ServiceError(422, "AWARE_TIMESTAMP_REQUIRED", str(error)) from error
                snapshot = con.execute("SELECT * FROM snapshots WHERE workspace=? AND recorded_at<=? ORDER BY revision DESC LIMIT 1", (workspace_id, known_text)).fetchone()
                history, trust = (self.store.history(snapshot), json.loads(snapshot["trust"])) if snapshot else ([], [])
                history = [r for r in history if all(self.store.document(workspace_id, a.document_id, con).acquired_at <= known_at for a in r.evidence)]
            active = effective_rules(history, scheme_id=config.scheme_id, as_of_date=as_of_date)
            return TimelineSnapshot(workspace_id=workspace_id, as_of_date=as_of_date, known_at=known_at,
                                    effective_rules=active, rule_set_sha256=rule_set_fingerprint(active, verified_rule_hashes=trust),
                                    decisions=[evaluate_applicant(p, active, scheme_id=config.scheme_id, as_of_date=as_of_date, verified_rule_hashes=trust) for p in config.profiles])
