from .llm import generate_answer
from .models import DocumentChunk
from .utils import chunk_pages, extract_pdf_pages
from .vector_store import add_chunks, search_chunks


def index_document(document):
    pages = extract_pdf_pages(document.pdf.path)
    chunks = chunk_pages(pages)
    add_chunks(document.id, chunks, filename=document.pdf.name)
    DocumentChunk.objects.filter(document=document).delete()
    DocumentChunk.objects.bulk_create([
        DocumentChunk(
            document=document,
            chunk_number=index,
            text=chunk["text"],
        )
        for index, chunk in enumerate(chunks, start=1)
    ])
    return pages, chunks


def answer_question(question, document_id):
    results = search_chunks(question, document_id=document_id, n_results=5)
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not documents:
        return {
            "answer": "I could not find relevant information in this document.",
            "sources": [],
        }

    context = "\n\n".join(documents)
    answer = generate_answer(question, context)
    sources = [
        {
            "filename": metadata.get("filename", ""),
            "page_number": metadata.get("page_number"),
        }
        for metadata in metadatas
    ]

    return {"answer": answer, "sources": sources}