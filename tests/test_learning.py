import chromadb
import pytest

from opssentinel.tools.knowledge_base import (
    add_postmortem,
    get_collection,
    search_similar_incidents,
    seed_knowledge_base,
)

pytestmark = pytest.mark.integration

NEW_RECORD = {
    "id": "PM-INC-NEW",
    "title": "Search indexer falling behind",
    "service": "search-indexer",
    "symptoms": "message queue depth growing steadily; consumer workers idle; "
    "no errors in logs; indexing lag rising",
    "root_cause": "Consumer workers deadlocked after a lock timeout",
    "remediation_action": "restart_service",
    "resolution": "Restarted the indexer workers; queue drained in 4 minutes",
    "source": "incident",
    "approved_by": "tester",
}


@pytest.fixture
def collection():
    col = get_collection(chromadb.EphemeralClient(), name="learning_test")
    seed_knowledge_base(col)
    return col


def test_learned_incident_is_retrievable_with_its_source(collection):
    add_postmortem(NEW_RECORD, collection)
    results = search_similar_incidents(
        "queue depth growing, workers idle, indexing lag rising", collection=collection
    )

    assert results[0]["id"] == "PM-INC-NEW"
    assert results[0]["source"] == "incident"
    assert results[0]["approved_by"] == "tester"


def test_learning_the_same_incident_twice_does_not_duplicate(collection):
    add_postmortem(NEW_RECORD, collection)
    add_postmortem(NEW_RECORD, collection)

    assert collection.count() == 8