import re

from pypdf import PdfReader


def extract_pdf_pages(pdf_path):
    reader = PdfReader(pdf_path)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page_number": page_number, "text": text})

    if not pages:
        raise ValueError("This PDF does not contain extractable text.")

    return pages


def chunk_pages(pages, chunk_size=900, overlap=120):
    chunks = []

    for page in pages:
        words = re.findall(r"\S+", page["text"])
        start = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            text = " ".join(words[start:end]).strip()

            if text:
                chunks.append({
                    "text": text,
                    "page_number": page["page_number"],
                })

            if end == len(words):
                break
            start = max(end - overlap, start + 1)

    return chunks