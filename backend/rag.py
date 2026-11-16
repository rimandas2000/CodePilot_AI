"""Optional ChromaDB retrieval with an offline local-notes fallback."""
from functools import lru_cache
from pathlib import Path
import re

DB_PATH = Path(__file__).resolve().parent.parent / "chroma_db"
KNOWLEDGE = Path(__file__).resolve().parent / "knowledge"
COLLECTION_NAME = "coding_knowledge"


@lru_cache(maxsize=1)
def get_collection():
    # Optional: a missing/broken vector dependency must not stop app startup.
    import chromadb
    client = chromadb.PersistentClient(path=str(DB_PATH))
    return client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def _local_notes(query, n_results):
    words = set(re.findall(r"[a-z0-9_]+", query.lower()))
    scored = []
    for path in KNOWLEDGE.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        score = len(words & set(re.findall(r"[a-z0-9_]+", text.lower())))
        if score:
            scored.append((score, path.name, text))
    return [{"text": text, "source": name} for _, name, text in sorted(scored, key=lambda row: (-row[0], row[1]))[:n_results]]


def retrieve(query: str, n_results: int = 5):
    try:
        limit = min(max(int(n_results), 1), 20)
    except (TypeError, ValueError):
        limit = 5
    # Do not trigger embedding model downloads on installations that have not
    # opted into vector RAG. Ordinary cloud/local AI works fully offline here.
    try:
        if (DB_PATH / "chroma.sqlite3").exists():
            collection = get_collection()
            count = collection.count()
            if count:
                result = collection.query(query_texts=[query], n_results=min(limit, count))
                docs = (result.get("documents") or [[]])[0]
                metas = (result.get("metadatas") or [[]])[0]
                return [{"text": doc, "source": (meta or {}).get("source", "Unknown")}
                        for doc, meta in zip(docs, metas)]
    except Exception:
        pass
    return _local_notes(query, limit)
