"""Undocumented-pattern discovery.

The brief warns that not every fraud pattern in the data is documented. We look for them explicitly:

1. take confirmed-fraud closed cases whose documented-pattern signatures are weak (the residual) plus any cases the
   analysts labelled UNCLASSIFIED/OTHER;
2. cluster their graph-derived signal vectors (k-means, k chosen by silhouette);
3. describe each cluster by the signals with the highest lift versus all fraud cases;
4. name it (Claude when available, otherwise a rule-based name from the top signals) and store it in TigerGraph as
   ``Pattern{status: HYPOTHESIS}`` linked to its example cases.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from verdict.config import settings
from verdict.scoring.features import SIGNAL_NAMES, SIGNALS

OUT = settings.work_dir / "discovered_patterns.json"
SIGNATURES = {
    "CARD_TESTING": ["ct_small_burst", "ct_large_after_small"],
    "CNP_NEW_DEVICE": ["device_new_flag", "device_unseen", "proxy"],
    "CARD_NOT_PRESENT_NEW_DEVICE": ["device_new_flag", "device_unseen", "proxy"],
    "CARD_NOT_PRESENT_FRAUD": ["device_new_flag", "device_unseen", "proxy"],
    "OUT_OF_REGION": ["region_novel_card_present", "concurrent_home_activity"],
    "OUT_OF_REGION_USE": ["region_novel_card_present", "concurrent_home_activity"],
    "ACCOUNT_TAKEOVER": ["match_fail", "email_changed", "mixed_channel_new_device"],
    "SHARED_ENTITY_RING": ["ring_linked_high_risk", "ring_linked_prior_fraud", "device_other_susp_cards"],
}
NAME_PARTS = {"card_dormant": "DORMANT_CARD", "night_time": "NIGHT", "amount_anomaly": "HIGH_VALUE", "hour_atypical": "ODD_HOUR",
              "velocity_24h_high": "BURST", "email_changed": "EMAIL_SWITCH", "device_unseen": "NEW_DEVICE", "proxy": "PROXY",
              "region_novel": "NEW_REGION", "match_fail": "MATCH_FAIL", "online_atypical": "ONLINE_SHIFT"}


def load_discovered() -> dict:
    try:
        return json.loads(OUT.read_text())
    except Exception:  # noqa: BLE001
        return {}


def discover(write_graph: bool = True, llm=None) -> dict:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    df = pd.read_parquet(settings.work_dir / "history_features.parquet")
    fr = df[df["outcome"] == "CONFIRMED_FRAUD"].copy()
    sig = pd.DataFrame({p: fr[s].mean(axis=1) for p, s in SIGNATURES.items()})
    fr["max_signature"] = sig.max(axis=1)
    residual = fr[(fr["max_signature"] < 0.5) | (fr["pattern"].isin(["UNCLASSIFIED", "OTHER", "UNKNOWN", "UNDOCUMENTED"]))]
    if len(residual) < 5:
        res = {"hypotheses": [], "n_residual": int(len(residual))}
        OUT.write_text(json.dumps(res, indent=1))
        return res
    X = residual[SIGNAL_NAMES].astype(float).to_numpy()
    best_k, best_s, labels = 1, -1.0, np.zeros(len(residual), dtype=int)
    for k in range(2, min(5, len(residual) - 1)):
        km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(X)
        if len(set(km.labels_)) < 2:
            continue
        s = silhouette_score(X, km.labels_)
        if s > best_s:
            best_k, best_s, labels = k, s, km.labels_
    base = fr[SIGNAL_NAMES].astype(float).mean()
    hyps = []
    for c in range(best_k):
        g = residual[labels == c]
        if len(g) < 4:
            continue
        rate = g[SIGNAL_NAMES].astype(float).mean()
        lift = (rate + 0.02) / (base + 0.02)
        top = [s for s in lift.sort_values(ascending=False).index
               if rate[s] >= 0.5 and not s.startswith(("precedent_", "prior_"))][:4]
        if not top:
            continue
        name = "_".join(dict.fromkeys(NAME_PARTS.get(s, s.upper()) for s in top[:3]))
        desc = "Confirmed-fraud cases not explained by the documented typologies, characterised by: " + "; ".join(
            f"{SIGNALS[s][1]} ({rate[s]:.0%} of cluster vs {base[s]:.0%} of all fraud)" for s in top)
        h = {"pattern_id": f"HYP-{name}", "name": name, "status": "HYPOTHESIS", "n_cases": int(len(g)), "signals": top,
             "rates": {s: round(float(rate[s]), 3) for s in top}, "lift": {s: round(float(lift[s]), 2) for s in top},
             "analyst_labels": g["pattern"].value_counts().to_dict(), "example_cases": g["case_id"].head(8).tolist(),
             "description": desc, "suggested_policy": "Escalate to analyst (POL-3.9); consider STEP_UP_AUTH on dormant-card reactivation."}
        if llm is not None and llm.enabled:
            from verdict.agent.llm import STR, obj

            named = llm.json_call("Name and describe this undocumented card-fraud typology discovered by clustering. Use only the data.\n"
                                  + json.dumps(h), obj({"name": STR, "description": STR, "suggested_policy": STR}), effort="low")
            if named:
                h.update(llm_name=named["name"], description=named["description"], suggested_policy=named["suggested_policy"])
        hyps.append(h)
    for h in hyps:  # rank by how much of the cluster analysts could not classify (i.e. truly undocumented)
        unl = sum(v for k, v in h["analyst_labels"].items() if k in ("UNCLASSIFIED", "OTHER", "UNKNOWN", ""))
        h["undocumented_share"] = round(unl / h["n_cases"], 2)
    hyps.sort(key=lambda h: -(h["undocumented_share"] * h["n_cases"] + len(h["signals"])))
    res = {"n_fraud_cases": int(len(fr)), "n_residual": int(len(residual)), "k": int(best_k), "silhouette": round(float(best_s), 3),
           "hypotheses": hyps}
    OUT.write_text(json.dumps(res, indent=1))
    if write_graph:
        from verdict.tg.client import conn

        c = conn("ops")
        for h in hyps:
            c.upsertVertex("Pattern", h["pattern_id"], {"name": h["name"], "status": "HYPOTHESIS", "description": h["description"][:1000],
                                                        "signature": json.dumps(h["rates"]), "n_cases": h["n_cases"]})
            for cid in h["example_cases"]:
                c.upsertEdge("FraudCase", cid, "CASE_PATTERN", "Pattern", h["pattern_id"], {"score": 1.0})
    return res
