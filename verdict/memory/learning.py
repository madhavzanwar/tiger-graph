"""Learning loop: resolved cases update the evidence model.

When an analyst resolves a case (confirmed fraud / cleared), its signal vector is appended to the feature store,
the calibrated model is refitted (with bootstrap uncertainty), FeatureStat vertices are refreshed in TigerGraph and
the running agent reloads the model. The weight deltas are returned so the UI can show what the agent learned.
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from verdict.calibrate.calibration import FEATURES_PATH, MODEL_PATH, evidence_likelihoods, fit, pattern_model
from verdict.scoring.features import SIGNAL_NAMES


def resolve(state: dict, signals: dict, outcome: str, analyst: str = "analyst", pattern: str | None = None,
            store=None) -> dict:
    df = pd.read_parquet(FEATURES_PATH)
    old = json.loads(MODEL_PATH.read_text())
    ev = state.get("responses", {})
    kind, resp = (next(iter(ev.items())) if ev else ("", ""))
    row = {"case_id": state["case_id"], "outcome": outcome, "pattern": pattern or state["assessments"][-1]["pattern"],
           "opened_at": state["trigger"].get("trigger_time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
           "evidence_requested": kind, "evidence_result": resp,
           "actions_taken": ";".join(x["code"] for x in state["nba_after_evidence"]["actions"]), "sar_filed": "",
           "amount": float(state["trigger"].get("amount") or 0), **{k: float(signals.get(k, 0)) for k in SIGNAL_NAMES},
           "risk_score": float(signals.get("risk_score", 0))}
    df = pd.concat([df[df["case_id"] != state["case_id"]], pd.DataFrame([row])], ignore_index=True)
    df.to_parquet(FEATURES_PATH, index=False)
    model = fit(df, n_boot=100)
    model["patterns"] = pattern_model(df) or old.get("patterns", {})
    model["evidence_likelihoods"] = evidence_likelihoods(df) or old.get("evidence_likelihoods", {})
    model["backtest"] = old.get("backtest", {})
    model["learned_from"] = old.get("learned_from", []) + [{"case_id": state["case_id"], "outcome": outcome, "by": analyst,
                                                            "at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}]
    MODEL_PATH.write_text(json.dumps(model, indent=1))
    active = [k for k in SIGNAL_NAMES if signals.get(k)]
    deltas = sorted(({"signal": k, "before": round(old["weights"].get(k, 0), 3), "after": round(model["weights"][k], 3),
                      "delta": round(model["weights"][k] - old["weights"].get(k, 0), 3)} for k in active),
                    key=lambda d: -abs(d["delta"]))
    if store is not None:
        store.update_case(state["case_id"], outcome=outcome, status="CLOSED")
        c = store.c
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        c.upsertVertices("FeatureStat", [(k, {"n_fraud_pos": v["n_fraud_pos"], "n_fraud": v["n_fraud"], "n_clear_pos": v["n_clear_pos"],
                                               "n_clear": v["n_clear"], "updated_at": now}) for k, v in model["stats"].items()])
    return {"case_id": state["case_id"], "outcome": outcome, "n_cases": model["n_cases"], "weight_deltas": deltas}


def publish_feature_stats() -> int:
    from verdict.tg.client import conn

    m = json.loads(MODEL_PATH.read_text())
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn("ops").upsertVertices("FeatureStat", [(k, {**v, "updated_at": now}) for k, v in m["stats"].items()])
    return len(m["stats"])
