"""Simulated bank systems (card controls, customer messaging, step-up, CRM, SAR filing).

The brief allows actions to be simulated. Every call returns a receipt that is written to the case audit log.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

SYSTEMS = {
    "ALLOW_TRANSACTION": "authorisation-switch", "DECLINE_TRANSACTION": "authorisation-switch",
    "BLOCK_CARD": "card-controls", "BLOCK_ALL_CARDS": "card-controls", "MONITOR_CARD": "monitoring",
    "MONITOR_ACCOUNT": "monitoring", "WARN_CUSTOMER": "customer-messaging", "CONTACT_CUSTOMER": "customer-messaging",
    "STEP_UP_AUTH": "auth-service", "REQUEST_ANALYST_INFO": "case-management", "CREATE_CASE": "case-management",
    "ESCALATE_TO_ANALYST": "case-management", "FILE_REPORT": "regulatory-filing", "CLOSE_NO_FRAUD": "case-management",
}


def execute(code: str, case_id: str, detail: dict | None = None) -> dict:
    now_utc = datetime.now(timezone.utc)
    ref = hashlib.sha1(f"{code}|{case_id}|{now_utc.isoformat()}".encode()).hexdigest()[:10].upper()
    return {"action": code, "system": SYSTEMS.get(code, "mock"), "status": "EXECUTED", "reference": f"MOCK-{ref}",
            "executed_at": now_utc.strftime("%Y-%m-%d %H:%M:%S"), "detail": detail or {}}
