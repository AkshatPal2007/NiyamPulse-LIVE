"""Closed, explicitly declared notice grammar; never infer free-form conditions."""
import re


def parse_closed_clause(text: str, language: str) -> dict:
    descriptions = [
        (r"Minimum qualifying marks: ([0-9]+(?:\.[0-9]+)?)%\.", r"न्यूनतम अंक: ([0-9]+(?:\.[0-9]+)?)%।", "minimum_marks", ("min_marks_percent",)),
        (r"Maximum annual household income: INR ([0-9]+)\.", r"अधिकतम वार्षिक पारिवारिक आय: INR ([0-9]+)।", "maximum_income_inr", ("max_annual_income_inr",)),
        (r"Application deadline: ([0-9]{4}-[0-9]{2}-[0-9]{2})\.", r"आवेदन की अंतिम तिथि: ([0-9]{4}-[0-9]{2}-[0-9]{2})।", "application_deadline", ("deadline_on",)),
        (r"Age bounds: ([0-9]+)\.\.([0-9]+) years on ([0-9]{4}-[0-9]{2}-[0-9]{2})\.", r"आयु सीमा: ([0-9]+)\.\.([0-9]+) वर्ष; आधार तिथि: ([0-9]{4}-[0-9]{2}-[0-9]{2})।", "age_bounds", ("min_age_years", "max_age_years", "age_as_of")),
        (r"Required documents: ([A-Za-z0-9_, .:-]+)\.", r"आवश्यक दस्तावेज़: ([A-Za-z0-9_, .:-]+)।", "required_documents", ("required_document_codes",)),
    ]
    if language not in {"en", "hi"}:
        raise ValueError("Unsupported clause language")
    for en, hi, rule_type, names in descriptions:
        found = re.fullmatch(en if language == "en" else hi, text)
        if found:
            fields = dict(zip(names, found.groups()))
            if rule_type == "required_documents":
                fields["required_document_codes"] = [code.strip() for code in fields["required_document_codes"].split(",")]
            return {"rule_type": rule_type, **fields}
    raise ValueError("Unsupported clause; no rules inferred")
