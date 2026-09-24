import pytest

from verdict.policy.engine import PolicyEngine, UnsafeExpression, evaluate


@pytest.fixture(scope="module")
def pe():
    from pathlib import Path
    return PolicyEngine(Path(__file__).parent.parent / "verdict" / "policy" / "policy.yaml")


def base(**kw):
    f = dict(p_fraud=0.9, pattern="CARD_TESTING", decision="PROTECT", phase="BEFORE_EVIDENCE", small_auths_1h=4,
             cleared_purchase_over_100=250.0, amount_at_risk=300.0, wider_compromise=False, undocumented_pattern=False,
             ring_detected=False, proxy=False, concurrent_home_activity=False)
    f.update(kw)
    return f


def test_evaluator_is_safe():
    assert evaluate("a > 1 and b in ('x', 'y')", {"a": 2, "b": "x"})
    with pytest.raises(UnsafeExpression):
        evaluate("__import__('os').system('true')", {})


def test_card_testing_steps_up_and_blocks(pe):
    codes = pe.evaluate(base()).codes()
    assert "STEP_UP_AUTH" in codes and "BLOCK_CARD" in codes


def test_block_all_cards_forbidden_without_wider_compromise(pe):
    d = pe.evaluate(base(pattern="ACCOUNT_TAKEOVER"), extra=[("BLOCK_ALL_CARDS", "agent thinks so")])
    assert "BLOCK_ALL_CARDS" not in d.codes()
    assert any(f["code"] == "BLOCK_ALL_CARDS" and f["clause"] == "POL-3.8" for f in d.forbidden)


def test_block_all_cards_allowed_with_wider_compromise(pe):
    assert "BLOCK_ALL_CARDS" in pe.evaluate(base(pattern="ACCOUNT_TAKEOVER", wider_compromise=True)).codes()


def test_block_card_route_escalates_with_amount(pe):
    assert pe.route("BLOCK_CARD", {"amount_at_risk": 100}) == "L1_ANALYST"
    assert pe.route("BLOCK_CARD", {"amount_at_risk": 5000}) == "L2_FRAUD_MANAGER"


def test_release_drops_protective_actions(pe):
    codes = pe.evaluate(base(decision="RELEASE", p_fraud=0.05, pattern="NONE")).codes()
    assert "ALLOW_TRANSACTION" in codes and "BLOCK_CARD" not in codes


def test_customer_contact_before_block_for_out_of_region(pe):
    d = pe.evaluate(base(pattern="OUT_OF_REGION", concurrent_home_activity=True, p_fraud=0.85))
    assert "CONTACT_CUSTOMER" in d.codes() and "BLOCK_CARD" not in d.codes()
    assert any(x["code"] == "BLOCK_CARD" for x in d.deferred)


def test_no_reply_declines_and_monitors(pe):
    codes = pe.evaluate(base(decision="PROTECT", phase="AFTER_EVIDENCE", CUSTOMER_VALIDATION="NO_REPLY", pattern="CNP_NEW_DEVICE")).codes()
    assert {"DECLINE_TRANSACTION", "MONITOR_CARD"} <= set(codes)


def test_sar_required_for_ring(pe):
    d = pe.evaluate(base(ring_detected=True, pattern="SHARED_ENTITY_RING"))
    assert d.sar_required and "FILE_REPORT" in d.codes()


def test_undocumented_pattern_cannot_be_auto_closed(pe):
    d = pe.evaluate(base(decision="RELEASE", phase="AFTER_EVIDENCE", p_fraud=0.05, undocumented_pattern=True))
    assert "CLOSE_NO_FRAUD" not in d.codes()


def test_unknown_agent_action_rejected(pe):
    d = pe.evaluate(base(), extra=[("FREEZE_EVERYTHING", "x")])
    assert any(f["code"] == "FREEZE_EVERYTHING" for f in d.forbidden)


def test_decision_override_on_confirmation(pe):
    assert pe.decision_override({"CUSTOMER_VALIDATION": "CONFIRMED", "p_fraud": 0.3, "undocumented_pattern": False})["decision"] == "RELEASE"
    assert pe.decision_override({"CUSTOMER_VALIDATION": "DENIED", "p_fraud": 0.1})["decision"] == "PROTECT"
