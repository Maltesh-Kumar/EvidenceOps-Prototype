from datetime import datetime


def add_audit(db, actor, action, vendor_id=None, target=None, metadata=None):
    entry = {
        "id": f"audit-{len(db['audit']) + 1}",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "actor": actor,
        "action": action,
        "vendorId": vendor_id,
        "target": target,
        "metadata": metadata or {},
    }
    db["audit"].insert(0, entry)
    return entry
