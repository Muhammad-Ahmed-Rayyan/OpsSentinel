import json
from pathlib import Path

import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "chroma_db"
POSTMORTEMS_PATH = PROJECT_ROOT / "data" / "postmortems" / "postmortems.json"
COLLECTION_NAME = "postmortems"


def get_collection(client=None, name: str = COLLECTION_NAME):
    """Return a postmortem collection, creating it if needed."""
    if client is None:
        client = chromadb.PersistentClient(path=str(DEFAULT_DB_PATH))
    return client.get_or_create_collection(name=name)


def _document_text(pm: dict) -> str:
    """The text that gets embedded: what happened, not how it was fixed."""
    return f"{pm['title']}. Symptoms: {pm['symptoms']}. Root cause: {pm['root_cause']}"


def _metadata(pm: dict) -> dict:
    return {
        "title": pm["title"],
        "service": pm["service"],
        "root_cause": pm["root_cause"],
        "remediation_action": pm["remediation_action"],
        "resolution": pm["resolution"],
        "source": pm.get("source", "seed"),
        "approved_by": pm.get("approved_by", ""),
    }


def add_postmortem(record: dict, collection=None) -> None:
    """Add or update one postmortem. Re-adding the same id replaces it."""
    if collection is None:
        collection = get_collection()
    collection.upsert(
        ids=[record["id"]],
        documents=[_document_text(record)],
        metadatas=[_metadata(record)],
    )


def seed_knowledge_base(collection=None, path: Path = POSTMORTEMS_PATH) -> int:
    """Load the seed postmortems. Safe to run repeatedly (upsert) and it leaves
    learned incidents untouched."""
    if collection is None:
        collection = get_collection()
    postmortems = json.loads(Path(path).read_text(encoding="utf-8"))
    collection.upsert(
        ids=[pm["id"] for pm in postmortems],
        documents=[_document_text(pm) for pm in postmortems],
        metadatas=[_metadata(pm) for pm in postmortems],
    )
    return len(postmortems)


def search_similar_incidents(query: str, n_results: int = 3, collection=None) -> list[dict]:
    """Return the most similar past incidents, closest first."""
    if collection is None:
        collection = get_collection()
    result = collection.query(query_texts=[query], n_results=n_results)
    return [
        {"id": incident_id, "distance": distance, **metadata}
        for incident_id, distance, metadata in zip(
            result["ids"][0], result["distances"][0], result["metadatas"][0]
        )
    ]