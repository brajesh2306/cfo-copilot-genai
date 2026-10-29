from pathlib import Path
from functools import lru_cache

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"

CORPUS_FILES = [
    DATA_DIR / "puzzle1_data" / "corpus_documents.csv",
    DATA_DIR / "drop2" / "data" / "corpus_documents_new.csv",
]

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def load_documents():
    frames = []

    for path in CORPUS_FILES:
        if path.exists():
            frames.append(pd.read_csv(path).fillna(""))

    if not frames:
        raise FileNotFoundError("No corpus CSV files were found.")

    documents = pd.concat(frames, ignore_index=True)

    required = {
        "doc_id", "doc_type", "company_id", "form_type",
        "fiscal_year", "fiscal_quarter", "filed_date", "title", "text",
    }
    missing = required - set(documents.columns)

    if missing:
        raise ValueError(f"Corpus is missing columns: {sorted(missing)}")

    documents = documents.drop_duplicates(
        subset=["doc_id"], keep="last"
    )

    return documents.to_dict(orient="records")


def split_text(text):
    text = str(text).strip()
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))

        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(end - CHUNK_OVERLAP, start + 1)

    return chunks


@lru_cache(maxsize=1)
def get_retriever():
    documents = load_documents()
    chunks = []

    for doc in documents:
        for number, chunk in enumerate(split_text(doc["text"])):
            chunks.append({
                "chunk_id": f'{doc["doc_id"]}::chunk-{number}',
                "doc_id": str(doc["doc_id"]),
                "doc_type": str(doc["doc_type"]),
                "company_id": str(doc["company_id"]),
                "form_type": str(doc["form_type"]),
                "fiscal_year": str(int(float(doc["fiscal_year"]))) if str(doc["fiscal_year"]).strip() else "",
                "fiscal_quarter": str(int(float(doc["fiscal_quarter"]))) if str(doc["fiscal_quarter"]).strip() else "",
                "filed_date": str(doc["filed_date"]),
                "title": str(doc["title"]),
                "text": chunk,
            })

    if not chunks:
        raise ValueError("Corpus contains no retrievable text.")

    model = SentenceTransformer(MODEL_NAME)

    embeddings = model.encode(
        [item["text"] for item in chunks],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=32,
    ).astype("float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    return model, index, chunks, len(documents)


def retrieve(
    query,
    company_id=None,
    fiscal_year=None,
    fiscal_quarter=None,
    top_k=5,
):
    query = str(query).strip()

    if not query:
        return []

    if top_k < 1 or top_k > 20:
        raise ValueError("top_k must be between 1 and 20.")

    model, index, chunks, _ = get_retriever()

    query_vector = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).astype("float32")

    search_k = len(chunks)
    scores, indices = index.search(query_vector, search_k)

    results = []

    for score, position in zip(scores[0], indices[0]):
        if position < 0:
            continue

        item = chunks[int(position)]

        if company_id and item["company_id"] != company_id:
            continue
        if fiscal_year is not None and item["fiscal_year"] != str(fiscal_year):
            continue
        if fiscal_quarter is not None and item["fiscal_quarter"] != str(fiscal_quarter):
            continue

        results.append({
            **item,
            "similarity": float(score),
        })

        if len(results) >= top_k:
            break

    return results


def corpus_stats():
    _, index, chunks, document_count = get_retriever()

    return {
        "document_count": document_count,
        "chunk_count": len(chunks),
        "embedding_dimension": index.d,
        "index_type": type(index).__name__,
        "model": MODEL_NAME,
    }
