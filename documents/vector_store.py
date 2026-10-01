import os

import chromadb

from .embeddings import embed_texts


client = chromadb.PersistentClient(
    path=os.getenv("CHROMA_DB_DIR", "chroma_db")
)

collection = client.get_or_create_collection(
    name="smartstudy_documents"
)

def add_chunks(document_id, chunks, filename=""):
    if not chunks:
        return

    collection.delete(where={"document_id": document_id})

    normalized_chunks = [
        chunk if isinstance(chunk, dict) else {"text": chunk, "page_number": 1}
        for chunk in chunks
    ]
    texts = [chunk["text"] for chunk in normalized_chunks]
    embeddings = embed_texts(texts)
    ids = []
    metadatas = []

    for index, chunk in enumerate(normalized_chunks):
        ids.append(f"document_{document_id}_chunk_{index + 1}")
        metadatas.append({
            "document_id": document_id,
            "filename": filename,
            "page_number": chunk["page_number"],
            "chunk_number": index + 1,
        })

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def search_chunks(question, n_results=3, document_id=None):
    question_embedding = embed_texts([question])
    query_kwargs = {
        "query_embeddings": question_embedding,
        "n_results": n_results,
    }

    if document_id is not None:
        query_kwargs["where"] = {"document_id": document_id}

    results = collection.query(**query_kwargs)

    return results