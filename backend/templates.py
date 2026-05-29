from copy import deepcopy


def requirement(name, evidence_type, required_type, reviewer_role, validity):
    key = name.lower().replace("/", "").replace(" ", "-")
    return {
        "id": key,
        "name": name,
        "evidenceType": evidence_type,
        "requiredType": required_type,
        "reviewerRole": reviewer_role,
        "validityPeriod": validity,
        "autoFlagRule": f"Flag if {name.lower()} is expired, missing, unclear, or risky.",
        "followupSla": "5 business days",
        "helpText": f"Upload the latest {name.lower()} for reviewer validation.",
    }


DEFAULT_TEMPLATES = [
    {
        "id": "tpl-low",
        "name": "Low-Risk Vendor Review",
        "riskTier": "Low",
        "description": "For vendors with no sensitive data or system access.",
        "requirements": [
            requirement("Company Registration", "Document", "Required", "Ops", "12 months"),
            requirement("GST Details", "Document", "Required", "Finance", "12 months"),
            requirement("Bank Details", "Document", "Required", "Finance", "12 months"),
            requirement("Basic Agreement", "Contract", "Required", "Legal", "Contract duration"),
        ],
    },
    {
        "id": "tpl-medium",
        "name": "Medium-Risk SaaS Vendor Review",
        "riskTier": "Medium",
        "description": "For SaaS vendors with limited data or system access.",
        "requirements": [
            requirement("SOC 2 Report", "PDF", "Required", "Security", "12 months"),
            requirement("DPA", "Contract", "Required", "Legal", "Contract duration"),
            requirement("Access Control Policy", "Document", "Required", "Security", "12 months"),
            requirement("Subprocessor List", "Document", "Required", "Legal/Security", "6 months"),
            requirement("Data Retention Policy", "Document", "Required", "Legal", "12 months"),
        ],
    },
    {
        "id": "tpl-high-ai",
        "name": "High-Risk AI SaaS Vendor Review",
        "riskTier": "High",
        "description": "For vendors touching customer data, AI workflows, APIs, or critical systems.",
        "requirements": [
            requirement("SOC 2 or ISO 27001", "PDF", "Required", "Security", "12 months"),
            requirement("DPA", "Contract", "Required", "Legal", "Contract duration"),
            requirement("Subprocessor List", "Document", "Required", "Legal/Security", "6 months"),
            requirement("Pen-test Summary", "PDF", "Required", "Security", "12 months"),
            requirement("MFA/RBAC Screenshot", "Screenshot", "Required", "Security", "6 months"),
            requirement("Encryption Policy", "Document", "Required", "Security", "12 months"),
            requirement("Incident Response Policy", "Document", "Required", "Security", "12 months"),
            requirement("AI Data Usage Policy", "Document", "Conditional", "Legal/Security", "12 months"),
        ],
    },
]


def list_templates():
    return deepcopy(DEFAULT_TEMPLATES)


def recommend_template(risk_tier, uses_ai=False):
    if risk_tier == "High":
        return "tpl-high-ai"
    if risk_tier == "Medium":
        return "tpl-medium"
    return "tpl-low"


def get_template(template_id):
    for template in DEFAULT_TEMPLATES:
        if template["id"] == template_id:
            return deepcopy(template)
    raise KeyError(f"Unknown template {template_id}")
