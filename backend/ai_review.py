from datetime import date


def review_evidence(vendor, evidence):
    name = evidence["name"].lower()
    file_name = (evidence.get("fileName") or "").lower()
    notes = (evidence.get("notes") or "").lower()
    valid_until = evidence.get("validUntil")

    flags = []
    suggested_action = "Reviewer can approve if the document matches the requirement."
    suggested_risk = "Low"
    confidence = 86

    if not file_name:
        flags.append("Missing file")
        suggested_action = "Request the evidence file."
        suggested_risk = "High"
        confidence = 94
    if valid_until and valid_until < date.today().isoformat():
        flags.append("Expired evidence")
        suggested_action = "Request a current version before approval."
        suggested_risk = "High"
        confidence = 91
    if "pen-test" in name and "date" not in notes and "202" not in notes:
        flags.append("Testing date unclear")
        suggested_action = "Ask vendor to confirm test date and remediation status."
        suggested_risk = "Medium"
        confidence = 78
    if "ai data usage" in name and ("training" in notes or "model improvement" in notes):
        flags.append("Customer data training risk")
        suggested_action = "Reject or require written restriction against customer-data training."
        suggested_risk = "High"
        confidence = 89
    if "subprocessor" in name and ("missing" in notes or "unknown" in notes):
        flags.append("Subprocessor visibility gap")
        suggested_action = "Request current subprocessor list before approval."
        suggested_risk = "High"
        confidence = 92

    doc_type = evidence["evidenceType"]
    if "soc" in name:
        doc_type = "SOC 2 Type II Report"
    elif "dpa" in name:
        doc_type = "Data Processing Agreement"

    if not flags:
        summary = f"{evidence['name']} appears complete and aligned with the requested evidence type."
    else:
        summary = f"{evidence['name']} was submitted, but AI found {len(flags)} issue(s): {', '.join(flags)}."

    return {
        "documentType": doc_type,
        "summary": summary,
        "extractedFields": {
            "file": evidence.get("fileName"),
            "validUntil": valid_until or "Not provided",
            "reviewerRole": evidence["reviewerRole"],
        },
        "flags": flags,
        "suggestedRisk": suggested_risk,
        "confidence": confidence,
        "suggestedAction": suggested_action,
    }
