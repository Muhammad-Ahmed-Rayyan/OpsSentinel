import json
from pathlib import Path

import chromadb
import pytest

from opssentinel.actions import ACTION_CATALOG
from opssentinel.tools.knowledge_base import get_collection
from opssentinel.tools.runbooks import search_runbooks, seed_runbooks

RUNBOOKS_PATH = Path(__file__).resolve().parent.parent / "data" / "runbooks" / "runbooks.json"


def load_runbooks():
    return json.loads(RUNBOOKS_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def collection():
    col = get_collection(chromadb.EphemeralClient(), name="runbooks_test")
    seed_runbooks(col)
    return col


def test_every_catalog_action_has_exactly_one_runbook():
    actions = [runbook["action"] for runbook in load_runbooks()]

    assert sorted(actions) == sorted(ACTION_CATALOG)


def test_every_runbook_has_steps_and_cautions():
    for runbook in load_runbooks():
        assert runbook["steps"], runbook["id"]
        assert runbook["cautions"].strip(), runbook["id"]


@pytest.mark.integration
def test_seeding_runbooks_twice_does_not_duplicate(collection):
    seed_runbooks(collection)

    assert collection.count() == 6


@pytest.mark.integration
def test_deployment_regression_finds_the_rollback_runbook(collection):
    results = search_runbooks(
        "error rate spiked within minutes of a deployment, errors from the new release",
        collection=collection,
    )

    assert "RB-001" in [result["id"] for result in results]


@pytest.mark.integration
def test_full_log_volume_finds_the_cleanup_runbook(collection):
    results = search_runbooks(
        "disk usage rising, log rotation failed, no space left on device",
        collection=collection,
    )

    assert "RB-002" in [result["id"] for result in results]