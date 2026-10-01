from documents.vector_store import add_chunks, search_chunks


chunks = [
    "Python is a programming language.",
    "Django is a Python web framework.",
    "Docker is used for containerization."
]


add_chunks(
    document_id=1,
    chunks=chunks
)


question = "Which framework is used to build web applications with Python?"

results = search_chunks(question)


print("\nRelevant chunks:")

for chunk in results["documents"][0]:
    print(chunk)