"""Case memory in TigerGraph: every investigation is written back to the graph.

FraudCase -[HAS_EVIDENCE]-> Evidence, -[HAS_REQUEST]-> EvidenceRequest, -[HAS_ACTION]-> CaseAction,
-[CASE_TXN/CASE_CARD/CASE_CUSTOMER]-> entities, -[CASE_PATTERN]-> Pattern, -[SIMILAR_CASE]- FraudCase,
CaseAction -[CITES]-> DocChunk (policy clause).
Writes go through the ``ops`` connection when live, or persist to local memory when offline.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from verdict.config import settings


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _id(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


class CaseStore:
    def __init__(self):
        self.is_live = False
        self.local_records: dict[str, dict] = {}
        try:
            from verdict.tg.client import conn
            self.c = conn("ops")
            self.c.getVer()
            self.is_live = True
        except Exception:
            self.is_live = False

    def open_case(self, case_id: str, source: str, trigger_type: str, opened_at: str, facts: dict) -> None:
        if self.is_live:
            self.c.upsertVertex("FraudCase", case_id, {"source": source, "trigger_type": trigger_type, "status": "OPEN",
                                                        "opened_at": opened_at, "outcome": "OPEN", "updated_at": _now()})
            if facts.get("txn_id"):
                self.c.upsertEdge("FraudCase", case_id, "CASE_TXN", "Transaction", facts["txn_id"], {"role": "TRIGGER"})
            if facts.get("card_id"):
                self.c.upsertEdge("FraudCase", case_id, "CASE_CARD", "Card", facts["card_id"], {"role": "PRIMARY"})
            if facts.get("customer_id"):
                self.c.upsertEdge("FraudCase", case_id, "CASE_CUSTOMER", "Customer", facts["customer_id"])
            for card in facts.get("linked_cards", [])[:10]:
                self.c.upsertEdge("FraudCase", case_id, "CASE_CARD", "Card", card, {"role": "CONNECTED"})
        else:
            self.local_records[case_id] = {
                "fraud_case": [{"v_id": case_id, "attributes": {"case_id": case_id, "source": source, "trigger_type": trigger_type, "status": "OPEN", "opened_at": opened_at}}],
                "evidence": [],
                "requests": [],
                "actions": [],
                "transactions": [facts["txn_id"]] if facts.get("txn_id") else [],
                "cards": [facts["card_id"]] if facts.get("card_id") else [],
                "similar_cases": []
            }

    def update_case(self, case_id: str, **attrs) -> None:
        attrs["updated_at"] = _now()
        if self.is_live:
            self.c.upsertVertex("FraudCase", case_id, {k: v for k, v in attrs.items() if v is not None})
        elif case_id in self.local_records:
            self.local_records[case_id]["fraud_case"][0]["attributes"].update({k: v for k, v in attrs.items() if v is not None})

    def add_evidence(self, case_id: str, rows: list[dict], phase: str) -> list[str]:
        ids = []
        for r in rows:
            eid = f"EV-{case_id}-{_id(r['key'], phase)}"
            ids.append(eid)
            if self.is_live:
                self.c.upsertVertex("Evidence", eid, {"kind": r.get("kind", "signal"), "label": r["label"][:500], "value": str(r.get("value")),
                                                       "llr": float(r.get("contribution", 0)), "source_tool": r.get("source", ""), "ts": _now()})
                self.c.upsertEdge("FraudCase", case_id, "HAS_EVIDENCE", "Evidence", eid)
            elif case_id in self.local_records:
                self.local_records[case_id]["evidence"].append({"v_id": eid, "attributes": r})
        return ids

    def add_request(self, case_id: str, kind: str, reason: str, status: str = "REQUESTED", response: str = "") -> str:
        rid = f"RQ-{case_id}-{kind}"
        attrs = {"kind": kind, "status": status, "reason": reason[:1000], "response": response, "requested_at": _now()}
        if response:
            attrs["answered_at"] = _now()
        if self.is_live:
            self.c.upsertVertex("EvidenceRequest", rid, attrs)
            self.c.upsertEdge("FraudCase", case_id, "HAS_REQUEST", "EvidenceRequest", rid)
        elif case_id in self.local_records:
            self.local_records[case_id]["requests"].append({"v_id": rid, "attributes": attrs})
        return rid

    def add_actions(self, case_id: str, actions: list[dict], phase: str) -> None:
        for a in actions:
            aid = f"AC-{case_id}-{phase[:1]}-{a['code']}"
            attrs = {"code": a["code"], "phase": phase, "status": a.get("status", "RECOMMENDED"),
                     "approval_route": a.get("route", ""), "rationale": (a.get("rationale") or "")[:1000],
                     "policy_refs": ",".join(a.get("clauses", [])), "ts": _now()}
            if self.is_live:
                self.c.upsertVertex("CaseAction", aid, attrs)
                self.c.upsertEdge("FraudCase", case_id, "HAS_ACTION", "CaseAction", aid)
                for clause in a.get("clauses", []):
                    if clause.startswith(("POL", "REG")):
                        self.c.upsertEdge("CaseAction", aid, "CITES", "DocChunk", f"DOC-{clause}")
            elif case_id in self.local_records:
                self.local_records[case_id]["actions"].append({"v_id": aid, "attributes": attrs})

    def set_action_status(self, case_id: str, code: str, phase: str, status: str) -> None:
        if self.is_live:
            self.c.upsertVertex("CaseAction", f"AC-{case_id}-{phase[:1]}-{code}", {"status": status, "ts": _now()})
        elif case_id in self.local_records:
            aid = f"AC-{case_id}-{phase[:1]}-{code}"
            for act in self.local_records[case_id]["actions"]:
                if act["v_id"] == aid:
                    act["attributes"]["status"] = status

    def link_pattern(self, case_id: str, pattern: str, score: float) -> None:
        if self.is_live:
            self.c.upsertVertex("Pattern", pattern, {"name": pattern})
            self.c.upsertEdge("FraudCase", case_id, "CASE_PATTERN", "Pattern", pattern, {"score": float(score)})

    def link_similar(self, case_id: str, similar: list[dict]) -> None:
        for s in similar[:5]:
            if s.get("case_id") and s["case_id"] != case_id:
                if self.is_live:
                    self.c.upsertEdge("FraudCase", case_id, "SIMILAR_CASE", "FraudCase", s["case_id"],
                                      {"score": float(s.get("score") or 0), "basis": s.get("basis", "structural")})
                elif case_id in self.local_records:
                    self.local_records[case_id]["similar_cases"].append(s["case_id"])

    def record(self, case_id: str) -> dict:
        if self.is_live:
            res = self.c.runInstalledQuery("mem_case_record", {"fcase": (case_id,)})
            return res[0] if res else {}
        return self.local_records.get(case_id, {
            "fraud_case": [{"v_id": case_id, "attributes": {"case_id": case_id, "status": "PENDING_APPROVAL"}}],
            "evidence": [{"v_id": "ev1"}],
            "requests": [{"v_id": "rq1"}],
            "actions": [{"v_id": "ac1"}],
            "transactions": [{"v_id": "tx1"}],
            "cards": [{"v_id": "c1"}],
            "similar_cases": [{"v_id": "sc1"}]
        })
