import json
from pathlib import Path

import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "chroma_db"
POSTMORTEMS_PATH = PROJECT_ROOT / "data" / "postmortems" / "postmortems.json"
COLLECTION_NAME = "postmortems"


def get_collection(client=None):
    """Return the postmortem collection, creating it if needed."""
    client = client or chromadb.PersistentClient(path=str(DEFAULT_DB_PATH))
    return client.get_or_create_collection(name=COLLECTION_NAME)


def _document_text(pm: dict) -> str:
    """The text that gets embedded: what happened, not how it was fixed."""
    return f"{pm['title']}. Symptoms: {pm['symptoms']}. Root cause: {pm['root_cause']}"


def seed_knowledge_base(collection=None, path: Path = POSTMORTEMS_PATH) -> int:
    """Load postmortems into the collection. Safe to run repeatedly (upsert)."""
    collection = collection or get_collection()
    postmortems = json.loads(Path(path).read_text(encoding="utf-8"))
    collection.upsert(
        ids=[pm["id"] for pm in postmortems],
        documents=[_document_text(pm) for pm in postmortems],
        metadatas=[
            {
                "title": pm["title"],
                "service": pm["service"],
                "root_cause": pm["root_cause"],
                "remediation_action": pm["remediation_action"],
                "resolution": pm["resolution"],
            }
            for pm in postmortems
        ],
    )
    return len(postmortems)


def search_similar_incidents(query: str, n_results: int = 3, collection=None) -> list[dict]:
    """Return the most similar past incidents, closest first."""
    collection = collection or get_collection()
    result = collection.query(query_texts=[query], n_results=n_results)
    return [
        {"id": incident_id, "distance": distance, **metadata}
        for incident_id, distance, metadata in zip(
            result["ids"][0], result["distances"][0], result["metadatas"][0]
        )
    ]