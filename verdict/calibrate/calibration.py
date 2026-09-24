"""Learn the evidence model from closed cases.

For every closed case we re-run the core graph queries *as of the case's trigger time* (queries only look at data
before t0, and the case itself is excluded), derive the signals, and fit:

  * a calibrated additive log-odds model  logit P(fraud) = b0 + w_risk*logit(risk_score) + sum_i w_i * signal_i
    (L2-regularised logistic regression; each w_i is the evidence weight shown in the ledger)
  * 200 bootstrap refits -> parameter uncertainty -> credible intervals and decision stability
  * per-signal counts P(signal | fraud), P(signal | cleared) (stored as FeatureStat vertices for explanation)
  * a pattern classifier over confirmed-fraud cases (labels from the history, incl. UNCLASSIFIED)
  * evidence-response likelihoods P(response | fraud / cleared) for each evidence request type (drives VOI)
  * a time-split backtest (fit on older cases, evaluate on the most recent month of history)
"""
from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from verdict.agent.graph_gateway import make_gateway
from verdict.config import settings
from verdict.scoring.features import SIGNAL_NAMES, collect_core, derive_signals

MODEL_PATH = settings.work_dir / "model.json"
FEATURES_PATH = settings.work_dir / "history_features.parquet"


def _logit(p: float) -> float:
    p = min(max(p, 0.01), 0.99)
    return math.log(p / (1 - p))


def history_features(workers: int = 8) -> pd.DataFrame:
    cases = pd.read_csv(settings.work_dir / "prepared" / "cases_history.csv", dtype=str).fillna("")
    cases = cases[cases["trigger_txn_id"] != ""]
    gw = make_gateway()

    def one(row):
        try:
            raw = collect_core(gw, row["trigger_txn_id"], parallel=False)
            s, f = derive_signals(raw, exclude_case_id=row["case_id"])
            return {"case_id": row["case_id"], "outcome": row["outcome"], "pattern": row["pattern"], "opened_at": row["opened_at"],
                    "evidence_requested": row["evidence_requested"], "evidence_result": row["evidence_result"],
                    "actions_taken": row["actions_taken"], "sar_filed": row["sar_filed"], "amount": f["amount"], **s}
        except Exception as e:  # noqa: BLE001
            return {"case_id": row["case_id"], "error": str(e)[:200]}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(one, [r for _, r in cases.iterrows()]))
    df = pd.DataFrame(rows)
    df = df[df.get("error").isna()] if "error" in df else df
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(FEATURES_PATH, index=False)
    return df


def _X(df: pd.DataFrame) -> np.ndarray:
    risk = df["risk_score"].astype(float).map(_logit).to_numpy()[:, None]
    return np.hstack([risk, df[SIGNAL_NAMES].astype(float).to_numpy()])


def fit(df: pd.DataFrame, C: float = 0.8, n_boot: int = 200, seed: int = 0) -> dict:
    y = (df["outcome"] == "CONFIRMED_FRAUD").astype(int).to_numpy()
    X = _X(df)
    lr = LogisticRegression(C=C, max_iter=2000).fit(X, y)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].min() == y[idx].max():
            continue
        b = LogisticRegression(C=C, max_iter=2000).fit(X[idx], y[idx])
        boots.append([float(b.intercept_[0])] + [float(v) for v in b.coef_[0]])
    names = ["risk_logit"] + SIGNAL_NAMES
    fr, cl = df[y == 1], df[y == 0]
    stats = {n: {"n_fraud_pos": int(fr[n].sum()), "n_fraud": int(len(fr)), "n_clear_pos": int(cl[n].sum()), "n_clear": int(len(cl))}
             for n in SIGNAL_NAMES}
    return {
        "intercept": float(lr.intercept_[0]),
        "weights": dict(zip(names, [float(v) for v in lr.coef_[0]])),
        "boot": boots,
        "feature_names": names,
        "stats": stats,
        "n_cases": int(len(y)),
        "base_rate": float(y.mean()),
    }


