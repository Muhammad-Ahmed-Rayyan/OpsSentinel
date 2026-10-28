import pytest

from opssentinel.agents.review import build_review_request, normalize_review


def test_confirmed_review_is_kept():
    review = normalize_review({"decision": "confirmed", "reviewer": "tester", "comment": " good "})

    assert review == {
        "decision": "confirmed",
        "reviewer": "tester",
        "comment": "good",
        "corrected_root_cause": "",
    }


def test_correction_keeps_the_corrected_root_cause():
    review = normalize_review(
        {"decision": "corrected", "reviewer": "tester", "corrected_root_cause": "  Bad config push  "}
    )

    assert review["decision"] == "corrected"
    assert review["corrected_root_cause"] == "Bad config push"


@pytest.mark.parametrize(
    "response",
    [
        None,
        "yes",
        {},
        {"decision": "maybe"},
        {"decision": "corrected", "corrected_root_cause": "   "},
    ],
)
def test_unclear_answers_are_treated_as_skipped(response):
    assert normalize_review(response)["decision"] == "skipped"


def test_review_request_summarizes_diagnosis_action_and_proof():
    state = {
        "incident_id": "INC-REV",
        "hypotheses": [{"cause": "Bad release", "confidence": 0.9}],
        "proposed_action": {
            "action": "rollback_deployment",
            "parameters": {"service": "checkout-api"},
        },
        "verification": {"message": "error rate is 0.5"},
    }

    request = build_review_request(state)

    assert request["kind"] == "review"
    assert request["likely_cause"] == "Bad release"
    assert "rollback_deployment" in request["action_taken"]
    assert request["verification"] == "error rate is 0.5"