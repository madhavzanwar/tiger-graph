"""Export a read-only replay of completed investigations for static hosting (e.g. Vercel).

The live agent needs TigerGraph, the MCP server and a long-running API, which serverless hosting cannot provide.
This writes the case queue, every stored answer file, the evidence model / scoreboard and the policy to
``ui/public/demo/`` so the analyst console can be browsed as a replay. The dataset label is taken from the data
directory the answers were produced from, so the hosted page always states which data it shows.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import yaml

from verdict.calibrate.calibration import MODEL_PATH
from verdict.config import ROOT, settings
from verdict.memory.discover import load_discovered
from verdict.scoring.features import SIGNALS

DATASET_LABELS = {"hhgoa": "HHGOA_IEEE (official hackathon dataset)", "synthetic": "HHGOA-format sample dataset"}


def export(out: Path | None = None) -> dict:
    out = Path(out or ROOT / "ui" / "public" / "demo")
    if out.exists():
        shutil.rmtree(out)
    (out / "cases").mkdir(parents=True)
    ans_dir = settings.answers_dir
    pack = pd.read_csv(settings.work_dir / "prepared" / "case_pack.csv", dtype=str).fillna("")
    rows = []
    for _, r in pack.iterrows():
        p = ans_dir / f"{r['case_id']}.json"
        row = {**r.to_dict(), "status": "NEW"}
        if p.exists():
            a = json.loads(p.read_text())
            nb = a["next_best_action"]
            row.update(status=a["case"]["status"], p_before=nb["before_evidence"]["p_fraud"], decision_before=nb["before_evidence"]["decision"],
                       p_after=nb["after_evidence"]["p_fraud"], decision_after=nb["after_evidence"]["decision"],
                       pattern=a["case"]["fraud_pattern"]["display"])
            (out / "cases" / f"{r['case_id']}.json").write_text(json.dumps({"case_id": r["case_id"], "status": row["status"],
                                                                            "answer": a, "from_file": True}))
        rows.append(row)
    (out / "cases.json").write_text(json.dumps(rows))
    m = json.loads(MODEL_PATH.read_text())
    model = {"backtest": m.get("backtest"), "n_cases": m.get("n_cases", 0), "base_rate": m.get("base_rate", 0.5),
             "weights": [{"signal": k, "weight": round(v, 3), "label": SIGNALS.get(k, ("", "bank model risk score (logit)"))[1],
                          **m.get("stats", {}).get(k, {})} for k, v in m.get("weights", {}).items()],
             "evidence_likelihoods": m.get("evidence_likelihoods"), "patterns": m.get("patterns", {}).get("counts", {}),
             "discovered": load_discovered(), "learned_from": m.get("learned_from", []), "learn_log": []}
    (out / "model.json").write_text(json.dumps(model))
    (out / "policy.json").write_text(json.dumps(yaml.safe_load(settings.policy_file.read_text())))
    label = DATASET_LABELS.get(settings.data_dir.name, settings.data_dir.name)
    health = {"ok": True, "replay": True, "llm": False, "model": "replay", "graph_access": "mcp", "graph": settings.tg_graph,
              "dataset": label, "synthetic": False}
    (out / "health.json").write_text(json.dumps(health))
    return {"cases": len(rows), "answers": sum(1 for r in rows if r["status"] != "NEW"), "dataset": label, "out": str(out)}


if __name__ == "__main__":
    print(export())