def pattern_model(df: pd.DataFrame) -> dict:
    fr = df[(df["outcome"] == "CONFIRMED_FRAUD") & (df["pattern"] != "")]
    if fr["pattern"].nunique() < 2:
        return {}
    X = _X(fr)
    clf = LogisticRegression(C=1.0, max_iter=3000).fit(X, fr["pattern"])
    return {"classes": list(clf.classes_), "intercept": clf.intercept_.tolist(), "coef": clf.coef_.tolist(),
            "counts": fr["pattern"].value_counts().to_dict()}


def evidence_likelihoods(df: pd.DataFrame) -> dict:
    out: dict = {}
    for kind, g in df[df["evidence_requested"] != ""].groupby("evidence_requested"):
        res: dict = {}
        for outcome_label, gg in (("fraud", g[g["outcome"] == "CONFIRMED_FRAUD"]), ("legit", g[g["outcome"] != "CONFIRMED_FRAUD"])):
            vc = gg["evidence_result"].value_counts()
            cats = sorted(set(g["evidence_result"]) - {""})
            tot = len(gg) + len(cats)
            res[outcome_label] = {c: round((int(vc.get(c, 0)) + 1) / tot, 4) for c in cats}  # Laplace
        res["n"] = int(len(g))
        out[kind] = res
    return out


def backtest(df: pd.DataFrame) -> dict:
    df = df.sort_values("opened_at")
    cut = df["opened_at"].quantile(0.75) if False else df["opened_at"].iloc[int(len(df) * 0.75)]
    tr, te = df[df["opened_at"] < cut], df[df["opened_at"] >= cut]
    m = fit(tr, n_boot=0)
    w = np.array([m["weights"][n] for n in m["feature_names"]])
    p = 1 / (1 + np.exp(-(m["intercept"] + _X(te) @ w)))
    y = (te["outcome"] == "CONFIRMED_FRAUD").astype(int).to_numpy()
    p_risk = te["risk_score"].astype(float).to_numpy()
    res = {"train_cases": int(len(tr)), "test_cases": int(len(te)), "split_at": cut,
           "auc_model": round(float(roc_auc_score(y, p)), 4) if len(set(y)) > 1 else None,
           "auc_risk_score_only": round(float(roc_auc_score(y, p_risk)), 4) if len(set(y)) > 1 else None,
           "brier_model": round(float(brier_score_loss(y, p)), 4),
           "accuracy_at_0.5": round(float(((p >= 0.5) == y).mean()), 4)}
    # reliability diagram (5 bins)
    bins = np.linspace(0, 1, 6)
    rel = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if mask.sum():
            rel.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(mask.sum()), "predicted": round(float(p[mask].mean()), 3),
                        "observed": round(float(y[mask].mean()), 3)})
    res["reliability"] = rel
    pm = pattern_model(tr)
    if pm:
        fr = te[(te["outcome"] == "CONFIRMED_FRAUD") & (te["pattern"] != "")]
        if len(fr):
            Xf = _X(fr)
            logits = np.array(pm["intercept"]) + Xf @ np.array(pm["coef"]).T
            pred = [pm["classes"][i] for i in logits.argmax(1)]
            res["pattern_accuracy"] = round(float(np.mean(np.array(pred) == fr["pattern"].to_numpy())), 4)
            res["pattern_test_cases"] = int(len(fr))
            conf: dict = {}
            for a, b in zip(fr["pattern"], pred):
                conf.setdefault(a, {}).setdefault(b, 0)
                conf[a][b] += 1
            res["pattern_confusion"] = conf
    return res


def calibrate(recompute: bool = True) -> dict:
    df = history_features() if recompute or not FEATURES_PATH.exists() else pd.read_parquet(FEATURES_PATH)
    model = fit(df)
    model["patterns"] = pattern_model(df)
    model["evidence_likelihoods"] = evidence_likelihoods(df)
    model["backtest"] = backtest(df)
    MODEL_PATH.write_text(json.dumps(model, indent=1))
    return {"n_cases": model["n_cases"], "base_rate": round(model["base_rate"], 3), "backtest": model["backtest"],
            "evidence_likelihoods": model["evidence_likelihoods"]}


if __name__ == "__main__":
    print(json.dumps(calibrate(), indent=1, default=str))
