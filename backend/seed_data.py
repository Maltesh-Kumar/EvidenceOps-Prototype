from copy import deepcopy

from .audit_log import add_audit
from .risk_engine import calculate_risk
from .status_engine import evidence_progress, rollup_vendor_status
from .templates import get_template, list_templates


def make_evidence(template_id, overrides=None):
    overrides = overrides or {}
    template = get_template(template_id)
    evidence = []
    for req in template["requirements"]:
        item = deepcopy(req)
        item.update(
            {
                "status": "Requested",
                "fileName": None,
                "submittedBy": None,
                "submittedAt": None,
                "validUntil": None,
                "notes": "",
                "aiReview": None,
                "decisionReason": "",
            }
        )
        item.update(overrides.get(item["name"], {}))
        evidence.append(item)
    return evidence


def vendor(vendor_id, name, category, owner, reviewer, stage, due_date, risk_answers, template_id, evidence_overrides, issues=None, followups=None):
    risk = calculate_risk(risk_answers)
    item = {
        "id": vendor_id,
        "name": name,
        "category": category,
        "owner": owner,
        "reviewer": reviewer,
        "stage": stage,
        "dueDate": due_date,
        "riskAnswers": risk_answers,
        "risk": risk,
        "templateId": template_id,
        "templateName": get_template(template_id)["name"],
        "evidence": make_evidence(template_id, evidence_overrides),
        "riskIssues": issues or [],
        "followups": followups or [],
        "overallDecision": None,
        "status": "Draft",
        "progress": 0,
    }
    item["status"] = rollup_vendor_status(item)
    item["progress"] = evidence_progress(item)
    return item


def create_seed_db():
    db = {"vendors": {}, "templates": list_templates(), "audit": []}
    acme_issues = [
        {
            "id": "issue-acme-subprocessors",
            "title": "Subprocessor list missing",
            "linkedEvidenceId": "subprocessor-list",
            "severity": "High",
            "owner": "Head of Support",
            "dueDate": "2026-06-05",
            "status": "Waiting on Vendor",
            "recommendation": "Request latest subprocessor list before approval.",
        },
        {
            "id": "issue-acme-ai-training",
            "title": "AI policy allows customer data training",
            "linkedEvidenceId": "ai-data-usage-policy",
            "severity": "High",
            "owner": "Security Manager",
            "dueDate": "2026-06-03",
            "status": "Open",
            "recommendation": "Require vendor commitment that customer data is not used for model training.",
        },
    ]
    acme_followups = [
        {
            "id": "follow-acme-subprocessors",
            "issueId": "issue-acme-subprocessors",
            "owner": "Head of Support",
            "dueDate": "2026-06-05",
            "status": "Waiting",
            "message": "Please collect the current subprocessor list from AcmeSupport AI before approval can proceed.",
        }
    ]
    acme = vendor(
        "v-acme",
        "AcmeSupport AI",
        "Customer Support AI SaaS",
        "Head of Support",
        "Security Manager",
        "Pre-onboarding",
        "2026-06-10",
        {"pii": True, "storesData": True, "api": True, "critical": True, "ai": True, "unknownSubprocessors": True},
        "tpl-high-ai",
        {
            "SOC 2 or ISO 27001": {"status": "Approved", "fileName": "acme-soc2.pdf", "validUntil": "2026-12-31", "notes": "Latest SOC 2 report.", "decisionReason": "Report covers security controls."},
            "DPA": {"status": "Approved", "fileName": "acme-dpa.pdf", "validUntil": "2027-06-10", "notes": "Signed DPA.", "decisionReason": "Legal approved."},
            "Subprocessor List": {"status": "Missing", "notes": "Vendor has not provided the list."},
            "Pen-test Summary": {"status": "Needs Clarification", "fileName": "acme-pentest.pdf", "notes": "Summary received but test date is unclear.", "decisionReason": "Need confirmation of latest test date."},
            "MFA/RBAC Screenshot": {"status": "Approved", "fileName": "acme-rbac.png", "validUntil": "2026-11-30", "notes": "Admin roles visible.", "decisionReason": "MFA and RBAC visible."},
            "AI Data Usage Policy": {"status": "Rejected", "fileName": "acme-ai-policy.pdf", "validUntil": "2027-01-15", "notes": "Policy permits customer data for model improvement and training.", "decisionReason": "Customer data training is not acceptable."},
        },
        acme_issues,
        acme_followups,
    )
    cloud = vendor(
        "v-cloudbooks",
        "CloudBooks Payroll",
        "Payroll SaaS",
        "Finance Lead",
        "Compliance Manager",
        "Annual review",
        "2026-05-30",
        {"financial": True, "storesData": True, "subprocessors": True},
        "tpl-medium",
        {
            "SOC 2 Report": {"status": "Expired", "fileName": "cloudbooks-soc2.pdf", "validUntil": "2025-12-31", "notes": "Report older than 12 months."},
            "DPA": {"status": "Approved", "fileName": "cloudbooks-dpa.pdf", "validUntil": "2027-05-01", "notes": "Signed DPA."},
            "Access Control Policy": {"status": "Approved", "fileName": "cloudbooks-access.pdf", "validUntil": "2026-10-01", "notes": "SSO and MFA described."},
            "Subprocessor List": {"status": "Approved", "fileName": "cloudbooks-subprocessors.pdf", "validUntil": "2026-09-01", "notes": "Current list present."},
            "Data Retention Policy": {"status": "Submitted", "fileName": "cloudbooks-retention.pdf", "validUntil": "2027-01-01", "notes": "Pending reviewer check."},
        },
    )
    design = vendor(
        "v-designhub",
        "DesignHub",
        "Design Collaboration Tool",
        "Design Lead",
        "Ops Manager",
        "Pre-onboarding",
        "2026-06-20",
        {},
        "tpl-low",
        {
            "Company Registration": {"status": "Approved", "fileName": "designhub-registration.pdf", "validUntil": "2027-01-01"},
            "GST Details": {"status": "Approved", "fileName": "designhub-gst.pdf", "validUntil": "2027-01-01"},
            "Bank Details": {"status": "Approved", "fileName": "designhub-bank.pdf", "validUntil": "2027-01-01"},
            "Basic Agreement": {"status": "Approved", "fileName": "designhub-agreement.pdf", "validUntil": "2027-01-01"},
        },
    )
    for item in [acme, cloud, design]:
        db["vendors"][item["id"]] = item
        add_audit(db, "System", f"Seeded demo vendor {item['name']}", item["id"], item["name"])
    return db
