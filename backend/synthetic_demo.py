"""OFFLINE SYNTHETIC ENGINE PREVIEW, with a deliberately narrow text parser.

Only built-in, declared synthetic fixture clauses are supported. Text hashes
refer to the actual UTF-8 fixture files, NOT PDFs. Attestations below represent
curated test assumptions, not a production source gate or human approval.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter

from backend.schemas import (
    AmendmentChange, ApplicantProfile, ImpactEvent, RuleDefinition, SourceEvidence,
)
from backend.services.amendments import change_fingerprint, plan_amendment
from backend.services.impact import preview_impact
from backend.services.rule_engine import rule_fingerprint

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "datasets" / "synthetic" / "phase1"
_RULE = TypeAdapter(RuleDefinition)


def parse_synthetic_clause(text: str, language: str) -> dict:
    """Fixture compatibility wrapper around the shared closed clause parser."""
    from backend.services.clauses import parse_closed_clause
    return parse_closed_clause(text, language)


@dataclass(frozen=True)
class SyntheticCase:
    case_id: str
    workspace_id: str
    scheme_id: str
    as_of_date: date
    occurred_at: datetime
    documents: dict[str, bytes]
    rules: tuple[RuleDefinition, ...]
    changes: tuple[AmendmentChange, ...]
    profiles: tuple[ApplicantProfile, ...]


def load_case(path: Path) -> SyntheticCase:
    path = path.resolve()
    if not path.is_relative_to(FIXTURE_ROOT.resolve()):
        raise ValueError("Only built-in synthetic fixtures may use this demo loader")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("synthetic") is not True or raw.get("source_format") != "utf8_text_not_pdf":
        raise ValueError("A declared synthetic UTF-8 text fixture is required")
    documents = {}
    for key, filename in raw["documents"].items():
        document_path = (path.parent / filename).resolve()
        if not document_path.is_relative_to(FIXTURE_ROOT.resolve()):
            raise ValueError("Synthetic document path is outside the fixture directory")
        documents[key] = document_path.read_bytes()

    def parse_rule(spec):
        source = documents[spec["document_id"]]
        digest = hashlib.sha256(source).hexdigest()
        lines = source.decode("utf-8").splitlines(keepends=True)
        line_number = spec["clause_line"]
        if not isinstance(line_number, int) or not 1 <= line_number <= len(lines):
            raise ValueError("Invalid synthetic clause line")
        quote = lines[line_number - 1].rstrip("\r\n")
        offset = sum(len(line) for line in lines[:line_number - 1])
        anchor = SourceEvidence(
            document_id=spec["document_id"], document_sha256=digest,
            extraction_id=f"synthetic-text-v1-{digest[:16]}", page_number=1,
            literal_quote=quote, start_char=offset, end_char=offset + len(quote),
        )
        return _RULE.validate_python(dict(
            rule_id=spec["rule_id"], scheme_id=raw["scheme_id"],
            scope_key=spec.get("scope_key", "all_applicants"),
            effective_from=spec["effective_from"], effective_until=spec.get("effective_until"),
            evidence=[anchor], **parse_synthetic_clause(quote, raw["language"]),
        ))

    rules = tuple(parse_rule(spec) for spec in raw["original_rules"])
    changes = []
    for spec in raw["changes"]:
        # Built-in pairs use ADD/REPLACE. REVOKE is covered by pure-engine tests.
        proposed = parse_rule(spec["proposed_rule"])
        changes.append(AmendmentChange(
            change_id=spec["change_id"], operation=spec["operation"],
            target_rule_id=spec.get("target_rule_id"), proposed_rule=proposed,
            effective_from=spec["effective_from"], amendment_evidence=proposed.evidence,
        ))
    profiles = tuple(ApplicantProfile.model_validate(spec) for spec in raw["profiles"])
    return SyntheticCase(
        case_id=raw["case_id"], workspace_id=raw["workspace_id"], scheme_id=raw["scheme_id"],
        as_of_date=date.fromisoformat(raw["as_of_date"]),
        occurred_at=datetime.fromisoformat(raw["occurred_at"]),
        documents=documents, rules=rules, changes=tuple(changes), profiles=profiles,
    )


def replay_case(path: Path) -> ImpactEvent:
    case = load_case(path)
    # EXPLICIT TEST ASSUMPTION: curated fixtures supply reviewed candidate maps.
    # The parser measures source values/anchors; it does not authenticate them.
    before_trust = frozenset(rule_fingerprint(r) for r in case.rules)
    proposal_trust = frozenset(rule_fingerprint(c.proposed_rule) for c in case.changes if c.proposed_rule)
    plan = plan_amendment(
        case.rules, case.changes, scheme_id=case.scheme_id,
        verified_rule_hashes=before_trust | proposal_trust,
        verified_change_hashes={change_fingerprint(c) for c in case.changes},
    )
    return preview_impact(
        case.profiles, case.rules, plan.rules, event_id=f"synthetic-preview-{case.case_id}",
        workspace_id=case.workspace_id, amendment_id=f"synthetic-amendment-{case.case_id}",
        scheme_id=case.scheme_id, as_of_date=case.as_of_date, occurred_at=case.occurred_at,
        before_verified_rule_hashes=before_trust, after_verified_rule_hashes=plan.verified_rule_hashes,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    names = sorted(p.stem for p in FIXTURE_ROOT.glob("*.json"))
    parser.add_argument("--case", choices=names)
    parser.add_argument("--json", action="store_true", help="Print actual ImpactEvent JSON")
    args = parser.parse_args()
    for name in [args.case] if args.case else names:
        event = replay_case(FIXTURE_ROOT / f"{name}.json")
        if args.json:
            print(event.model_dump_json())
        else:
            print(f"OFFLINE SYNTHETIC ENGINE PREVIEW: {name}")
            print("Decision support only; not official approval.")
            print("Source: curated UTF-8 test text; no PDF/OCR, source gate, or live API.")
            print(json.dumps(event.counts.model_dump(), sort_keys=True))
            for transition in event.transitions:
                print(f"  {transition.applicant_id}: {transition.before.status.value} -> {transition.after.status.value} ({transition.direction.value})")


if __name__ == "__main__":
    main()
