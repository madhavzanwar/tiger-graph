"""Evidence ledger: calibrated log-odds accounting with uncertainty.

logit P(fraud) = intercept + w_risk * logit(risk_score) + sum_i w_i * signal_i + sum_j LLR(evidence response_j)

Every term is a ledger row. Uncertainty comes from the bootstrap refits of the model: each bootstrap parameter
vector gives one posterior sample, from which we report an 80% credible interval and (with the decision rule)
decision stability.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import numpy as np

from verdict.calibrate.calibration import MODEL_PATH
from verdict.scoring.features import SIGNALS, explain_signal


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def logit(p: float) -> float:
    p = min(max(p, 0.01), 0.99)
    return math.log(p / (1 - p))


@dataclass
class LedgerRow:
    key: str
    label: str
    value: float
    weight: float
    contribution: float
    source: str
    kind: str = "signal"  # signal | prior | evidence_response

    def to_dict(self):
        return self.__dict__.copy()


@dataclass
class Assessment:
    p: float
    ci: tuple[float, float]
    samples: np.ndarray
    rows: list[LedgerRow]
    patterns: list[tuple[str, float]] = field(default_factory=list)
    log_odds: float = 0.0

    def to_dict(self):
        return {"p_fraud": round(self.p, 4), "ci80": [round(self.ci[0], 4), round(self.ci[1], 4)], "log_odds": round(self.log_odds, 3),
                "ledger": [r.to_dict() for r in self.rows], "patterns": [{"pattern": k, "prob": round(v, 3)} for k, v in self.patterns]}


class EvidenceModel:
    def __init__(self, path=MODEL_PATH):
        self.m = json.loads(open(path).read())
        self.names = self.m["feature_names"]
        self.w = np.array([self.m["weights"][n] for n in self.names])
        self.b0 = self.m["intercept"]
        boot = np.array(self.m.get("boot") or [[self.b0] + list(self.w)])
        self.boot_b0, self.boot_w = boot[:, 0], boot[:, 1:]
        self.ev_lik = self.m.get("evidence_likelihoods", {})
        self.pm = self.m.get("patterns") or {}

    def _x(self, signals: dict) -> np.ndarray:
        return np.array([logit(float(signals.get("risk_score", 0.5)))] + [float(signals.get(n, 0)) for n in self.names[1:]])

    def evidence_llr(self, kind: str, response: str) -> float | None:
        lk = self.ev_lik.get(kind)
        if not lk or response not in lk.get("fraud", {}):
            return None
        return math.log(lk["fraud"][response] / lk["legit"][response])

    def assess(self, signals: dict, responses: dict[str, str] | None = None) -> Assessment:
        x = self._x(signals)
        rows = [LedgerRow("base_rate", "Base rate of fraud among investigated cases (intercept)", 1.0, self.b0, self.b0, "calibration", "prior"),
                LedgerRow("risk_score", f"Bank model risk score {signals.get('risk_score', 0):.2f}", float(signals.get("risk_score", 0)),
                          self.w[0], self.w[0] * x[0], "transaction.risk_score", "prior")]
        for i, n in enumerate(self.names[1:], start=1):
            if x[i]:
                rows.append(LedgerRow(n, SIGNALS[n][1], 1.0, float(self.w[i]), float(self.w[i] * x[i]), SIGNALS[n][0]))
        lo = self.b0 + float(self.w @ x)
        samples = self.boot_b0 + self.boot_w @ x
        for kind, resp in (responses or {}).items():
            llr = self.evidence_llr(kind, resp)
            if llr is None:
                continue
            rows.append(LedgerRow(f"{kind}={resp}", f"{kind.replace('_', ' ').lower()} returned {resp}", 1.0, llr, llr,
                                  "evidence_request", "evidence_response"))
            lo += llr
            samples = samples + llr
        ps = sigmoid(samples)
        p = float(sigmoid(lo))
        ci = (float(np.quantile(ps, 0.1)), float(np.quantile(ps, 0.9)))
        return Assessment(p=p, ci=ci, samples=ps, rows=rows, patterns=self.pattern_probs(signals), log_odds=lo)

    def pattern_probs(self, signals: dict) -> list[tuple[str, float]]:
        if not self.pm or "classes" not in self.pm or "intercept" not in self.pm:
            # Signature-based fallback pattern scoring
            p_scores = []
            if signals.get("ct_small_burst") or signals.get("ct_large_after_small"):
                p_scores.append(("CARD_TESTING", 0.95))
            if signals.get("device_new_flag") or signals.get("proxy") or signals.get("device_unseen"):
                p_scores.append(("CNP_NEW_DEVICE", 0.85))
            if signals.get("region_novel_card_present") or signals.get("concurrent_home_activity"):
                p_scores.append(("OUT_OF_REGION", 0.85))
            if signals.get("match_fail") or signals.get("email_changed"):
                p_scores.append(("ACCOUNT_TAKEOVER", 0.80))
            if signals.get("ring_linked_high_risk") or signals.get("community_fraud"):
                p_scores.append(("SHARED_ENTITY_RING", 0.75))
            if not p_scores:
                p_scores = [("CARD_NOT_PRESENT_FRAUD", 0.6), ("UNCLASSIFIED", 0.2)]
            tot = sum(v for _, v in p_scores) or 1.0
            return sorted([(k, round(v / tot, 3)) for k, v in p_scores], key=lambda t: -t[1])
        x = self._x(signals)
        z = np.array(self.pm["intercept"]) + np.array(self.pm["coef"]) @ x
        z = np.exp(z - z.max())
        pr = z / z.sum()
        return sorted(zip(self.pm["classes"], pr.tolist()), key=lambda t: -t[1])

    def feature_stats(self) -> dict:
        return self.m.get("stats", {})


def annotate(rows: list[LedgerRow], facts: dict) -> list[LedgerRow]:
    for r in rows:
        if r.kind == "signal" and r.key in SIGNALS:
            r.label = explain_signal(r.key, facts)
    return rows
