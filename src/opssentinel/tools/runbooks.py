import json
from pathlib import Path

from opssentinel.tools.knowledge_base import PROJECT_ROOT, get_collection

RUNBOOKS_PATH = PROJECT_ROOT / "data" / "runbooks" / "runbooks.json"
RUNBOOK_COLLECTION = "runbooks"


def _document_text(runbook: dict) -> str:
    """The text that gets embedded: when the procedure applies."""
    return f"{runbook['title']}. Applies when: {runbook['applies_when']}"


def _metadata(runbook: dict) -> dict:
    return {
        "title": runbook["title"],
        "action": runbook["action"],
        "steps": " | ".join(runbook["steps"]),
        "cautions": runbook["cautions"],
    }


def seed_runbooks(collection=None, path: Path = RUNBOOKS_PATH) -> int:
    """Load the runbooks. Safe to run repeatedly (upsert)."""
    if collection is None:
        collection = get_collection(name=RUNBOOK_COLLECTION)
    runbooks = json.loads(Path(path).read_text(encoding="utf-8"))
    collection.upsert(
        ids=[rb["id"] for rb in runbooks],
        documents=[_document_text(rb) for rb in runbooks],
        metadatas=[_metadata(rb) for rb in runbooks],
    )
    return len(runbooks)


def search_runbooks(query: str, n_results: int = 2, collection=None) -> list[dict]:
    """Return the most relevant runbooks, closest first."""
    if collection is None:
        collection = get_collection(name=RUNBOOK_COLLECTION)
    result = collection.query(query_texts=[query], n_results=n_results)
    return [
        {"id": runbook_id, "distance": distance, **metadata}
        for runbook_id, distance, metadata in zip(
            result["ids"][0], result["distances"][0], result["metadatas"][0]
        )
    ]