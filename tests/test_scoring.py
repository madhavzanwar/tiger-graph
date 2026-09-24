import numpy as np

from verdict.outputs.claim_checker import check
from verdict.policy.engine import PolicyEngine
from verdict.scoring.ledger import Assessment
from verdict.scoring.nba import NbaEngine


class FakeModel:
    ev_lik = {"CUSTOMER_VALIDATION": {"fraud": {"CONFIRMED": 0.05, "DENIED": 0.74, "NO_REPLY": 0.21},
                                      "legit": {"CONFIRMED": 0.75, "DENIED": 0.07, "NO_REPLY": 0.18}}}


def _a(p, spread=0.05):
    return Assessment(p=p, ci=(p - spread, p + spread), samples=np.clip(np.random.default_rng(0).normal(p, spread, 200), 0.001, 0.999), rows=[])


def nba():
    return NbaEngine(FakeModel(), PolicyEngine())


def test_clear_fraud_acts_without_evidence():
    d = nba().decide(_a(0.99, 0.005), {"amount": 500, "amount_at_risk": 500}, used=set())
    assert d.decision == "PROTECT" and d.chosen_evidence is None


def test_clear_legit_releases():
    d = nba().decide(_a(0.01, 0.005), {"amount": 50, "amount_at_risk": 50}, used=set())
    assert d.decision == "RELEASE"


def test_ambiguous_case_gathers_evidence_that_can_flip_the_decision():
    d = nba().decide(_a(0.5, 0.15), {"amount": 150, "amount_at_risk": 150}, used=set())
    assert d.decision == "GATHER" and d.chosen_evidence.kind == "CUSTOMER_VALIDATION"
    decisions = {o["decision_after"] for o in d.chosen_evidence.outcomes}
    assert decisions == {"PROTECT", "RELEASE"}


def test_no_gathering_when_evidence_already_used():
    d = nba().decide(_a(0.5, 0.15), {"amount": 150, "amount_at_risk": 150}, used={"CUSTOMER_VALIDATION"})
    assert d.decision in ("PROTECT", "RELEASE")


def test_claim_checker_flags_invented_numbers_and_ids():
    ev = {"amount": 211.06, "card_id": "CARD-000543", "p": 0.93}
    assert check("Card CARD-000543 charged $211.06, P(fraud) 0.93 (93%).", ev) == []
    bad = check("Card CARD-999999 charged $5,000.00.", ev)
    assert "CARD-999999" in bad and "$5,000.00" in bad
