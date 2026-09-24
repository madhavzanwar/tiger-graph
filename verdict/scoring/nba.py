"""Next-best-action engine: expected loss, value of information and the stopping rule.

Decisions:  PROTECT (decline/block), RELEASE (allow/close), GATHER (request more evidence first).

  EL(PROTECT) = (1 - p) * C_fp             C_fp = friction of blocking a genuine customer
  EL(RELEASE) = p * E                      E = amount at risk * (1 + follow-on loss factor)
  EVSI(e)     = min_a EL(a) - sum_o P(o) * min_a EL(a | o) - cost(e)

We GATHER with the evidence request of highest positive EVSI (if policy permits it) unless the current decision is
already stable across the bootstrap posterior (stability >= threshold) *and* no evidence is worth its cost.
Everything computed here is written to the case so the explanation can quote it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from verdict.policy.engine import PolicyEngine
from verdict.scoring.ledger import Assessment, EvidenceModel


@dataclass
class VoiOption:
    kind: str
    action: str
    evsi: float
    cost: float
    outcomes: list[dict] = field(default_factory=list)  # [{response, prob, p_after, decision_after}]

    def to_dict(self):
        return {"kind": self.kind, "action": self.action, "evsi": round(self.evsi, 2), "cost": round(self.cost, 2),
                "outcomes": self.outcomes}


@dataclass
class Decision:
    decision: str
    p: float
    ci: tuple[float, float]
    stability: float
    expected_loss: dict
    voi: list[VoiOption]
    chosen_evidence: VoiOption | None
    reason: str

    def to_dict(self):
        return {"decision": self.decision, "p_fraud": round(self.p, 4), "ci80": [round(self.ci[0], 4), round(self.ci[1], 4)],
                "decision_stability": round(self.stability, 3), "expected_loss": {k: round(v, 2) for k, v in self.expected_loss.items()},
                "voi": [v.to_dict() for v in self.voi], "chosen_evidence": self.chosen_evidence.to_dict() if self.chosen_evidence else None,
                "reason": self.reason}


class NbaEngine:
    def __init__(self, model: EvidenceModel, policy: PolicyEngine):
        self.model = model
        self.policy = policy
        self.loss = policy.p.get("loss", {})
        self.costs = policy.p.get("evidence_costs", {})
        self.stop = policy.p.get("stopping", {}).get("stability_to_act", 0.9)

    # ------------------------------------------------------------------ losses
    def exposure(self, facts: dict) -> float:
        return max(float(facts.get("amount_at_risk") or facts.get("amount") or 0), 1.0) * (1 + self.loss.get("follow_on_loss_factor", 0.5))

    def c_fp(self, facts: dict) -> float:
        return self.loss.get("false_positive_base", 25) + self.loss.get("false_positive_pct", 0.02) * float(facts.get("amount") or 0)

    def _el(self, p, facts):
        return {"PROTECT": (1 - p) * self.c_fp(facts), "RELEASE": p * self.exposure(facts)}

    def _best(self, p, facts) -> tuple[str, float]:
        el = self._el(p, facts)
        a = min(el, key=el.get)
        return a, el[a]

    # --------------------------------------------------------------------- VOI
    def voi(self, assessment: Assessment, facts: dict, used: set[str]) -> list[VoiOption]:
        p = assessment.p
        _, el_now = self._best(p, facts)
        opts = []
        for kind, lk in self.model.ev_lik.items():
            action = self.policy.evidence_action_for(kind)
            if kind in used or not action:
                continue
            outs, exp_el = [], 0.0
            for resp, pf in lk["fraud"].items():
                pl = lk["legit"][resp]
                po = p * pf + (1 - p) * pl
                lo = math.log(p / (1 - p)) + math.log(pf / pl) if 0 < p < 1 else (50 if p >= 1 else -50)
                pa = 1 / (1 + math.exp(-lo))
                d, el = self._best(pa, facts)
                exp_el += po * el
                outs.append({"response": resp, "prob": round(po, 3), "p_after": round(pa, 4), "decision_after": d})
            c = self.costs.get(kind, {"fixed": 10, "exposure_pct": 0.05})
            cost = c["fixed"] + c["exposure_pct"] * p * self.exposure(facts)
            opts.append(VoiOption(kind, action, el_now - exp_el - cost, cost, outs))
        return sorted(opts, key=lambda o: -o.evsi)

    def decide(self, assessment: Assessment, facts: dict, used: set[str], allow_gather: bool = True) -> Decision:
        p = assessment.p
        best, _ = self._best(p, facts)
        # stability: share of posterior samples that agree with the point decision
        samples = assessment.samples if len(assessment.samples) else np.array([p])
        agree = np.mean([self._best(float(s), facts)[0] == best for s in samples])
        opts = self.voi(assessment, facts, used) if allow_gather else []
        top = opts[0] if opts and opts[0].evsi > 0 else None
        el = self._el(p, facts)
        if top and not (agree >= self.stop and top.evsi <= 0):
            # gather only if the evidence could change the decision under some outcome
            flips = any(o["decision_after"] != best for o in top.outcomes)
            if flips:
                reason = (f"Evidence {top.kind} is worth requesting: EVSI ${top.evsi:.2f} > 0 after its cost ${top.cost:.2f}; "
                          + "; ".join(f"{o['response']} (p={o['prob']:.2f}) -> P(fraud)={o['p_after']:.2f} -> {o['decision_after']}" for o in top.outcomes))
                return Decision("GATHER", p, assessment.ci, float(agree), el, opts, top, reason)
        facts_p = {**facts, "p_fraud": p}
        ov = self.policy.decision_override(facts_p) if not allow_gather or used else None
        if ov and ov["decision"] != best:
            reason = (f"Policy {ov['id']} sets the decision to {ov['decision']} given the evidence received "
                      f"(loss model alone preferred {best}: PROTECT ${el['PROTECT']:.2f} vs RELEASE ${el['RELEASE']:.2f}).")
            return Decision(ov["decision"], p, assessment.ci, float(agree), el, opts, None, reason)
        reason = (f"Stop and act: best decision {best} (expected loss PROTECT ${el['PROTECT']:.2f} vs RELEASE ${el['RELEASE']:.2f}); "
                  f"decision stability {agree:.0%}; " + ("no evidence request has positive value of information." if not top else
                                                         f"top evidence {top.kind} would not change the decision."))
        return Decision(best, p, assessment.ci, float(agree), el, opts, None, reason)
