import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .seed_data import create_seed_db
from .templates import list_templates

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.getenv("EVIDENCEOPS_DB", DATA_DIR / "evidenceops.sqlite"))

DEFAULT_USERS = [
    {"id": "user-admin", "name": "Admin", "role": "Admin / Ops Manager", "email": "admin@finedge.example"},
    {"id": "user-owner", "name": "Head of Support", "role": "Vendor Owner", "email": "support-owner@finedge.example"},
    {"id": "user-security", "name": "Security Manager", "role": "Reviewer", "email": "security@finedge.example"},
    {"id": "user-legal", "name": "Legal Counsel", "role": "Reviewer", "email": "legal@finedge.example"},
    {"id": "user-leadership", "name": "Leadership", "role": "Leadership / Auditor", "email": "leadership@finedge.example"},
]


def encode(value):
    return json.dumps({} if value is None else value, separators=(",", ":"))


def decode(value, fallback):
    if not value:
        return fallback
    return json.loads(value)


class EvidenceOpsDB:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()
        self.seed_if_empty()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self):
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS templates (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    risk_tier TEXT NOT NULL,
                    description TEXT NOT NULL,
                    requirements_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    email TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS vendors (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    overall_decision TEXT,
                    template_id TEXT,
                    template_name TEXT,
                    risk_score INTEGER NOT NULL DEFAULT 0,
                    risk_tier TEXT NOT NULL,
                    risk_signals_json TEXT NOT NULL,
                    risk_answers_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (template_id) REFERENCES templates(id)
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT NOT NULL,
                    vendor_id TEXT NOT NULL,
                    requirement_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    required_type TEXT NOT NULL,
                    reviewer_role TEXT NOT NULL,
                    validity_period TEXT NOT NULL,
                    auto_flag_rule TEXT NOT NULL,
                    followup_sla TEXT NOT NULL,
                    help_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    file_name TEXT,
                    submitted_by TEXT,
                    submitted_at TEXT,
                    valid_until TEXT,
                    notes TEXT NOT NULL DEFAULT '',
                    stored_path TEXT,
                    ai_review_json TEXT,
                    decision_reason TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL,
                    PRIMARY KEY (vendor_id, id),
                    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS risk_issues (
                    id TEXT PRIMARY KEY,
                    vendor_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    linked_evidence_id TEXT,
                    severity TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS followups (
                    id TEXT PRIMARY KEY,
                    vendor_id TEXT NOT NULL,
                    issue_id TEXT,
                    owner TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    time TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    vendor_id TEXT,
                    target TEXT,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_vendor ON evidence(vendor_id);
                CREATE INDEX IF NOT EXISTS idx_risk_issues_vendor ON risk_issues(vendor_id);
                CREATE INDEX IF NOT EXISTS idx_followups_vendor ON followups(vendor_id);
                CREATE INDEX IF NOT EXISTS idx_audit_vendor ON audit_logs(vendor_id);
                """
            )
            self.ensure_column(conn, "evidence", "stored_path", "TEXT")

    def seed_if_empty(self):
        with self.connect() as conn:
            for template in list_templates():
                self.upsert_template(conn, template)
            for user in DEFAULT_USERS:
                self.upsert_user(conn, user)
            count = conn.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
        if count == 0:
            self.reset_to_demo()

    def ensure_column(self, conn, table, column, definition):
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def reset_to_demo(self):
        seed = create_seed_db()
        with self.connect() as conn:
            conn.executescript(
                """
                DELETE FROM audit_logs;
                DELETE FROM followups;
                DELETE FROM risk_issues;
                DELETE FROM evidence;
                DELETE FROM vendors;
                DELETE FROM templates;
                """
            )
            for template in list_templates():
                self.upsert_template(conn, template)
            for user in DEFAULT_USERS:
                self.upsert_user(conn, user)
            for vendor in seed["vendors"].values():
                self.upsert_vendor(conn, vendor)
            for entry in reversed(seed["audit"]):
                self.insert_audit(conn, entry)

    def load_state(self):
        with self.connect() as conn:
            templates = [self.template_from_row(row) for row in conn.execute("SELECT * FROM templates ORDER BY risk_tier, name")]
            users = [self.user_from_row(row) for row in conn.execute("SELECT * FROM users ORDER BY role, name")]
            vendors = [self.vendor_from_row(conn, row) for row in conn.execute("SELECT * FROM vendors ORDER BY created_at")]
            audit = [self.audit_from_row(row) for row in conn.execute("SELECT * FROM audit_logs ORDER BY time DESC, id DESC")]
        return {"templates": templates, "users": users, "vendors": vendors, "audit": audit}

    def save_vendor(self, vendor):
        with self.connect() as conn:
            self.upsert_vendor(conn, vendor)

    def save_templates(self):
        with self.connect() as conn:
            for template in list_templates():
                self.upsert_template(conn, template)

    def upsert_user(self, conn, user):
        conn.execute(
            """
            INSERT INTO users (id, name, role, email)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                role=excluded.role,
                email=excluded.email
            """,
            (user["id"], user["name"], user["role"], user["email"]),
        )

    def add_audit(self, actor, action, vendor_id=None, target=None, metadata=None):
        with self.connect() as conn:
            next_id = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0] + 1
            entry = {
                "id": f"audit-{next_id}",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "actor": actor,
                "action": action,
                "vendorId": vendor_id,
                "target": target,
                "metadata": metadata or {},
            }
            self.insert_audit(conn, entry)
            return entry

    def upsert_template(self, conn, template):
        conn.execute(
            """
            INSERT INTO templates (id, name, risk_tier, description, requirements_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                risk_tier=excluded.risk_tier,
                description=excluded.description,
                requirements_json=excluded.requirements_json
            """,
            (
                template["id"],
                template["name"],
                template["riskTier"],
                template["description"],
                encode(template["requirements"]),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

    def upsert_vendor(self, conn, vendor):
        now = datetime.now().isoformat(timespec="seconds")
        existing = conn.execute("SELECT created_at FROM vendors WHERE id = ?", (vendor["id"],)).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO vendors (
                id, name, category, owner, reviewer, stage, due_date, status, progress,
                overall_decision, template_id, template_name, risk_score, risk_tier,
                risk_signals_json, risk_answers_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                owner=excluded.owner,
                reviewer=excluded.reviewer,
                stage=excluded.stage,
                due_date=excluded.due_date,
                status=excluded.status,
                progress=excluded.progress,
                overall_decision=excluded.overall_decision,
                template_id=excluded.template_id,
                template_name=excluded.template_name,
                risk_score=excluded.risk_score,
                risk_tier=excluded.risk_tier,
                risk_signals_json=excluded.risk_signals_json,
                risk_answers_json=excluded.risk_answers_json,
                updated_at=excluded.updated_at
            """,
            (
                vendor["id"],
                vendor["name"],
                vendor["category"],
                vendor["owner"],
                vendor["reviewer"],
                vendor["stage"],
                vendor["dueDate"],
                vendor["status"],
                vendor["progress"],
                vendor.get("overallDecision"),
                vendor.get("templateId"),
                vendor.get("templateName"),
                vendor["risk"]["score"],
                vendor["risk"]["tier"],
                encode(vendor["risk"].get("signals", [])),
                encode(vendor.get("riskAnswers", {})),
                created_at,
                now,
            ),
        )
        conn.execute("DELETE FROM evidence WHERE vendor_id = ?", (vendor["id"],))
        conn.execute("DELETE FROM risk_issues WHERE vendor_id = ?", (vendor["id"],))
        conn.execute("DELETE FROM followups WHERE vendor_id = ?", (vendor["id"],))
        for index, evidence in enumerate(vendor["evidence"]):
            self.insert_evidence(conn, vendor["id"], evidence, index)
        for issue in vendor["riskIssues"]:
            self.insert_issue(conn, vendor["id"], issue)
        for followup in vendor["followups"]:
            self.insert_followup(conn, vendor["id"], followup)

    def insert_evidence(self, conn, vendor_id, evidence, index):
        conn.execute(
            """
            INSERT INTO evidence (
                id, vendor_id, requirement_id, name, evidence_type, required_type,
                reviewer_role, validity_period, auto_flag_rule, followup_sla, help_text,
                status, file_name, submitted_by, submitted_at, valid_until, notes,
                stored_path, ai_review_json, decision_reason, sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence["id"],
                vendor_id,
                evidence.get("requirementId", evidence["id"]),
                evidence["name"],
                evidence["evidenceType"],
                evidence["requiredType"],
                evidence["reviewerRole"],
                evidence["validityPeriod"],
                evidence["autoFlagRule"],
                evidence["followupSla"],
                evidence["helpText"],
                evidence["status"],
                evidence.get("fileName"),
                evidence.get("submittedBy"),
                evidence.get("submittedAt"),
                evidence.get("validUntil"),
                evidence.get("notes", ""),
                evidence.get("storedPath"),
                encode(evidence.get("aiReview")) if evidence.get("aiReview") else None,
                evidence.get("decisionReason", ""),
                index,
            ),
        )

    def insert_issue(self, conn, vendor_id, issue):
        conn.execute(
            """
            INSERT INTO risk_issues (
                id, vendor_id, title, linked_evidence_id, severity, owner, due_date,
                status, recommendation, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                issue["id"],
                vendor_id,
                issue["title"],
                issue.get("linkedEvidenceId"),
                issue["severity"],
                issue["owner"],
                issue["dueDate"],
                issue["status"],
                issue["recommendation"],
                issue.get("createdAt", datetime.now().isoformat(timespec="seconds")),
            ),
        )

    def insert_followup(self, conn, vendor_id, followup):
        conn.execute(
            """
            INSERT INTO followups (id, vendor_id, issue_id, owner, due_date, status, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                followup["id"],
                vendor_id,
                followup.get("issueId"),
                followup["owner"],
                followup["dueDate"],
                followup["status"],
                followup["message"],
                followup.get("createdAt", datetime.now().isoformat(timespec="seconds")),
            ),
        )

    def insert_audit(self, conn, entry):
        conn.execute(
            """
            INSERT OR REPLACE INTO audit_logs (id, time, actor, action, vendor_id, target, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["id"],
                entry["time"],
                entry["actor"],
                entry["action"],
                entry.get("vendorId"),
                entry.get("target"),
                encode(entry.get("metadata", {})),
            ),
        )

    def template_from_row(self, row):
        return {
            "id": row["id"],
            "name": row["name"],
            "riskTier": row["risk_tier"],
            "description": row["description"],
            "requirements": decode(row["requirements_json"], []),
        }

    def user_from_row(self, row):
        return {
            "id": row["id"],
            "name": row["name"],
            "role": row["role"],
            "email": row["email"],
        }

    def vendor_from_row(self, conn, row):
        vendor = {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "owner": row["owner"],
            "reviewer": row["reviewer"],
            "stage": row["stage"],
            "dueDate": row["due_date"],
            "riskAnswers": decode(row["risk_answers_json"], {}),
            "risk": {
                "score": row["risk_score"],
                "tier": row["risk_tier"],
                "signals": decode(row["risk_signals_json"], []),
            },
            "templateId": row["template_id"],
            "templateName": row["template_name"],
            "evidence": [
                self.evidence_from_row(item)
                for item in conn.execute("SELECT * FROM evidence WHERE vendor_id = ? ORDER BY sort_order", (row["id"],))
            ],
            "riskIssues": [
                self.issue_from_row(item)
                for item in conn.execute("SELECT * FROM risk_issues WHERE vendor_id = ? ORDER BY created_at", (row["id"],))
            ],
            "followups": [
                self.followup_from_row(item)
                for item in conn.execute("SELECT * FROM followups WHERE vendor_id = ? ORDER BY created_at", (row["id"],))
            ],
            "overallDecision": row["overall_decision"],
            "status": row["status"],
            "progress": row["progress"],
        }
        return vendor

    def evidence_from_row(self, row):
        return {
            "id": row["id"],
            "requirementId": row["requirement_id"],
            "name": row["name"],
            "evidenceType": row["evidence_type"],
            "requiredType": row["required_type"],
            "reviewerRole": row["reviewer_role"],
            "validityPeriod": row["validity_period"],
            "autoFlagRule": row["auto_flag_rule"],
            "followupSla": row["followup_sla"],
            "helpText": row["help_text"],
            "status": row["status"],
            "fileName": row["file_name"],
            "submittedBy": row["submitted_by"],
            "submittedAt": row["submitted_at"],
            "validUntil": row["valid_until"],
            "notes": row["notes"],
            "storedPath": row["stored_path"],
            "aiReview": decode(row["ai_review_json"], None),
            "decisionReason": row["decision_reason"],
        }

    def issue_from_row(self, row):
        return {
            "id": row["id"],
            "title": row["title"],
            "linkedEvidenceId": row["linked_evidence_id"],
            "severity": row["severity"],
            "owner": row["owner"],
            "dueDate": row["due_date"],
            "status": row["status"],
            "recommendation": row["recommendation"],
            "createdAt": row["created_at"],
        }

    def followup_from_row(self, row):
        return {
            "id": row["id"],
            "issueId": row["issue_id"],
            "owner": row["owner"],
            "dueDate": row["due_date"],
            "status": row["status"],
            "message": row["message"],
            "createdAt": row["created_at"],
        }

    def audit_from_row(self, row):
        return {
            "id": row["id"],
            "time": row["time"],
            "actor": row["actor"],
            "action": row["action"],
            "vendorId": row["vendor_id"],
            "target": row["target"],
            "metadata": decode(row["metadata_json"], {}),
        }
