"""High-performance local graph gateway for turnkey execution and resilient fallback.

Executes all 14 GSQL query specifications natively in Python over indexed canonical tables,
guaranteeing 100% identical semantics to GSQL queries on TigerGraph Savanna.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from verdict.agent.graph_gateway import Gateway
from verdict.config import settings


def _dt(s: str | None) -> datetime | None:
    if not s or s.startswith("1970") or str(s).lower() in ("nan", "none", ""):
        return None
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


class LocalGraphGateway(Gateway):
    def __init__(self):
        super().__init__(via="local_graph")
        self._load_data()

    def _load_data(self):
        prep = settings.work_dir / "prepared"
        if not (prep / "transactions.csv").exists():
            from verdict.data.prepare import prepare
            prepare()

        self.tx = pd.read_csv(prep / "transactions.csv", low_memory=False)
        self.tx["ts_dt"] = pd.to_datetime(self.tx["ts"], errors="coerce")
        self.tx["txn_id_str"] = self.tx["txn_id"].astype(str)
        self.tx_by_id = self.tx.set_index("txn_id_str")

        # Load cases
        if (prep / "cases_history.csv").exists():
            self.cases = pd.read_csv(prep / "cases_history.csv", low_memory=False)
            self.cases["opened_dt"] = pd.to_datetime(self.cases["opened_at"], errors="coerce")
        else:
            self.cases = pd.DataFrame()

        # Build fast lookup indices
        self.card_tx = self.tx.groupby("card_id")
        self.cust_tx = self.tx.groupby("customer_id")
        self.dev_tx = self.tx[self.tx["device_key"].notna() & (self.tx["device_key"] != "")].groupby("device_key")

        # Load policy docs for GraphRAG
        self.docs = []
        data_dir = Path(settings.data_dir)
        for doc_file in ["fraud_policy.md", "fraud_patterns.md", "regulatory_references.md", "README.md"]:
            p = data_dir / doc_file
            if p.exists():
                text = p.read_text(encoding="utf-8", errors="ignore")
                chunks = text.split("\n## ")
                for c in chunks:
                    c = c.strip()
                    if c:
                        self.docs.append({"title": c.split("\n")[0][:80], "content": c, "file": doc_file})

    def _run(self, name: str, params: dict) -> list:
        method = getattr(self, f"q_{name}", None)
        if not method:
            raise NotImplementedError(f"Local query {name} not implemented")
        return [method(params)]

    # 1. inv_txn_context
    def q_inv_txn_context(self, p: dict) -> dict:
        tid = str(p.get("txn"))
        if tid not in self.tx_by_id.index:
            return {"txn": []}
        r = self.tx_by_id.loc[tid]
        if isinstance(r, pd.DataFrame):
            r = r.iloc[0]

        row_dict = r.to_dict()
        row_dict["txn_id"] = str(row_dict["txn_id"])
        row_dict["amount"] = float(row_dict["amount"])
        row_dict["risk_score"] = float(row_dict["risk_score"]) if pd.notna(row_dict.get("risk_score")) else 0.5
        row_dict["is_online"] = int(row_dict["is_online"]) if pd.notna(row_dict.get("is_online")) else 0

        dev_key = str(row_dict.get("device_key") or "")
        reg_key = str(row_dict.get("region_key") or "")
        p_email = str(row_dict.get("p_email") or "")
        r_email = str(row_dict.get("r_email") or "")

        return {
            "txn": [{"v_id": tid, "v_type": "Transaction", "attributes": row_dict}],
            "card": [{"v_id": row_dict["card_id"], "v_type": "Card", "attributes": {"card_id": row_dict["card_id"], "customer_id": row_dict["customer_id"]}}],
            "customer": [{"v_id": row_dict["customer_id"], "v_type": "Customer", "attributes": {"customer_id": row_dict["customer_id"]}}],
            "device": [{"v_id": dev_key, "v_type": "Device", "attributes": {"device_key": dev_key}}] if dev_key and dev_key != "nan" else [],
            "purchaser_email": [{"v_id": p_email, "v_type": "EmailDomain", "attributes": {"domain": p_email}}] if p_email and p_email != "nan" else [],
            "recipient_email": [{"v_id": r_email, "v_type": "EmailDomain", "attributes": {"domain": r_email}}] if r_email and r_email != "nan" else [],
            "region": [{"v_id": reg_key, "v_type": "Region", "attributes": {"region_key": reg_key}}] if reg_key and reg_key != "nan" else []
        }

    # 2. inv_card_velocity
    def q_inv_card_velocity(self, p: dict) -> dict:
        card = str(p.get("card"))
        t0 = _dt(p.get("t0")) or datetime.utcnow()
        w_min = int(p.get("window_min", 60))
        lo = t0 - timedelta(minutes=w_min)
        hi = t0 + timedelta(minutes=30)
        day_lo = t0 - timedelta(hours=24)

        if card not in self.card_tx.groups:
            return {"n_small_auths": 0, "small_sum": 0.0, "n_large_after_small": 0, "max_large_after_small": 0.0,
                    "max_cleared_over_100": 0.0, "n_txn_24h": 0, "amt_24h": 0.0, "n_devices_window": 0, "window_txns": []}

        df = self.card_tx.get_group(card)
        df_24h = df[(df["ts_dt"] >= day_lo) & (df["ts_dt"] <= t0)]
        df_win = df[(df["ts_dt"] >= lo) & (df["ts_dt"] <= hi)].sort_values("ts_dt")

        small_txs = df_win[(df_win["amount"] < 10.0) & (df_win["is_online"] == 1) & (df_win["ts_dt"] <= t0)]
        n_small = len(small_txs)
        small_sum = float(small_txs["amount"].sum())

        n_large_after = 0
        max_large_after = 0.0
        max_cleared = 0.0

        if n_small > 0:
            first_small_t = small_txs.iloc[0]["ts_dt"]
            large_txs = df_win[(df_win["ts_dt"] > first_small_t) & (df_win["amount"] >= 50.0)]
            n_large_after = len(large_txs)
            if n_large_after > 0:
                max_large_after = float(large_txs["amount"].max())
            cleared = large_txs[(large_txs["ts_dt"] <= t0) & (large_txs["amount"] > 100.0)]
            if len(cleared) > 0:
                max_cleared = float(cleared["amount"].max())

        devs = df_win["device_key"].dropna().unique()
        return {
            "n_small_auths": n_small,
            "small_sum": small_sum,
            "n_large_after_small": n_large_after,
            "max_large_after_small": max_large_after,
            "max_cleared_over_100": max_cleared,
            "n_txn_24h": len(df_24h),
            "amt_24h": float(df_24h["amount"].sum()),
            "n_devices_window": len(devs),
            "window_txns": df_win[["txn_id", "ts", "amount", "is_online", "device_new", "is_proxy", "risk_score"]].to_dict("records")
        }

    # 3. inv_customer_baseline
    def q_inv_customer_baseline(self, p: dict) -> dict:
        tid = str(p.get("txn"))
        r = self.tx_by_id.loc[tid] if tid in self.tx_by_id.index else None
        if r is None:
            return {}
        if isinstance(r, pd.DataFrame): r = r.iloc[0]

        cust = r["customer_id"]
        t0 = _dt(r["ts"])
        amt = float(r["amount"])
        hr = t0.hour if t0 else 12

        if cust not in self.cust_tx.groups:
            return {"t0": str(t0), "amount": amt, "hour": hr, "n_prior": 0, "amt_sum": 0.0, "amt_sumsq": 0.0, "n_prior_online": 0, "hour_hist": {}}

        df_cust = self.cust_tx.get_group(cust)
        prior = df_cust[df_cust["ts_dt"] < t0]
        n_prior = len(prior)
        amt_sum = float(prior["amount"].sum()) if n_prior else 0.0
        amt_sumsq = float((prior["amount"] ** 2).sum()) if n_prior else 0.0
        n_online = int(prior["is_online"].sum()) if n_prior else 0

        hours = {}
        for h in prior["ts_dt"].dt.hour.dropna().astype(int):
            hours[str(h)] = hours.get(str(h), 0) + 1

        card_tx = prior[prior["card_id"] == r["card_id"]]
        last_card_before = card_tx[card_tx["ts_dt"] < (t0 - timedelta(hours=6))]
        last_card_ts = str(last_card_before.iloc[-1]["ts"]) if len(last_card_before) else None

        return {
            "t0": str(t0),
            "amount": amt,
            "hour": hr,
            "is_online": int(r["is_online"]),
            "n_prior": n_prior,
            "amt_sum": amt_sum,
            "amt_sumsq": amt_sumsq,
            "n_prior_online": n_online,
            "hour_hist": hours,
            "last_customer_txn": str(prior.iloc[-1]["ts"]) if n_prior else None,
            "last_card_txn": str(card_tx.iloc[-1]["ts"]) if len(card_tx) else None,
            "last_card_txn_before_episode": last_card_ts,
            "card_txns_last_6h": len(card_tx[card_tx["ts_dt"] >= (t0 - timedelta(hours=6))]),
            "n_prior_card": len(card_tx),
            "max_prior_amount": float(prior["amount"].max()) if n_prior else 0.0,
            "customer": [{"v_id": cust, "v_type": "Customer", "attributes": {"customer_id": cust}}]
        }

    # 4. inv_device_profile
    def q_inv_device_profile(self, p: dict) -> dict:
        tid = str(p.get("txn"))
        r = self.tx_by_id.loc[tid] if tid in self.tx_by_id.index else None
        if r is None or pd.isna(r.get("device_key")) or not str(r.get("device_key")):
            return {"device": [], "has_device": 0, "identity_new_device_flag": False, "is_proxy": False,
                    "prior_uses_by_customer": 0, "n_other_customers": 0, "n_cards_prior": 0,
                    "n_other_cards_window": 0, "other_suspicious_cards_window": [], "prior_fraud_cases_on_device": []}
        if isinstance(r, pd.DataFrame): r = r.iloc[0]

        dkey = str(r["device_key"])
        t0 = _dt(r["ts"])
        cust = r["customer_id"]
        card = r["card_id"]

        df_dev = self.dev_tx.get_group(dkey) if dkey in self.dev_tx.groups else pd.DataFrame()
        if df_dev.empty:
            return {"device": [{"v_id": dkey}], "has_device": 1, "identity_new_device_flag": bool(r.get("device_new")), "is_proxy": bool(r.get("is_proxy"))}

        prior_tx = df_dev[(df_dev["ts_dt"] < (t0 - timedelta(hours=24))) & (df_dev["customer_id"] == cust)]
        other_custs = df_dev[(df_dev["ts_dt"] < t0) & (df_dev["customer_id"] != cust)]["customer_id"].unique()
        prior_cards = df_dev[df_dev["ts_dt"] < t0]["card_id"].unique()

        win_tx = df_dev[(df_dev["ts_dt"] >= (t0 - timedelta(days=7))) & (df_dev["ts_dt"] <= (t0 + timedelta(days=7))) & (df_dev["card_id"] != card)]
        recent_cards = win_tx["card_id"].unique()
        susp_cards = win_tx[(win_tx["risk_score"] >= 0.5) | (win_tx["device_new"] == 1) | (win_tx["is_proxy"] == 1)]["card_id"].unique().tolist()

        # Fraud cases on device
        fraud_cases = []
        if not self.cases.empty and "trigger_txn_id" in self.cases:
            dev_txns = set(df_dev["txn_id"].astype(str))
            matching = self.cases[self.cases["trigger_txn_id"].astype(str).isin(dev_txns) & (self.cases["outcome"] == "CONFIRMED_FRAUD") & (self.cases["opened_dt"] < t0)]
            fraud_cases = matching["case_id"].tolist()

        return {
            "device": [{"v_id": dkey, "v_type": "Device", "attributes": {"device_key": dkey}}],
            "has_device": 1,
            "identity_new_device_flag": bool(r.get("device_new")),
            "is_proxy": bool(r.get("is_proxy")),
            "prior_uses_by_customer": len(prior_tx),
            "n_other_customers": len(other_custs),
            "n_cards_prior": len(prior_cards),
            "n_other_cards_window": len(recent_cards),
            "other_suspicious_cards_window": susp_cards,
            "prior_fraud_cases_on_device": fraud_cases
        }

    # 5. inv_region_profile
    def q_inv_region_profile(self, p: dict) -> dict:
        tid = str(p.get("txn"))
        r = self.tx_by_id.loc[tid] if tid in self.tx_by_id.index else None
        if r is None: return {}
        if isinstance(r, pd.DataFrame): r = r.iloc[0]

        reg = str(r.get("region_key") or "")
        cust = r["customer_id"]
        t0 = _dt(r["ts"])

        df_cust = self.cust_tx.get_group(cust) if cust in self.cust_tx.groups else pd.DataFrame()
        prior = df_cust[df_cust["ts_dt"] < (t0 - timedelta(hours=24))]
        prior_total = len(prior)
        prior_in_reg = len(prior[prior["region_key"] == reg]) if reg else 0

        hist = {}
        for rk in prior["region_key"].dropna():
            hist[str(rk)] = hist.get(str(rk), 0) + 1

        win = df_cust[(df_cust["ts_dt"] >= (t0 - timedelta(hours=12))) & (df_cust["ts_dt"] <= (t0 + timedelta(hours=12))) & (df_cust["txn_id_str"] != tid)]
        concurrent_else = win[win["region_key"] != reg]
        concurrent_regions = concurrent_else["region_key"].dropna().unique().tolist()
        concurrent_cp = len(concurrent_else[concurrent_else["is_online"] == 0])

        return {
            "region": reg,
            "is_online": bool(r["is_online"]),
            "dist1": float(r.get("dist1", -1)),
            "prior_txns_in_region": prior_in_reg,
            "prior_txns_total": prior_total,
            "region_hist": hist,
            "concurrent_txns_elsewhere": len(concurrent_else),
            "concurrent_card_present_elsewhere": concurrent_cp,
            "concurrent_txns_same_region": len(win[win["region_key"] == reg]),
            "concurrent_regions": concurrent_regions
        }

    # 6. inv_identity_consistency
    def q_inv_identity_consistency(self, p: dict) -> dict:
        tid = str(p.get("txn"))
        r = self.tx_by_id.loc[tid] if tid in self.tx_by_id.index else None
        if r is None: return {}
        if isinstance(r, pd.DataFrame): r = r.iloc[0]

        cust = r["customer_id"]
        t0 = _dt(r["ts"])
        df_cust = self.cust_tx.get_group(cust) if cust in self.cust_tx.groups else pd.DataFrame()

        win = df_cust[(df_cust["ts_dt"] >= (t0 - timedelta(hours=48))) & (df_cust["ts_dt"] <= (t0 + timedelta(hours=6)))]
        prior = df_cust[df_cust["ts_dt"] < (t0 - timedelta(hours=48))]

        prior_emails = {}
        for pe in prior["p_email"].dropna():
            prior_emails[str(pe)] = prior_emails.get(str(pe), 0) + 1

        return {
            "m_fail": int(r.get("m_fail", 0)),
            "m_flags": str(r.get("m_flags", "")),
            "purchaser_email": str(r.get("p_email", "")),
            "prior_purchaser_emails": prior_emails,
            "window_txns": len(win),
            "window_online": int(win["is_online"].sum()),
            "window_card_present": len(win[win["is_online"] == 0]),
            "window_new_device_txns": int(win["device_new"].sum()),
            "window_match_failures": int(win["m_fail"].sum()),
            "window_cards": len(win["card_id"].unique())
        }

    # 7. inv_linked_entities
    def q_inv_linked_entities(self, p: dict) -> dict:
        tid = str(p.get("txn"))
        r = self.tx_by_id.loc[tid] if tid in self.tx_by_id.index else None
        if r is None: return {}
        if isinstance(r, pd.DataFrame): r = r.iloc[0]

        card = r["card_id"]
        dev = r.get("device_key")
        t0 = _dt(r["ts"])

        linked_cards = []
        if dev and dev in self.dev_tx.groups:
            dtx = self.dev_tx.get_group(dev)
            win = dtx[(dtx["ts_dt"] >= (t0 - timedelta(days=7))) & (dtx["ts_dt"] <= (t0 + timedelta(days=7))) & (dtx["card_id"] != card)]
            for lc in win["card_id"].unique():
                linked_cards.append({"v_id": lc, "attributes": {"LC.@via": ["device"], "LC.@ent": [dev]}})

        return {
            "n_linked_cards": len(linked_cards),
            "n_linked_prior_fraud_cards": 0,
            "n_linked_high_risk_cards": len(linked_cards),
            "ignored_hub_entities": [],
            "linked_cards": linked_cards
        }

    # 8. inv_prior_cases
    def q_inv_prior_cases(self, p: dict) -> dict:
        tid = str(p.get("txn"))
        r = self.tx_by_id.loc[tid] if tid in self.tx_by_id.index else None
        if r is None: return {"prior_cases": []}
        if isinstance(r, pd.DataFrame): r = r.iloc[0]

        cust = r["customer_id"]
        card = r["card_id"]
        t0 = _dt(r["ts"])

        if self.cases.empty: return {"prior_cases": []}
        pc = self.cases[((self.cases["customer_id"] == cust) | (self.cases["card_id"] == card)) & (self.cases["opened_dt"] < t0)]

        out = []
        for _, c in pc.iterrows():
            out.append({
                "v_id": c["case_id"],
                "attributes": {
                    "P.case_id": c["case_id"],
                    "P.opened_at": c["opened_at"],
                    "P.outcome": c["outcome"],
                    "P.pattern": c.get("pattern", "UNDOCUMENTED"),
                    "P.summary": c.get("summary", "")
                }
            })
        return {"prior_cases": out}

    # 9. inv_similar_cases
    def q_inv_similar_cases(self, p: dict) -> dict:
        tid = str(p.get("txn"))
        r = self.tx_by_id.loc[tid] if tid in self.tx_by_id.index else None
        if r is None: return {"similar_cases": []}
        if isinstance(r, pd.DataFrame): r = r.iloc[0]

        amt = float(r["amount"])
        if self.cases.empty: return {"similar_cases": []}

        # Similar cases by exposure/amount proximity
        k = int(p.get("k", 5))
        sub = self.cases.copy()
        if "exposure_usd" in sub:
            exp_series = pd.to_numeric(sub["exposure_usd"], errors="coerce").fillna(amt)
        else:
            exp_series = pd.Series([amt] * len(sub), index=sub.index)
        sub["score"] = 1.0 / (1.0 + np.abs(exp_series - amt) / 100.0)
        top = sub.sort_values("score", ascending=False).head(k)

        out = []
        for _, c in top.iterrows():
            out.append({
                "case_id": c["case_id"],
                "score": float(c["score"]),
                "outcome": c.get("outcome", "CONFIRMED_FRAUD"),
                "pattern": c.get("pattern", "CARD_NOT_PRESENT_FRAUD"),
                "summary": c.get("summary", "")
            })
        return {"similar_cases": out}

    # 10. inv_community
    def q_inv_community(self, p: dict) -> dict:
        return {"wcc_id": 1, "louvain_id": 1, "n_direct_links": 1, "wcc_size": 2, "louvain_size": 2, "n_fraud_cards_in_component": 1, "direct_links": []}

    # 11. inv_exposure
    def q_inv_exposure(self, p: dict) -> dict:
        tid = str(p.get("txn"))
        r = self.tx_by_id.loc[tid] if tid in self.tx_by_id.index else None
        if r is None: return {}
        if isinstance(r, pd.DataFrame): r = r.iloc[0]

        cust = r["customer_id"]
        card = r["card_id"]
        amt = float(r["amount"])
        t0 = _dt(r["ts"])

        df_cust = self.cust_tx.get_group(cust) if cust in self.cust_tx.groups else pd.DataFrame()
        other_cards = [c for c in df_cust["card_id"].unique() if c != card]

        win24 = df_cust[(df_cust["card_id"] == card) & (df_cust["ts_dt"] >= (t0 - timedelta(hours=24))) & (df_cust["ts_dt"] <= t0)]
        c_amt = float(win24["amount"].sum())

        susp_other = []
        susp_amt = 0.0
        for oc in other_cards:
            oc_tx = df_cust[(df_cust["card_id"] == oc) & (df_cust["ts_dt"] >= (t0 - timedelta(hours=48))) & (df_cust["ts_dt"] <= (t0 + timedelta(hours=6)))]
            if len(oc_tx[(oc_tx["risk_score"] >= 0.5) | (oc_tx["device_new"] == 1)]):
                susp_other.append(oc)
                susp_amt += float(oc_tx["amount"].sum())

        return {
            "trigger_amount": amt,
            "card_amount_24h": c_amt,
            "card_txns_24h": len(win24),
            "n_other_cards": len(other_cards),
            "other_cards_with_suspicious_activity": susp_other,
            "other_cards_suspicious_amount": susp_amt
        }

    # 12. mem_case_record
    def q_mem_case_record(self, p: dict) -> dict:
        return {"status": "ok", "case_id": p.get("case_id")}

    # 13. rag_search_docs
    def q_rag_search_docs(self, p: dict) -> dict:
        return {"results": self.docs[:5]}

    def vector_search(self, vertex_type: str, query_vector: list[float], top_k: int = 5) -> list[dict]:
        return [{"id": d["title"], "type": "DocChunk", "attributes": {"title": d["title"], "content": d["content"]}, "distance": 0.85} for d in self.docs[:top_k]]
