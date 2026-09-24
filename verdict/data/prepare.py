"""Normalise raw dataset files into canonical vertex/edge CSVs for TigerGraph loading."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from verdict.config import settings


def load_map(path: Path | None = None) -> dict:
    return yaml.safe_load(Path(path or settings.schema_map).read_text())


def _h(s: str, n: int = 12) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:n]


def _clean(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none") else s


def _num_str(v) -> str:
    s = _clean(v)
    if s.endswith(".0"):
        s = s[:-2]
    return s


def prepare(data_dir: Path | None = None, out_dir: Path | None = None) -> dict:
    data_dir = Path(data_dir or settings.data_dir)
    out = Path(out_dir or settings.work_dir / "prepared")
    out.mkdir(parents=True, exist_ok=True)
    m = load_map()
    fm, tm, im, cm, pm = m["files"], m["transactions"], m["identity"], m["closed_cases"], m["case_pack"]

    tx = pd.read_csv(data_dir / fm["transactions"], low_memory=False)
    idn = pd.read_csv(data_dir / fm["identity"], low_memory=False) if (data_dir / fm["identity"]).exists() else pd.DataFrame()
    cc = pd.read_csv(data_dir / fm["closed_cases"], low_memory=False)
    cp = pd.read_csv(data_dir / fm["case_pack"], low_memory=False)

    # ---------------------------------------------------------------- transactions
    t = pd.DataFrame()
    t["txn_id"] = tx[tm["txn_id"]].map(_num_str)
    t["customer_id"] = tx[tm["customer_id"]].map(_clean)
    if tm.get("timestamp") and tm["timestamp"] in tx:
        ts = pd.to_datetime(tx[tm["timestamp"]], errors="coerce")
    else:
        ts = pd.Timestamp(tm["base_date"]) + pd.to_timedelta(tx[tm["txn_dt"]], unit="s")
    t["ts"] = ts.dt.strftime("%Y-%m-%d %H:%M:%S")
    t["amount"] = pd.to_numeric(tx[tm["amount"]], errors="coerce").fillna(0).round(2)
    t["product_cd"] = tx[tm["product_cd"]].map(_clean)
    ch = tx[tm["channel"]].map(_clean) if tm.get("channel") in tx else pd.Series([""] * len(tx))
    t["channel"] = ch
    t["is_online"] = ch.isin(tm["online_channel_values"]).astype(int)
    t["risk_score"] = pd.to_numeric(tx[tm["risk_score"]], errors="coerce").fillna(0).round(4)
    t["dist1"] = pd.to_numeric(tx.get(tm["dist1"]), errors="coerce").fillna(-1)
    mf = tx[[c for c in tm["m_flags"] if c in tx]].fillna("")
    t["m_flags"] = mf.astype(str).agg("".join, axis=1) if len(mf.columns) else ""
    # count of explicit match failures (T/F flags that are F; M4 == M2 is a weak mismatch)
    t["m_fail"] = (mf == "F").sum(axis=1) + (mf.get("M4", pd.Series([""] * len(tx))) == "M2").astype(int)
    # card fingerprint
    if tm.get("card_id") and tm["card_id"] in tx:
        t["card_fp"] = tx[tm["card_id"]].map(_clean)
    else:
        key = tx[tm["card_key_columns"]].fillna("").astype(str).agg("|".join, axis=1)
        t["card_fp"] = key.map(lambda s: "FP-" + _h(s, 10))
    t["region_key"] = [f"{_num_str(a)}|{_num_str(b)}" if _num_str(a) else "" for a, b in zip(tx[tm["addr1"]], tx[tm["addr2"]])]
    t["p_email"] = tx[tm["p_email"]].map(_clean).str.lower()
    t["r_email"] = tx[tm["r_email"]].map(_clean).str.lower()

    # ---------------------------------------------------------------- identity
    t["device_key"] = ""
    t["is_proxy"] = 0
    t["device_new"] = 0
    dev_rows = pd.DataFrame(columns=["device_key", "device_type", "device_info", "os", "browser", "screen"])
    if len(idn):
        i = pd.DataFrame()
        i["txn_id"] = idn[im["txn_id"]].map(_num_str)
        parts = {k: idn[im[k]].map(_clean) if im.get(k) in idn else pd.Series([""] * len(idn)) for k in ("device_info", "os", "browser", "screen", "device_type")}
        for k, v in parts.items():
            i[k] = v
        sig = i["device_info"] + "|" + i["os"] + "|" + i["browser"] + "|" + i["screen"]
        i["device_key"] = np.where(sig.str.replace("|", "", regex=False).str.len() > 0, "DEV-" + sig.map(lambda s: _h(s, 10)), "")
        i["is_proxy"] = idn[im["proxy"]].map(_clean).str.contains("PROXY:ANONYMOUS|PROXY:HIDDEN", case=False).astype(int) if im.get("proxy") in idn else 0
        i["device_new"] = idn[im["new_device"]].map(_clean).isin(im["new_device_values"]).astype(int) if im.get("new_device") in idn else 0
        t = t.drop(columns=["device_key", "is_proxy", "device_new"]).merge(i[["txn_id", "device_key", "is_proxy", "device_new"]], on="txn_id", how="left")
        t["device_key"] = t["device_key"].fillna("")
        t["is_proxy"] = t["is_proxy"].fillna(0).astype(int)
        t["device_new"] = t["device_new"].fillna(0).astype(int)
        dev_rows = i[i["device_key"] != ""].drop_duplicates("device_key")[["device_key", "device_type", "device_info", "os", "browser", "screen"]]

    # ---------------------------------------------------------------- closed cases & card ids
    sep = cm.get("list_sep", ";")
    txn_to_fp = dict(zip(t["txn_id"], t["card_fp"]))
    fp_to_card: dict[str, str] = {}

    def ids(v) -> list[str]:
        s = _clean(v)
        return [_num_str(x) for x in s.split(sep) if x.strip()] if s else []

    for _, r in cc.iterrows():
        card = _clean(r.get(cm["card_id"]))
        for tid in ids(r.get(cm["involved_txn_ids"])) + ids(r.get(cm["trigger_txn_id"])):
            fp = txn_to_fp.get(tid)
            if fp and card:
                fp_to_card.setdefault(fp, card)
    for _, r in cp.iterrows():
        fp = txn_to_fp.get(_num_str(r.get(pm["trigger_txn_id"])))
        card = _clean(r.get(pm["card_id"]))
        if fp and card:
            fp_to_card.setdefault(fp, card)
    t["card_id"] = t["card_fp"].map(lambda fp: fp_to_card.get(fp, fp))

    # ---------------------------------------------------------------- vertices
    cards = tx[tm["card_attr_columns"]].copy()
    cards["card_id"] = t["card_id"].values
    cards["customer_id"] = t["customer_id"].values
    cards = cards.drop_duplicates("card_id")
    for c in tm["card_attr_columns"]:
        cards[c] = cards[c].map(_clean)

    t["ts_dt"] = pd.to_datetime(t["ts"])
    g = t.groupby("customer_id")
    cust = pd.DataFrame({
        "customer_id": g.size().index,
        "first_seen": g["ts"].min().values,
        "n_txn": g.size().values,
        "amt_mean": g["amount"].mean().round(2).values,
        "amt_std": g["amount"].std().fillna(0).round(2).values,
        "amt_p95": g["amount"].quantile(0.95).round(2).values,
        "online_ratio": g["is_online"].mean().round(3).values,
    })
    home = t[t["region_key"] != ""].groupby("customer_id")["region_key"].agg(lambda s: s.value_counts().index[0])
    cust["home_region"] = cust["customer_id"].map(home).fillna("")

    regions = pd.DataFrame({"region_key": sorted(set(t["region_key"]) - {""})})
    emails = pd.DataFrame({"domain": sorted((set(t["p_email"]) | set(t["r_email"])) - {""})})

    # closed cases canonical
    fraud_vals = set(str(v) for v in cm["fraud_outcome_values"])
    cases = pd.DataFrame({
        "case_id": cc[cm["case_id"]].map(_clean),
        "source": "HISTORY",
        "trigger_type": cc[cm["trigger_type"]].map(_clean) if cm.get("trigger_type") in cc else "",
        "status": "CLOSED",
        "opened_at": pd.to_datetime(cc[cm["opened_at"]], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S") if cm.get("opened_at") in cc else "",
        "closed_at": pd.to_datetime(cc[cm["closed_at"]], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S") if cm.get("closed_at") in cc else "",
        "outcome": np.where(cc[cm["outcome"]].astype(str).str.strip().str.upper().isin({v.upper() for v in fraud_vals}), "CONFIRMED_FRAUD", "CLEARED"),
        "pattern": cc[cm["pattern"]].map(_clean).str.upper() if cm.get("pattern") in cc else "",
        "evidence_requested": cc[cm["evidence_requested"]].map(_clean) if cm.get("evidence_requested") in cc else "",
        "evidence_result": cc[cm["evidence_result"]].map(_clean) if cm.get("evidence_result") in cc else "",
        "actions_taken": cc[cm["actions_taken"]].map(_clean) if cm.get("actions_taken") in cc else "",
        "sar_filed": cc[cm["sar_filed"]].map(_clean) if cm.get("sar_filed") in cc else "",
        "summary": cc[cm["narrative"]].map(_clean) if cm.get("narrative") in cc else "",
        "customer_id": cc[cm["customer_id"]].map(_clean) if cm.get("customer_id") in cc else "",
        "card_id": cc[cm["card_id"]].map(_clean),
        "trigger_txn_id": cc[cm["trigger_txn_id"]].map(_num_str) if cm.get("trigger_txn_id") in cc else "",
    })
    case_txn, case_card = [], []
    for _, r in cc.iterrows():
        cid = _clean(r[cm["case_id"]])
        trig = _num_str(r.get(cm["trigger_txn_id"]))
        for tid in ids(r.get(cm["involved_txn_ids"])):
            case_txn.append((cid, tid, "TRIGGER" if tid == trig else "INVOLVED"))
        if trig and trig not in ids(r.get(cm["involved_txn_ids"])):
            case_txn.append((cid, trig, "TRIGGER"))
        case_card.append((cid, _clean(r[cm["card_id"]]), "PRIMARY"))
        for c in _clean(r.get(cm["connected_card_ids"])).split(sep) if cm.get("connected_card_ids") in cc else []:
            if c.strip():
                case_card.append((cid, c.strip(), "CONNECTED"))

    pack = pd.DataFrame({
        "case_id": cp[pm["case_id"]].map(_clean),
        "trigger_type": cp[pm["trigger_type"]].map(_clean).str.upper(),
        "trigger_time": pd.to_datetime(cp[pm["trigger_time"]], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S") if pm.get("trigger_time") in cp else "",
        "card_id": cp[pm["card_id"]].map(_clean) if pm.get("card_id") in cp else "",
        "customer_id": cp[pm["customer_id"]].map(_clean) if pm.get("customer_id") in cp else "",
        "trigger_txn_id": cp[pm["trigger_txn_id"]].map(_num_str) if pm.get("trigger_txn_id") in cp else "",
        "risk_score": pd.to_numeric(cp[pm["risk_score"]], errors="coerce") if pm.get("risk_score") in cp else np.nan,
        "detail": cp[pm["detail"]].map(_clean) if pm.get("detail") in cp else "",
    })

    # ---------------------------------------------------------------- write
    t_out = t.drop(columns=["ts_dt", "card_fp"])
    t_out.to_csv(out / "transactions.csv", index=False)
    cards.to_csv(out / "cards.csv", index=False)
    cust.to_csv(out / "customers.csv", index=False)
    dev_rows.to_csv(out / "devices.csv", index=False)
    regions.to_csv(out / "regions.csv", index=False)
    emails.to_csv(out / "emails.csv", index=False)
    cases.to_csv(out / "cases_history.csv", index=False)
    pd.DataFrame(case_txn, columns=["case_id", "txn_id", "role"]).to_csv(out / "case_txn.csv", index=False)
    pd.DataFrame(case_card, columns=["case_id", "card_id", "role"]).to_csv(out / "case_card.csv", index=False)
    pack.to_csv(out / "case_pack.csv", index=False)
    stats = {
        "transactions": len(t_out), "cards": len(cards), "customers": len(cust), "devices": len(dev_rows),
        "regions": len(regions), "emails": len(emails), "closed_cases": len(cases),
        "fraud_cases": int((cases["outcome"] == "CONFIRMED_FRAUD").sum()), "case_pack": len(pack),
        "cards_mapped_from_cases": len(fp_to_card),
        "time_range": [t["ts"].min(), t["ts"].max()],
    }
    (out / "stats.json").write_text(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2))
