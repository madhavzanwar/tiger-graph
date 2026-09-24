"""Turn graph query results into typed, explainable evidence signals.

``collect_core`` runs the mandatory evidence queries for a trigger transaction; ``derive_signals`` maps the raw
results onto a fixed set of named binary signals (plus the model risk score) that the calibrated scorer uses.
Each signal carries a human-readable explanation and the query it came from, so every number in the ledger can
be traced back to a GSQL query.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from verdict.agent.graph_gateway import Gateway

# name -> (source query, description shown in the ledger)
SIGNALS: dict[str, tuple[str, str]] = {
    "ct_small_burst": ("inv_card_velocity", "3+ small (<$10) online authorisations on the card within 1h before the trigger"),
    "ct_large_after_small": ("inv_card_velocity", "a larger purchase followed the small authorisations"),
    "ct_cleared_over_100": ("inv_card_velocity", "a purchase over $100 already cleared after the small authorisations"),
    "velocity_24h_high": ("inv_card_velocity", "5+ transactions on the card in the last 24h"),
    "amount_anomaly": ("inv_customer_baseline", "amount far above the customer's history (z>3 or >2.5x prior max)"),
    "hour_atypical": ("inv_customer_baseline", "transaction hour the customer almost never uses"),
    "night_time": ("inv_customer_baseline", "transaction between midnight and 5am"),
    "card_dormant": ("inv_customer_baseline", "card inactive for 30+ days before this activity"),
    "online_atypical": ("inv_customer_baseline", "online purchase by a customer who rarely shops online"),
    "device_new_flag": ("inv_device_profile", "identity record marks the device as new for this account"),
    "device_unseen": ("inv_device_profile", "device never used by this customer before"),
    "proxy": ("inv_device_profile", "connection through an anonymous proxy"),
    "device_multi_customer": ("inv_device_profile", "device previously used by 2+ other customers"),
    "device_prior_fraud": ("inv_device_profile", "device linked to a previously confirmed fraud case"),
    "device_other_susp_cards": ("inv_device_profile", "other cards used this device with suspicious activity in the same week"),
    "region_novel": ("inv_region_profile", "billing region where the customer has no prior history"),
    "region_novel_card_present": ("inv_region_profile", "card-present purchase in a new region"),
    "concurrent_home_activity": ("inv_region_profile", "customer's normal activity continued elsewhere at the same time"),
    "dist_far": ("inv_region_profile", "large billing distance (dist1 >= 250)"),
    "match_fail": ("inv_identity_consistency", "2+ address/name match-flag failures"),
    "email_changed": ("inv_identity_consistency", "purchaser email domain never used by the customer before"),
    "mixed_channel_new_device": ("inv_identity_consistency", "online and in-store activity with new devices inside 48h"),
    "ring_linked_high_risk": ("inv_linked_entities", "2+ other cards share a device/recipient email with high-risk activity"),
    "ring_linked_prior_fraud": ("inv_linked_entities", "a card sharing a device/recipient email has a confirmed fraud case"),
    "community_fraud": ("inv_community", "the card's WCC component contains cards with confirmed fraud"),
    "prior_fraud_case": ("inv_prior_cases", "customer/card had a confirmed fraud case before"),
    "prior_cleared_case": ("inv_prior_cases", "customer/card had a cleared (false-positive) case before"),
    "other_cards_suspicious": ("inv_exposure", "suspicious activity on the customer's other cards (wider compromise)"),
    "precedent_fraud_majority": ("inv_similar_cases", "most structurally similar past cases were confirmed fraud"),
    "precedent_cleared_majority": ("inv_similar_cases", "most structurally similar past cases were cleared"),
}
SIGNAL_NAMES = list(SIGNALS)

CORE_QUERIES = ["inv_card_velocity", "inv_customer_baseline", "inv_device_profile", "inv_region_profile",
                "inv_identity_consistency", "inv_linked_entities", "inv_prior_cases", "inv_similar_cases",
                "inv_community", "inv_exposure"]


def _dt(s: str | None) -> datetime | None:
    if not s or s.startswith("1970"):
        return None
    try:
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _first(res: list) -> dict:
    return res[0] if res else {}


def txn_context(gw: Gateway, txn_id: str) -> dict:
    r = _first(gw.run_query("inv_txn_context", {"txn": txn_id}))
    if not r.get("txn"):
        raise KeyError(f"transaction {txn_id} not found")
    tx = r["txn"][0]["attributes"]
    return {
        "txn": tx,
        "card": (r.get("card") or [{}])[0].get("attributes", {}),
        "customer": (r.get("customer") or [{}])[0].get("attributes", {}),
        "device": (r.get("device") or [{}])[0].get("attributes", {}),
        "purchaser_email": [x["v_id"] for x in r.get("purchaser_email", [])],
        "recipient_email": [x["v_id"] for x in r.get("recipient_email", [])],
        "region": [x["v_id"] for x in r.get("region", [])],
    }


def query_params(name: str, ctx: dict) -> dict:
    tx = ctx["txn"]
    if name == "inv_card_velocity":
        return {"card": tx["card_id"], "t0": tx["ts"], "window_min": 60}
    if name == "inv_community":
        return {"card": tx["card_id"]}
    if name == "inv_similar_cases":
        return {"txn": tx["txn_id"], "k": 8}
    return {"txn": tx["txn_id"]}


def collect_core(gw: Gateway, txn_id: str, parallel: bool = True, queries: list[str] | None = None) -> dict:
    ctx = txn_context(gw, txn_id)
    names = queries or CORE_QUERIES
    raw: dict[str, Any] = {"inv_txn_context": ctx}

    def one(n):
        return n, _first(gw.run_query(n, query_params(n, ctx)))

    if parallel and gw.via == "direct":
        with ThreadPoolExecutor(max_workers=6) as ex:
            for n, r in ex.map(one, names):
                raw[n] = r
    else:
        for n in names:
            raw[n] = one(n)[1]
    return raw


def _hour_frac(hist: dict, hr: int) -> float:
    total = sum(hist.values()) or 0
    if not total:
        return 1.0
    near = sum(v for k, v in hist.items() if min(abs(int(k) - hr), 24 - abs(int(k) - hr)) <= 2)
    return near / total


def derive_signals(raw: dict, exclude_case_id: str | None = None) -> tuple[dict[str, float], dict[str, Any]]:
    """Returns (signals, facts). ``signals`` holds 0/1 per SIGNAL_NAMES plus ``risk_score``."""
    ctx = raw["inv_txn_context"]
    tx = ctx["txn"]
    s = {k: 0.0 for k in SIGNAL_NAMES}
    f: dict[str, Any] = {"txn_id": tx["txn_id"], "card_id": tx["card_id"], "customer_id": tx["customer_id"], "ts": tx["ts"],
                         "amount": float(tx["amount"]), "channel": tx.get("channel"), "is_online": bool(tx.get("is_online")),
                         "risk_score": float(tx.get("risk_score") or 0.0)}

    v = raw.get("inv_card_velocity", {})
    f["small_auths_1h"] = int(v.get("n_small_auths", 0))
    f["cleared_purchase_over_100"] = float(v.get("max_cleared_over_100", 0) or 0)
    f["card_txns_24h"] = int(v.get("n_txn_24h", 0))
    s["ct_small_burst"] = float(f["small_auths_1h"] >= 3)
    s["ct_large_after_small"] = float(f["small_auths_1h"] >= 3 and int(v.get("n_large_after_small", 0)) >= 1)
    s["ct_cleared_over_100"] = float(f["small_auths_1h"] >= 3 and f["cleared_purchase_over_100"] > 100)
    s["velocity_24h_high"] = float(f["card_txns_24h"] >= 5)

    b = raw.get("inv_customer_baseline", {})
    n = int(b.get("n_prior", 0))
    amt = f["amount"]
    mean = (b.get("amt_sum", 0) / n) if n else 0.0
    var = (b.get("amt_sumsq", 0) / n - mean * mean) if n else 0.0
    sd = math.sqrt(max(var, 1e-9))
    z = (amt - mean) / sd if n >= 3 and sd > 1e-6 else 0.0
    f.update(n_prior_txns=n, amount_mean=round(mean, 2), amount_z=round(z, 2), max_prior_amount=float(b.get("max_prior_amount", 0) or 0))
    s["amount_anomaly"] = float(n >= 5 and (z > 3 or amt > 2.5 * max(f["max_prior_amount"], 1)))
    hr = int(b.get("hour", 12))
    hf = _hour_frac(b.get("hour_hist", {}) or {}, hr)
    s["hour_atypical"] = float(n >= 8 and hf <= 0.05)
    s["night_time"] = float(0 <= hr < 5)
    t0 = _dt(tx["ts"])
    last_hist = _dt(b.get("last_card_txn_before_episode"))
    gap = (t0 - last_hist).days if (t0 and last_hist) else None
    f["card_gap_days"] = gap
    s["card_dormant"] = float(gap is not None and gap >= 30)
    online_ratio = (b.get("n_prior_online", 0) / n) if n else 0.0
    s["online_atypical"] = float(f["is_online"] and n >= 8 and online_ratio < 0.15)

    d = raw.get("inv_device_profile", {})
    has_dev = int(d.get("has_device", 0)) > 0
    s["device_new_flag"] = float(bool(d.get("identity_new_device_flag")))
    s["device_unseen"] = float(has_dev and int(d.get("prior_uses_by_customer", 0)) == 0)
    s["proxy"] = float(bool(d.get("is_proxy")))
    s["device_multi_customer"] = float(has_dev and int(d.get("n_other_customers", 0)) >= 2)
    s["device_prior_fraud"] = float(len([c for c in d.get("prior_fraud_cases_on_device", []) if c != exclude_case_id]) >= 1)
    s["device_other_susp_cards"] = float(len(d.get("other_suspicious_cards_window", [])) >= 1)
    f["device_key"] = (d.get("device") or [{}])[0].get("v_id") if d.get("device") else None
    f["other_suspicious_cards_on_device"] = d.get("other_suspicious_cards_window", [])

    r = raw.get("inv_region_profile", {})
    novel = int(r.get("prior_txns_in_region", 0)) == 0 and int(r.get("prior_txns_total", 0)) >= 3
    s["region_novel"] = float(novel)
    s["region_novel_card_present"] = float(novel and not f["is_online"])
    s["concurrent_home_activity"] = float(novel and int(r.get("concurrent_txns_elsewhere", 0)) >= 1)
    s["dist_far"] = float(float(r.get("dist1", -1) or -1) >= 250)
    f["region"] = r.get("region")
    f["concurrent_regions"] = r.get("concurrent_regions", [])

    i = raw.get("inv_identity_consistency", {})
    f["m_fail"] = int(i.get("m_fail", 0))
    s["match_fail"] = float(f["m_fail"] >= 2)
    pe = i.get("purchaser_email") or ""
    prior = i.get("prior_purchaser_emails") or {}
    s["email_changed"] = float(bool(pe) and bool(prior) and pe not in prior)
    s["mixed_channel_new_device"] = float(int(i.get("window_online", 0)) >= 1 and int(i.get("window_card_present", 0)) >= 1
                                          and int(i.get("window_new_device_txns", 0)) >= 1)

    le = raw.get("inv_linked_entities", {})
    f["n_linked_cards"] = int(le.get("n_linked_cards", 0))
    f["n_linked_high_risk_cards"] = int(le.get("n_linked_high_risk_cards", 0))
    f["n_linked_prior_fraud_cards"] = int(le.get("n_linked_prior_fraud_cards", 0))
    f["linked_cards"] = [x.get("v_id") for x in le.get("linked_cards", [])][:20]
    f["linked_via"] = sorted({via for x in le.get("linked_cards", []) for via in x.get("attributes", {}).get("LC.@via", [])})
    s["ring_linked_high_risk"] = float(f["n_linked_high_risk_cards"] >= 2)
    s["ring_linked_prior_fraud"] = float(f["n_linked_prior_fraud_cards"] >= 1)

    cm = raw.get("inv_community", {})
    f["wcc_size"] = int(cm.get("wcc_size", 0))
    f["louvain_size"] = int(cm.get("louvain_size", 0))
    f["n_fraud_cards_in_component"] = int(cm.get("n_fraud_cards_in_component", 0))
    s["community_fraud"] = float(f["wcc_size"] > 1 and f["n_fraud_cards_in_component"] >= 1)

    pc = [c for c in raw.get("inv_prior_cases", {}).get("prior_cases", []) if c.get("v_id") != exclude_case_id]
    outcomes = [c.get("attributes", {}).get("P.outcome") for c in pc]
    f["prior_cases"] = [{"case_id": c.get("v_id"), "outcome": c.get("attributes", {}).get("P.outcome"),
                         "pattern": c.get("attributes", {}).get("P.pattern")} for c in pc][:10]
    s["prior_fraud_case"] = float("CONFIRMED_FRAUD" in outcomes)
    s["prior_cleared_case"] = float("CLEARED" in outcomes)

    ex = raw.get("inv_exposure", {})
    f["card_amount_24h"] = float(ex.get("card_amount_24h", 0) or 0)
    f["n_other_cards"] = int(ex.get("n_other_cards", 0))
    f["other_cards_suspicious"] = ex.get("other_cards_with_suspicious_activity", [])
    s["other_cards_suspicious"] = float(len(f["other_cards_suspicious"]) >= 1)
    f["amount_at_risk"] = round(max(f["card_amount_24h"], f["amount"]) + float(ex.get("other_cards_suspicious_amount", 0) or 0), 2)

    sim = [h for h in raw.get("inv_similar_cases", {}).get("similar_cases", []) if h.get("case_id") != exclude_case_id][:5]
    f["similar_cases"] = [{k: h.get(k) for k in ("case_id", "score", "outcome", "pattern")} for h in sim]
    wsum = sum(h.get("score", 0) for h in sim) or 0
    if len(sim) >= 3 and wsum > 0:
        fr = sum(h.get("score", 0) for h in sim if h.get("outcome") == "CONFIRMED_FRAUD") / wsum
        s["precedent_fraud_majority"] = float(fr >= 0.8)
        s["precedent_cleared_majority"] = float(fr <= 0.5)
        f["precedent_fraud_share"] = round(fr, 2)

    s["risk_score"] = f["risk_score"]
    return s, f


def explain_signal(name: str, facts: dict) -> str:
    base = SIGNALS[name][1]
    extra = {
        "ct_small_burst": f" ({facts.get('small_auths_1h')} small auths)",
        "ct_cleared_over_100": f" (${facts.get('cleared_purchase_over_100', 0):.2f})",
        "velocity_24h_high": f" ({facts.get('card_txns_24h')} txns)",
        "amount_anomaly": f" (${facts.get('amount', 0):.2f} vs mean ${facts.get('amount_mean', 0):.2f}, z={facts.get('amount_z')})",
        "card_dormant": f" ({facts.get('card_gap_days')} days)",
        "ring_linked_high_risk": f" ({facts.get('n_linked_high_risk_cards')} cards via {', '.join(facts.get('linked_via') or []) or 'shared entities'})",
        "ring_linked_prior_fraud": f" ({facts.get('n_linked_prior_fraud_cards')} cards)",
        "community_fraud": f" (component of {facts.get('wcc_size')} cards, {facts.get('n_fraud_cards_in_component')} with fraud)",
        "other_cards_suspicious": f" ({len(facts.get('other_cards_suspicious') or [])} other cards)",
        "precedent_fraud_majority": f" (fraud share {facts.get('precedent_fraud_share')})",
        "precedent_cleared_majority": f" (fraud share {facts.get('precedent_fraud_share')})",
        "region_novel": f" (region {facts.get('region')})",
    }.get(name, "")
    return base + extra
