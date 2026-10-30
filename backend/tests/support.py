"""Explicitly synthetic test builders; these do not certify real sources."""
from backend.schemas import ApplicantProfile, SourceEvidence
from pydantic import TypeAdapter
from backend.schemas import RuleDefinition


def evidence():
    return SourceEvidence(document_id="synthetic-original", document_sha256="a" * 64,
                          extraction_id="synthetic-extraction", page_number=1,
                          literal_quote="SYNTHETIC TEST ONLY")


def make_rule(kind="minimum_marks", value=70, **overrides):
    values = {
        "minimum_marks": {"min_marks_percent": value},
        "maximum_income_inr": {"max_annual_income_inr": value},
        "application_deadline": {"deadline_on": value},
        "age_bounds": dict(zip(("min_age_years", "max_age_years", "age_as_of"), value if isinstance(value, tuple) else (18, 25, "2026-10-30"))),
        "required_documents": {"required_document_codes": value},
    }
    return TypeAdapter(RuleDefinition).validate_python(dict(
        rule_id=f"rule-{kind}", scheme_id="demo", effective_from="2026-10-01",
        evidence=[evidence()], rule_type=kind, **values[kind],
    ) | overrides)


def profile(**overrides):
    fields = dict(applicant_id="synthetic-01", workspace_id="workspace-demo",
                  display_name="Synthetic Applicant 01", marks_percent=75,
                  annual_household_income_inr=200000, date_of_birth="2006-10-30",
                  planned_submission_on="2026-10-30", available_document_codes=["ID", "INCOME"],
                  document_inventory_complete=True, updated_at="2026-10-30T00:00:00Z")
    return ApplicantProfile.model_validate(fields | overrides)


def verified(rules):
    from backend.services.rule_engine import rule_fingerprint
    return frozenset(rule_fingerprint(rule) for rule in rules)
