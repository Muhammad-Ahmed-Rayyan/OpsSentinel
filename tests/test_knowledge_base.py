import chromadb
import pytest

from opssentinel.tools.knowledge_base import (
    get_collection,
    search_similar_incidents,
    seed_knowledge_base,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def collection():
    col = get_collection(chromadb.EphemeralClient())
    seed_knowledge_base(col)
    return col


def test_seeding_twice_does_not_duplicate(collection):
    seed_knowledge_base(collection)
    assert collection.count() == 7


def test_deployment_regression_query_finds_rollback_incident(collection):
    results = search_similar_incidents(
        "5xx error rate 38% NullPointerException PaymentValidator right after deployment",
        collection=collection,
    )
    assert "PM-001" in [r["id"] for r in results[:2]]


def test_disk_query_finds_log_rotation_incident(collection):
    results = search_similar_incidents(
        "disk usage above 95% log rotation failed no space left on device",
        collection=collection,
    )
    assert "PM-002" in [r["id"] for r in results[:2]]