import pytest

from opssentinel.agents.approval import normalize_approval

STATE = {
    "proposed_action": {"action": "rollback_deployment"},
    "alternatives": [
        {"action": "restart_service", "risk_tier": "high"},
        {"action": "clear_cache", "risk_tier": "low"},
    ],
}


def answer(**fields):
    return {"decision": "approved", "reviewer": "tester", "comment": "", **fields}


def test_plain_approval_means_option_one():
    approval = normalize_approval(STATE, answer())

    assert approval["decision"] == "approved"
    assert approval["option"] == 1


def test_approval_can_choose_an_alternative():
    approval = normalize_approval(STATE, answer(option=2))

    assert approval["decision"] == "approved"
    assert approval["option"] == 2


@pytest.mark.parametrize("option", [0, 4, "2", True, 2.0])
def test_an_unclear_option_is_a_rejection_not_a_default_approval(option):
    approval = normalize_approval(STATE, answer(option=option))

    assert approval["decision"] == "rejected"
    assert approval["option"] is None


def test_a_rejection_never_carries_a_choice():
    approval = normalize_approval(STATE, {"decision": "rejected", "option": 2})

    assert approval["decision"] == "rejected"
    assert approval["option"] is None