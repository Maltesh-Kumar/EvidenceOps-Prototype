from datetime import date


BLOCKING_EVIDENCE_STATUSES = {"Missing", "Rejected", "Expired", "Needs Clarification"}


def required_evidence(vendor):
    return [
        item
        for item in vendor["evidence"]
        if item["requiredType"] in {"Required", "Conditional"}
    ]


def evidence_progress(vendor):
    required = required_evidence(vendor)
    if not required:
        return 0
    complete = [item for item in required if item["status"] in {"Approved", "Waived"}]
    return round((len(complete) / len(required)) * 100)


def rollup_vendor_status(vendor):
    if vendor.get("overallDecision") == "Rejected":
        return "Rejected"
    if not vendor.get("templateId"):
        return "Draft"

    evidence = required_evidence(vendor)
    statuses = {item["status"] for item in evidence}
    open_high_issues = [
        issue
        for issue in vendor["riskIssues"]
        if issue["severity"] == "High" and issue["status"] in {"Open", "In Progress", "Waiting on Vendor", "Rejected / Blocked"}
    ]
    accepted_risks = [issue for issue in vendor["riskIssues"] if issue["status"] == "Accepted Risk"]

    if not evidence or statuses <= {"Requested"}:
        return "Evidence Requested"
    if statuses & BLOCKING_EVIDENCE_STATUSES or open_high_issues:
        return "Action Required"
    if any(status == "Submitted" for status in statuses) and all(status == "Submitted" for status in statuses):
        return "Ready for Review"
    if any(status == "Submitted" for status in statuses):
        return "Partially Submitted"
    if all(status in {"Approved", "Waived"} for status in statuses):
        return "Approved with Risk" if accepted_risks else "Approved"
    return "In Review"


def mark_missing_or_overdue(vendor):
    today = date.today().isoformat()
    for item in vendor["evidence"]:
        if item["status"] == "Requested" and vendor["dueDate"] < today:
            item["status"] = "Missing"
    vendor["status"] = rollup_vendor_status(vendor)
    vendor["progress"] = evidence_progress(vendor)
    return vendor
