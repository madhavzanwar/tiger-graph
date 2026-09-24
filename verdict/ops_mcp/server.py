"""verdict-ops MCP server: the only path to side effects.

Where tigergraph-mcp gives an agent *read* access to the graph, this server exposes the fraud-operations tools:
open/inspect a case, record findings, request controlled evidence, propose actions and execute actions - every
execution passes the policy gate (policy.yaml): AUTO-route actions run against the mock bank, anything else is
queued as PENDING_APPROVAL for a human. Usable from any MCP client (e.g. Claude Desktop) alongside tigergraph-mcp.

    verdict ops-mcp          # stdio
"""
from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from verdict.memory.case_store import CaseStore
from verdict.ops_mcp import mock_bank
from verdict.policy.engine import PolicyEngine

server = MCPServer(name="verdict-ops", title="VERDICT fraud operations",
                   instructions="Case management and policy-gated actions for fraud investigations. Read graph evidence with "
                                "tigergraph-mcp; use these tools to record the case and act. You cannot bypass approval routes.")
_policy = PolicyEngine()
_store: CaseStore | None = None


def store() -> CaseStore:
    global _store
    if _store is None:
        _store = CaseStore()
    return _store


@server.tool(description="List the bank's policy action catalogue with approval routes.")
def policy_actions() -> str:
    return json.dumps({k: {"route": v["route"], "class": v.get("class")} for k, v in _policy.catalogue.items()})


@server.tool(description="Open (or re-open) a fraud case linked to a trigger transaction, card and customer.")
def open_case(case_id: str, trigger_type: str, txn_id: str, card_id: str, customer_id: str, opened_at: str) -> str:
    store().open_case(case_id, "MCP", trigger_type, opened_at, {"txn_id": txn_id, "card_id": card_id, "customer_id": customer_id})
    return json.dumps({"ok": True, "case_id": case_id})


@server.tool(description="Record an investigation finding on a case, with the evidence it is based on.")
def add_finding(case_id: str, finding: str, based_on: list[str], log_odds: float = 0.0) -> str:
    ids = store().add_evidence(case_id, [{"key": finding[:40], "label": finding, "value": ",".join(based_on),
                                          "contribution": log_odds, "source": "mcp:add_finding", "kind": "finding"}], "MCP")
    return json.dumps({"ok": True, "evidence_ids": ids})


@server.tool(description="Request controlled evidence: STEP_UP_AUTH, CUSTOMER_VALIDATION or ANALYST_INFO.")
def request_evidence(case_id: str, kind: str, reason: str) -> str:
    action = _policy.evidence_action_for(kind)
    if not action:
        return json.dumps({"ok": False, "error": f"{kind} is not an approved evidence channel"})
    rid = store().add_request(case_id, kind, reason)
    return json.dumps({"ok": True, "request_id": rid, "receipt": mock_bank.execute(action, case_id, {"kind": kind})})


@server.tool(description="Propose and (if permitted) execute a policy action. AUTO-route actions execute; others are queued for "
                         "human approval; forbidden actions are refused with the policy clause.")
def take_action(case_id: str, code: str, rationale: str, amount_at_risk: float = 0.0, wider_compromise: bool = False,
                undocumented_pattern: bool = False) -> str:
    facts = {"amount_at_risk": amount_at_risk, "wider_compromise": wider_compromise, "undocumented_pattern": undocumented_pattern}
    if code not in _policy.catalogue:
        return json.dumps({"ok": False, "error": "unknown action", "allowed": list(_policy.catalogue)})
    fb = _policy.is_forbidden(code, facts)
    if fb:
        return json.dumps({"ok": False, "status": "FORBIDDEN", "clause": fb["id"], "reason": f"forbidden unless {fb['unless']}"})
    route = _policy.route(code, facts)
    status = "EXECUTED" if route == "AUTO" else "PENDING_APPROVAL"
    store().add_actions(case_id, [{"code": code, "route": route, "status": status, "rationale": rationale, "clauses": ["MCP"]}], "MCP")
    out = {"ok": True, "action": code, "route": route, "status": status}
    if status == "EXECUTED":
        out["receipt"] = mock_bank.execute(code, case_id)
    return json.dumps(out)


@server.tool(description="Fetch the stored case record (evidence, requests, actions, linked entities, similar cases).")
def get_case(case_id: str) -> str:
    return json.dumps(store().record(case_id), default=str)[:20000]


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
