import json
from pathlib import Path

from opssentinel.actions import ACTION_CATALOG

POSTMORTEMS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "postmortems" / "postmortems.json"
)


def test_every_action_has_a_valid_risk_tier():
    assert all(spec.risk_tier in {"low", "high"} for spec in ACTION_CATALOG.values())


def test_actions_that_touch_live_traffic_are_high_risk():
    for name in ("rollback_deployment", "restart_service", "scale_up_service"):
        assert ACTION_CATALOG[name].risk_tier == "high"
    assert ACTION_CATALOG["escalate_to_human"].required_params == ()


def test_postmortems_only_reference_catalog_actions():
    postmortems = json.loads(POSTMORTEMS_PATH.read_text(encoding="utf-8"))
    assert all(pm["remediation_action"] in ACTION_CATALOG for pm in postmortems)