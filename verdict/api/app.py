"""VERDICT API: case queue, live investigation stream (SSE), evidence responses, approvals, learning, scoreboard."""
from __future__ import annotations

import asyncio
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from verdict.agent.orchestrator import Investigation, Shared, simulate_response
from verdict.calibrate.calibration import MODEL_PATH
from verdict.config import ROOT, settings
from verdict.outputs import answer_writer
from verdict.outputs.benchmark import graph_check, load_oracle

app = FastAPI(title="VERDICT", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATE: dict = {"shared": None, "inv": {}, "events": {}, "lock": threading.Lock(), "learn_log": []}


def shared() -> Shared:
    if STATE["shared"] is None:
        STATE["shared"] = Shared.create()
    return STATE["shared"]


def pack() -> pd.DataFrame:
    return pd.read_csv(settings.work_dir / "prepared" / "case_pack.csv", dtype=str).fillna("")


def _emit(case_id: str):
    buf = STATE["events"].setdefault(case_id, [])
    return lambda ev: buf.append(ev)


def _clean_obj(obj):
    import math
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    elif isinstance(obj, dict):
        return {k: _clean_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_obj(v) for v in obj]
    return obj


def _answer(case_id: str) -> dict | None:
    p = settings.answers_dir / f"{case_id}.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return _clean_obj(data)
    except Exception:
        return None


def _bg(fn, *a):
    def run():
        with STATE["lock"]:
            try:
                fn(*a)
            except Exception as e:  # noqa: BLE001
                cid = a[0] if a and isinstance(a[0], str) else "?"
                STATE["events"].setdefault(cid, []).append({"case_id": cid, "ts": datetime.utcnow().isoformat(), "phase": "ERROR",
                                                            "type": "error", "title": str(e)[:500], "data": {}})
    threading.Thread(target=run, daemon=True).start()


def _finish_if_ready(inv: Investigation) -> None:
    if inv.s["status"] == "AWAITING_EVIDENCE":
        return
    inv.finalize()
    answer_writer.write(inv.s, graph_check=graph_check(inv.sh, inv.case_id))
    STATE["events"][inv.case_id].append({"case_id": inv.case_id, "ts": datetime.utcnow().isoformat(), "phase": "DONE", "type": "done",
                                         "title": "Answer file written", "data": {}})


# ------------------------------------------------------------------- routes
@app.get("/api/health")
def health():
    sh = shared()
    return {"ok": True, "llm": sh.llm.enabled, "model": settings.model if sh.llm.enabled else "offline (deterministic templates)",
            "graph_access": sh.gateway.via, "data_dir": settings.data_dir.name, "graph": settings.tg_graph,
            "synthetic": settings.data_dir.name == "synthetic"}


@app.get("/api/cases")
def cases():
    out = []
    for _, r in pack().iterrows():
        cid = r["case_id"]
        row = {**r.to_dict(), "status": "NEW"}
        inv = STATE["inv"].get(cid)
        a = _answer(cid)
        if inv is not None:
            row["status"] = inv.s["status"]
            if inv.s.get("nba_before_evidence"):
                row["p_before"] = inv.s["nba_before_evidence"]["p_fraud"]
                row["decision_before"] = inv.s["nba_before_evidence"]["decision"]
                row["pattern"] = inv.s["nba_before_evidence"]["pattern"]
            if inv.s.get("nba_after_evidence"):
                row["p_after"] = inv.s["nba_after_evidence"]["p_fraud"]
                row["decision_after"] = inv.s["nba_after_evidence"]["decision"]
                row["pattern"] = inv.s["nba_after_evidence"]["pattern"]
        elif a:
            nb = a["next_best_action"]
            row.update(status=a["case"]["status"], p_before=nb["before_evidence"]["p_fraud"], decision_before=nb["before_evidence"]["decision"],
                       p_after=nb["after_evidence"]["p_fraud"], decision_after=nb["after_evidence"]["decision"],
                       pattern=a["case"]["fraud_pattern"]["display"])
        out.append(row)
    for cid, inv in STATE["inv"].items():
        if cid.startswith("LIVE-"):
            out.append({**inv.t, "status": inv.s["status"], "p_before": inv.s.get("nba_before_evidence", {}).get("p_fraud")})
    return out


class TriggerIn(BaseModel):
    trigger_type: str = "CUSTOMER_REPORT"
    trigger_txn_id: str
    detail: str = ""


@app.post("/api/triggers")
def new_trigger(t: TriggerIn):
    cid = f"LIVE-{uuid.uuid4().hex[:6].upper()}"
    trig = {"case_id": cid, "trigger_type": t.trigger_type, "trigger_txn_id": t.trigger_txn_id, "detail": t.detail,
            "trigger_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}
    return _start(cid, trig, source="LIVE")


@app.post("/api/cases/{case_id}/investigate")
def investigate(case_id: str):
    row = pack()[pack()["case_id"] == case_id]
    if row.empty:
        raise HTTPException(404, "unknown case")
    return _start(case_id, row.iloc[0].to_dict())


def _start(case_id: str, trig: dict, source: str = "BENCHMARK"):
    STATE["events"][case_id] = []
    inv = Investigation(trig, shared(), emit=_emit(case_id), source=source)
    STATE["inv"][case_id] = inv

    def go(cid):
        inv.run_to_decision()
        _finish_if_ready(inv)

    _bg(go, case_id)
    return {"case_id": case_id, "started": True}


@app.get("/api/cases/{case_id}/events")
async def events(case_id: str):
    async def gen():
        i = 0
        idle = 0
        while idle < 1800:
            buf = STATE["events"].get(case_id, [])
            if i < len(buf):
                for ev in buf[i:]:
                    yield {"event": "message", "data": json.dumps(ev, default=str)}
                i = len(buf)
                idle = 0
            else:
                idle += 1
                yield {"event": "ping", "data": "{}"} if idle % 30 == 0 else {"comment": "k"}
            await asyncio.sleep(0.2)

    return EventSourceResponse(gen())


@app.get("/api/cases/{case_id}")
def case(case_id: str):
    inv = STATE["inv"].get(case_id)
    if inv is not None:
        s = dict(inv.s)
        if s.get("nba_after_evidence"):
            s["answer"] = answer_writer.to_answer(inv.s)
        return json.loads(json.dumps(s, default=str))
    a = _answer(case_id)
    if a:
        return {"case_id": case_id, "status": a["case"]["status"], "answer": a, "from_file": True}
    raise HTTPException(404, "not investigated yet")


class EvidenceIn(BaseModel):
    kind: str
    response: str | None = None   # None -> use benchmark response if available, else simulate


@app.post("/api/cases/{case_id}/evidence")
def evidence(case_id: str, e: EvidenceIn):
    inv = STATE["inv"].get(case_id)
    if inv is None or inv.s["status"] != "AWAITING_EVIDENCE":
        raise HTTPException(409, "case is not awaiting evidence")
    resp = e.response or load_oracle().get(case_id, {}).get(e.kind) or simulate_response(inv, e.kind)

    def go(cid):
        inv.provide_evidence(e.kind, resp)
        pending = [r for r in inv.s["evidence_requests"] if r["status"] == "REQUESTED"]
        if pending:
            inv.s["status"] = "AWAITING_EVIDENCE"
            return
        if not inv.next_request():
            inv.s["status"] = "REASSESSED"
            _finish_if_ready(inv)

    _bg(go, case_id)
    return {"case_id": case_id, "kind": e.kind, "response": resp}


class ApprovalIn(BaseModel):
    code: str
    approved: bool = True
    approver: str = "analyst.demo"
    note: str = ""


@app.post("/api/cases/{case_id}/approve")
def approve(case_id: str, a: ApprovalIn):
    inv = STATE["inv"].get(case_id)
    if inv is None:
        raise HTTPException(404, "case not active in this session")
    inv.approve(a.code, a.approver, a.approved, a.note)
    answer_writer.write(inv.s, graph_check=graph_check(inv.sh, case_id))
    return {"status": inv.s["status"], "actions": inv.s["nba_after_evidence"]["actions"]}


class ResolveIn(BaseModel):
    outcome: str  # CONFIRMED_FRAUD | CLEARED
    analyst: str = "analyst.demo"


@app.post("/api/cases/{case_id}/resolve")
def resolve(case_id: str, r: ResolveIn):
    from verdict.memory.learning import resolve as learn
    from verdict.scoring.ledger import EvidenceModel

    inv = STATE["inv"].get(case_id)
    if inv is None or not inv.s.get("nba_after_evidence"):
        raise HTTPException(409, "investigate the case first")
    with STATE["lock"]:
        res = learn(inv.s, inv.signals, r.outcome, r.analyst, store=inv.sh.store)
        inv.sh.model = EvidenceModel()
    STATE["learn_log"].append(res)
    return res


@app.get("/api/model")
def model():
    m = json.loads(MODEL_PATH.read_text())
    from verdict.memory.discover import load_discovered
    from verdict.scoring.features import SIGNALS

    return {"backtest": m.get("backtest"), "n_cases": m.get("n_cases", 0), "base_rate": m.get("base_rate", 0.5),
            "weights": [{"signal": k, "weight": round(v, 3), "label": SIGNALS.get(k, ("", "bank model risk score (logit)"))[1],
                         **m.get("stats", {}).get(k, {})} for k, v in m.get("weights", {}).items()],
            "evidence_likelihoods": m.get("evidence_likelihoods"), "patterns": m.get("patterns", {}).get("counts", {}),
            "discovered": load_discovered(), "learned_from": m.get("learned_from", []), "learn_log": STATE["learn_log"]}


@app.get("/api/policy")
def policy():
    return yaml.safe_load(settings.policy_file.read_text())


# ------------------------------------------------------------------ static UI
UI = ROOT / "ui" / "dist"
if UI.exists():
    app.mount("/assets", StaticFiles(directory=UI / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = UI / path
        return FileResponse(f if path and f.exists() and f.is_file() else UI / "index.html")
