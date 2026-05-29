from datetime import date
from uuid import uuid4

from .ai_review import review_evidence
from .audit_log import add_audit
from .risk_engine import calculate_risk
from .seed_data import create_seed_db, make_evidence
from .status_engine import evidence_progress, mark_missing_or_overdue, rollup_vendor_status
from .templates import get_template, recommend_template


class WorkflowService:
    def __init__(self):
        self.db = create_seed_db()

    def reset(self):
        self.db = create_seed_db()
        return self.state()

    def state(self):
        for vendor in self.db["vendors"].values():
            mark_missing_or_overdue(vendor)
        vendors = list(self.db["vendors"].values())
        return {
            "vendors": vendors,
            "templates": self.db["templates"],
            "metrics": self.metrics(vendors),
            "queue": self.reviewer_queue(vendors),
            "followups": self.followups(vendors),
            "audit": self.db["audit"],
        }

    def metrics(self, vendors):
        evidence = [item for vendor in vendors for item in vendor["evidence"]]
        return {
            "Vendors Under Review": len([v for v in vendors if v["status"] not in {"Approved", "Rejected"}]),
            "High-Risk Vendors": len([v for v in vendors if v["risk"]["tier"] == "High"]),
            "Pending Evidence": len([e for e in evidence if e["status"] in {"Requested", "Missing"}]),
            "Overdue Evidence": len([e for e in evidence if e["status"] in {"Missing", "Expired"}]),
            "Ready for Review": len([v for v in vendors if v["status"] == "Ready for Review"]),
            "Action Required": len([v for v in vendors if v["status"] == "Action Required"]),
            "Approved Vendors": len([v for v in vendors if v["status"] == "Approved"]),
            "Approved with Risk": len([v for v in vendors if v["status"] == "Approved with Risk"]),
            "Evidence Expiring Soon": len([e for e in evidence if e.get("validUntil") and date.today().isoformat() <= e["validUntil"] <= "2026-06-30"]),
        }

    def reviewer_queue(self, vendors):
        queue = []
        risk_rank = {"High": 0, "Medium": 1, "Low": 2}
        for vendor in vendors:
            for item in vendor["evidence"]:
                if item["status"] in {"Submitted", "Needs Clarification", "Expired", "Rejected"}:
                    flags = item.get("aiReview", {}).get("flags", []) if item.get("aiReview") else []
                    queue.append(
                        {
                            "vendorId": vendor["id"],
                            "vendorName": vendor["name"],
                            "riskTier": vendor["risk"]["tier"],
                            "evidenceId": item["id"],
                            "evidenceName": item["name"],
                            "status": item["status"],
                            "dueDate": vendor["dueDate"],
                            "aiFlag": ", ".join(flags) if flags else "None",
                            "priority": self.priority_label(vendor, item, flags),
                        }
                    )
        return sorted(queue, key=lambda row: (risk_rank[row["riskTier"]], row["dueDate"], row["aiFlag"] == "None"))

    def priority_label(self, vendor, evidence, flags):
        if vendor["risk"]["tier"] == "High" and (flags or evidence["status"] in {"Rejected", "Expired", "Needs Clarification"}):
            return "Critical"
        if evidence["status"] in {"Expired", "Rejected"} or flags:
            return "High"
        if vendor["risk"]["tier"] == "Medium":
            return "Medium"
        return "Low"

    def followups(self, vendors):
        return [followup | {"vendorId": vendor["id"], "vendorName": vendor["name"]} for vendor in vendors for followup in vendor["followups"]]

    def create_vendor(self, payload):
        risk_answers = payload.get("riskAnswers", {})
        risk = calculate_risk(risk_answers)
        template_id = payload.get("templateId") or recommend_template(risk["tier"], risk_answers.get("ai"))
        template = get_template(template_id)
        vendor_id = f"v-{uuid4().hex[:8]}"
        vendor = {
            "id": vendor_id,
            "name": payload["name"],
            "category": payload["category"],
            "owner": payload["owner"],
            "reviewer": payload["reviewer"],
            "stage": payload.get("stage", "Pre-onboarding"),
            "dueDate": payload["dueDate"],
            "riskAnswers": risk_answers,
            "risk": risk,
            "templateId": template_id,
            "templateName": template["name"],
            "evidence": make_evidence(template_id),
            "riskIssues": [],
            "followups": [],
            "overallDecision": None,
            "status": "Evidence Requested",
            "progress": 0,
        }
        vendor["status"] = rollup_vendor_status(vendor)
        self.db["vendors"][vendor_id] = vendor
        add_audit(self.db, "Admin", f"Created vendor {vendor['name']}", vendor_id, vendor["name"])
        add_audit(self.db, "System", f"Calculated {risk['tier']} risk score {risk['score']}", vendor_id, "Risk assessment", {"signals": risk["signals"]})
        add_audit(self.db, "Admin", f"Applied template {template['name']}", vendor_id, template["name"])
        return self.state()

    def submit_evidence(self, vendor_id, evidence_id, payload):
        vendor, evidence = self.find_evidence(vendor_id, evidence_id)
        evidence.update(
            {
                "status": "Submitted",
                "fileName": payload["fileName"],
                "submittedBy": payload.get("submittedBy", vendor["owner"]),
                "submittedAt": date.today().isoformat(),
                "validUntil": payload.get("validUntil") or None,
                "notes": payload.get("notes", ""),
            }
        )
        evidence["aiReview"] = review_evidence(vendor, evidence)
        if evidence["aiReview"]["flags"] and "Expired evidence" in evidence["aiReview"]["flags"]:
            evidence["status"] = "Expired"
        vendor["status"] = rollup_vendor_status(vendor)
        vendor["progress"] = evidence_progress(vendor)
        add_audit(self.db, vendor["owner"], f"Uploaded {evidence['name']}", vendor_id, evidence["name"], {"fileName": evidence["fileName"]})
        add_audit(self.db, "AI Assistant", f"Completed AI review for {evidence['name']}", vendor_id, evidence["name"], {"flags": evidence["aiReview"]["flags"]})
        return self.state()

    def decide_evidence(self, vendor_id, evidence_id, payload):
        vendor, evidence = self.find_evidence(vendor_id, evidence_id)
        decision = payload["decision"]
        reason = payload.get("reason", "")
        evidence["status"] = decision
        evidence["decisionReason"] = reason
        if decision in {"Rejected", "Needs Clarification"} and payload.get("createIssue", True):
            self.create_issue(vendor, evidence, reason)
        vendor["status"] = rollup_vendor_status(vendor)
        vendor["progress"] = evidence_progress(vendor)
        add_audit(self.db, vendor["reviewer"], f"Marked {evidence['name']} as {decision}", vendor_id, evidence["name"], {"reason": reason})
        return self.state()

    def create_issue(self, vendor, evidence, reason):
        issue_id = f"issue-{uuid4().hex[:8]}"
        issue = {
            "id": issue_id,
            "title": f"{evidence['name']} needs action",
            "linkedEvidenceId": evidence["id"],
            "severity": "High" if vendor["risk"]["tier"] == "High" else "Medium",
            "owner": vendor["owner"],
            "dueDate": vendor["dueDate"],
            "status": "Waiting on Vendor",
            "recommendation": reason or evidence.get("aiReview", {}).get("suggestedAction", "Request clarification before approval."),
        }
        vendor["riskIssues"].append(issue)
        followup = {
            "id": f"follow-{uuid4().hex[:8]}",
            "issueId": issue_id,
            "owner": vendor["owner"],
            "dueDate": vendor["dueDate"],
            "status": "Not Started",
            "message": f"Please resolve: {issue['title']}. {issue['recommendation']}",
        }
        vendor["followups"].append(followup)
        add_audit(self.db, "System", f"Created risk issue {issue['title']}", vendor["id"], evidence["name"])
        add_audit(self.db, "System", f"Created follow-up for {vendor['owner']}", vendor["id"], issue["title"])

    def update_issue_status(self, vendor_id, issue_id, status):
        vendor = self.db["vendors"][vendor_id]
        for issue in vendor["riskIssues"]:
            if issue["id"] == issue_id:
                issue["status"] = status
                add_audit(self.db, vendor["reviewer"], f"Updated risk issue to {status}", vendor_id, issue["title"])
                break
        vendor["status"] = rollup_vendor_status(vendor)
        return self.state()

    def update_followup_status(self, vendor_id, followup_id, status):
        vendor = self.db["vendors"][vendor_id]
        for followup in vendor["followups"]:
            if followup["id"] == followup_id:
                followup["status"] = status
                add_audit(self.db, "Admin", f"Updated follow-up to {status}", vendor_id, followup["message"])
                break
        return self.state()

    def reject_vendor(self, vendor_id, reason):
        vendor = self.db["vendors"][vendor_id]
        vendor["overallDecision"] = "Rejected"
        vendor["status"] = "Rejected"
        add_audit(self.db, vendor["reviewer"], f"Rejected vendor: {reason}", vendor_id, vendor["name"])
        return self.state()

    def find_evidence(self, vendor_id, evidence_id):
        vendor = self.db["vendors"][vendor_id]
        for evidence in vendor["evidence"]:
            if evidence["id"] == evidence_id:
                return vendor, evidence
        raise KeyError(f"Unknown evidence {evidence_id}")
