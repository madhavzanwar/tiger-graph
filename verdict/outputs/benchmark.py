"""Run the benchmark case pack end-to-end and write answer files."""
from __future__ import annotations

import time

import pandas as pd

from verdict.agent.orchestrator import Shared, run_case
from verdict.config import settings
from verdict.outputs import answer_writer


def load_oracle() -> dict:
    """Evidence responses for benchmark cases, if the dataset provides them (column names are flexible)."""
    p = settings.data_dir / "evidence_responses.csv"
    if not p.exists():
        return {}
    df = pd.read_csv(p, dtype=str).fillna("")
    out = {}
    for _, r in df.iterrows():
        out[r["case_id"]] = {"CUSTOMER_VALIDATION": r.get("customer_validation_response", ""), "STEP_UP_AUTH": r.get("step_up_response", ""),
                             "ANALYST_INFO": r.get("analyst_response", "")}
    return out


def graph_check(shared: Shared, case_id: str) -> dict:
    if not shared.store:
        return {}
    rec = shared.store.record(case_id)
    fc = (rec.get("fraud_case") or [{}])[0]
    return {"vertex": f"FraudCase/{case_id}", "status": fc.get("attributes", {}).get("status"),
            "evidence_vertices": len(rec.get("evidence", [])), "evidence_requests": len(rec.get("requests", [])),
            "action_vertices": len(rec.get("actions", [])), "linked_transactions": len(rec.get("transactions", [])),
            "linked_cards": len(rec.get("cards", [])), "similar_case_edges": len(rec.get("similar_cases", [])), "verified": bool(fc)}


def run(case_ids: list[str] | None = None, shared: Shared | None = None) -> list[dict]:
    shared = shared or Shared.create()
    pack = pd.read_csv(settings.work_dir / "prepared" / "case_pack.csv", dtype=str).fillna("")
    oracle = load_oracle()
    rows = []
    for _, r in pack.iterrows():
        if case_ids and r["case_id"] not in case_ids:
            continue
        t = time.time()
        s = run_case(r.to_dict(), shared, oracle=oracle.get(r["case_id"]))
        answer_writer.write(s, graph_check=graph_check(shared, r["case_id"]))
        b, a = s["nba_before_evidence"], s["nba_after_evidence"]
        rows.append({"case": r["case_id"], "trigger": r["trigger_type"], "pattern": a["pattern"], "p_before": round(b["p_fraud"], 3),
                     "nba_before": b["decision"], "evidence": ", ".join(f"{q['kind']}={q.get('response')}" for q in s["evidence_requests"]) or "-",
                     "p_after": round(a["p_fraud"], 3), "nba_after": a["decision"],
                     "actions_after": ", ".join(f"{x['code']}[{x['route']}]" for x in a["actions"]), "sar": "Y" if a["sar_required"] else "N",
                     "status": s["status"], "secs": round(time.time() - t, 1)})
        print(" | ".join(str(v) for v in rows[-1].values()), flush=True)
    answer_writer.summary(rows)
    return rows
