RISK_WEIGHTS = {
    "pii": 3,
    "financial": 3,
    "storesData": 2,
    "api": 2,
    "critical": 2,
    "ai": 2,
    "subprocessors": 1,
    "unknownSubprocessors": 1,
}


def calculate_risk(answers):
    score = sum(weight for key, weight in RISK_WEIGHTS.items() if answers.get(key))
    if score >= 8:
        tier = "High"
    elif score >= 4:
        tier = "Medium"
    else:
        tier = "Low"

    signals = [
        label
        for key, label in {
            "pii": "Customer PII access",
            "financial": "Financial/payment data",
            "storesData": "Stores customer/company data",
            "api": "API or webhook integration",
            "critical": "Business-critical workflow",
            "ai": "AI on customer/company data",
            "subprocessors": "Uses subprocessors",
            "unknownSubprocessors": "Unknown subprocessors",
        }.items()
        if answers.get(key)
    ]
    return {"score": score, "tier": tier, "signals": signals}
