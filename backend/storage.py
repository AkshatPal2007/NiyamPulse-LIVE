"""SQLite persistence with immutable sources/extractions and atomic write scopes."""
from contextlib import contextmanager
from datetime import date, datetime
import base64
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3

from pydantic import Field, TypeAdapter

from backend.legacy_schemas_v1 import (
    AmendmentRecord, ApplicantDecision, ApplicantProfile, ContractModel, DocumentExtraction,
    EventFeedResponse, Id, ImpactEvent, Sha256, SourceDocument, WorkspaceState,
)
from backend.services.rule_engine import evaluate_applicant, validated_rules


class ServiceError(ValueError):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code = status, code
        super().__init__(message)


class WorkspaceConfig(ContractModel):
    """Local operator configuration, never accepted from HTTP upload fields."""
    workspace_id: Id
    scheme_id: Id
    issuing_authority: str = Field(min_length=1)
    synthetic: bool = False
    evaluation_date: date
    configured_hashes: list[Sha256] = Field(default_factory=list)
    intake_directory: str | None = None
    profiles: list[ApplicantProfile] = Field(default_factory=list)


def json_models(models) -> str:
    return json.dumps([m.model_dump(mode="json") for m in models], ensure_ascii=False, separators=(",", ":"))


def utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An aware timestamp is required")
    from datetime import timezone
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect(snapshot=False) as con:
            con.execute("PRAGMA journal_mode=WAL")
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, 1}:
                raise ServiceError(500, "DATABASE_VERSION_UNSUPPORTED", "Database migration version is unsupported")
            con.executescript((Path(__file__).parent / "migrations" / "001_initial.sql").read_text(encoding="utf-8"))
            con.execute("INSERT OR IGNORE INTO metadata VALUES (?,?)", ("cursor_secret", secrets.token_hex(32)))
            con.commit()

    @contextmanager
    def connect(self, *, write=False, snapshot=True):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                con.execute("BEGIN IMMEDIATE")
            elif snapshot:
                # A workspace response spans multiple SELECTs. Keep revision,
                # rules, documents and latest event in one committed snapshot.
                con.execute("BEGIN")
            yield con
            if write:
                con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def row(self, con, workspace_id):
        row = con.execute("SELECT * FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
        if row is None:
            raise ServiceError(404, "WORKSPACE_NOT_FOUND", "Workspace does not exist; configure it locally first")
        return row

    def config(self, workspace_id, con=None):
        if con is None:
            with self.connect() as connection:
                return self.config(workspace_id, connection)
        return WorkspaceConfig.model_validate_json(self.row(con, workspace_id)["config"])

    def configure(self, config: WorkspaceConfig):
        config = WorkspaceConfig.model_validate(config.model_dump(mode="json"))
        ids = [p.applicant_id for p in config.profiles]
        if len(ids) != len(set(ids)) or any(p.workspace_id != config.workspace_id for p in config.profiles):
            raise ServiceError(400, "INVALID_COHORT", "Profiles need unique IDs and the configured workspace")
        if config.intake_directory:
            config.intake_directory = str(Path(config.intake_directory).resolve())
        with self.connect(write=True) as con:
            existing = con.execute("SELECT config FROM workspaces WHERE id=?", (config.workspace_id,)).fetchone()
            if existing:
                if WorkspaceConfig.model_validate_json(existing[0]) != config:
                    raise ServiceError(409, "CONFIGURATION_EXISTS", "Existing workspace configuration is immutable; use another workspace ID")
                return
            decisions = [evaluate_applicant(p, [], scheme_id=config.scheme_id, as_of_date=config.evaluation_date) for p in config.profiles]
            con.execute("INSERT INTO workspaces(id,config,decisions) VALUES (?,?,?)",
                        (config.workspace_id, config.model_dump_json(), json_models(decisions)))

    def document(self, workspace_id, document_id, con=None):
        if con is None:
            with self.connect() as connection:
                return self.document(workspace_id, document_id, connection)
        row = con.execute("SELECT s.payload FROM documents d JOIN document_states s ON s.id=d.id WHERE d.id=? AND d.workspace=?", (document_id, workspace_id)).fetchone()
        if row is None:
            raise ServiceError(404, "DOCUMENT_NOT_FOUND", "Document not found in this workspace")
        return SourceDocument.model_validate_json(row[0])

    def pdf(self, workspace_id, document_id, con=None):
        if con is None:
            with self.connect() as connection:
                return self.pdf(workspace_id, document_id, connection)
        document = self.document(workspace_id, document_id, con)
        row = con.execute("SELECT p.content FROM pdf_sources p JOIN documents d ON d.sha=p.sha WHERE d.id=? AND d.workspace=?", (document_id, workspace_id)).fetchone()
        data = bytes(row[0])
        if hashlib.sha256(data).hexdigest() != document.sha256:
            raise ServiceError(409, "SOURCE_INTEGRITY_FAILED", "Stored PDF hash does not match its acquisition record")
        return data

    def extraction(self, workspace_id, document_id, con=None):
        if con is None:
            with self.connect() as connection:
                return self.extraction(workspace_id, document_id, connection)
        doc = self.document(workspace_id, document_id, con)
        self.pdf(workspace_id, document_id, con)
        row = con.execute("SELECT * FROM extractions WHERE id=? AND sha=?", (doc.extraction_id, doc.sha256)).fetchone()
        if row is None:
            raise ServiceError(409, "EXTRACTION_UNAVAILABLE", "No completed immutable extraction exists")
        if hashlib.sha256(row["payload"].encode("utf-8")).hexdigest() != row["payload_sha"]:
            raise ServiceError(409, "EXTRACTION_INTEGRITY_FAILED", "Immutable extraction checksum failed")
        result = DocumentExtraction.model_validate_json(row["payload"])
        expected_id = "ext-" + hashlib.sha256(f"{doc.sha256}:{row['version']}".encode()).hexdigest()
        if result.document_sha256 != doc.sha256 or result.extraction_id != expected_id or result.extractor_version != row["version"]:
            raise ServiceError(409, "EXTRACTION_INTEGRITY_FAILED", "Immutable extraction identity failed")
        return result.model_copy(update={"document_id": document_id})

    def amendment(self, workspace_id, amendment_id, con=None):
        if con is None:
            with self.connect() as connection:
                return self.amendment(workspace_id, amendment_id, connection)
        row = con.execute("SELECT payload FROM amendments WHERE id=? AND workspace=?", (amendment_id, workspace_id)).fetchone()
        if row is None:
            raise ServiceError(404, "AMENDMENT_NOT_FOUND", "Amendment not found in this workspace")
        return AmendmentRecord.model_validate_json(row[0])

    def history(self, row):
        from backend.legacy_schemas_v1 import RuleDefinition
        return validated_rules(TypeAdapter(list[RuleDefinition]).validate_json(row["history"]))

    def state(self, workspace_id):
        with self.connect() as con:
            row = self.row(con, workspace_id)
            config = self.config(workspace_id, con)
            documents = [SourceDocument.model_validate_json(r[0]) for r in con.execute("SELECT s.payload FROM document_states s JOIN documents d ON d.id=s.id WHERE d.workspace=? ORDER BY d.rowid", (workspace_id,))]
            amendments = [AmendmentRecord.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM amendments WHERE workspace=? ORDER BY rowid", (workspace_id,))]
            event = con.execute("SELECT payload FROM events WHERE workspace=? ORDER BY sequence DESC LIMIT 1", (workspace_id,)).fetchone()
            from backend.services.rule_engine import effective_rules
            return WorkspaceState(
                workspace_id=workspace_id, revision=row["revision"], scheme_id=config.scheme_id,
                as_of_date=config.evaluation_date, synthetic=config.synthetic, documents=documents,
                amendments=amendments, profiles=config.profiles,
                active_rules=effective_rules(self.history(row), scheme_id=config.scheme_id, as_of_date=config.evaluation_date),
                decisions=TypeAdapter(list[ApplicantDecision]).validate_json(row["decisions"]),
                latest_event=ImpactEvent.model_validate_json(event[0]) if event else None,
            )

    def events(self, workspace_id, cursor=None):
        with self.connect() as con:
            self.row(con, workspace_id)
            secret = bytes.fromhex(con.execute("SELECT value FROM metadata WHERE key='cursor_secret'").fetchone()[0])
            sequence = 0
            if cursor:
                try:
                    body, signature = cursor.split(".")
                    expected = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
                    if not hmac.compare_digest(expected, signature):
                        raise ValueError()
                    decoded = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
                    if decoded["workspace"] != workspace_id or type(decoded["sequence"]) is not int or decoded["sequence"] < 0:
                        raise ValueError()
                    sequence = decoded["sequence"]
                except (ValueError, KeyError, TypeError):
                    raise ServiceError(400, "INVALID_CURSOR", "Event cursor is invalid for this workspace") from None
            rows = con.execute("SELECT sequence,payload FROM events WHERE workspace=? AND sequence>? ORDER BY sequence LIMIT 100", (workspace_id, sequence)).fetchall()
            if rows:
                sequence = rows[-1]["sequence"]
            body = base64.urlsafe_b64encode(json.dumps({"workspace":workspace_id,"sequence":sequence}, separators=(",", ":")).encode()).decode().rstrip("=")
            signature = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
            return EventFeedResponse(workspace_id=workspace_id, events=[ImpactEvent.model_validate_json(r["payload"]) for r in rows], next_cursor=f"{body}.{signature}")
