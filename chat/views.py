import re
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from documents.llm import generate_answer
from documents.models import Document
from documents.rag import answer_question
from documents.utils import extract_pdf_pages
from .models import ChatMessage


MAX_GUEST_PDF_BYTES = 10 * 1024 * 1024
MAX_GUEST_CONTEXT_CHARS = 100_000


def extract_name_from_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines[:10]:
        if len(line.split()) > 2:
            continue
        if any(token in line.lower() for token in ["python", "developer", "resume", "summary", "skills", "experience", "project", "education", "contact", "linkedin", "github", "email", "phone"]):
            continue
        if re.fullmatch(r"[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+)+", line):
            return line

    return None


def extract_section_from_text(text, keywords):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    section = []
    in_section = False

    for line in lines:
        lower = line.lower()
        if any(keyword in lower for keyword in keywords):
            in_section = True
            section.append(line)
            continue

        if in_section:
            if any(next_heading in lower for next_heading in [
                "professional summary",
                "technical skills",
                "professional experience",
                "projects",
                "certifications",
                "soft skills",
                "summary",
                "skills",
                "experience",
            ]):
                break
            section.append(line)

    return "\n".join(section[:20]).strip()


@login_required
def ask_pdf(request, document_id):
    document = get_object_or_404(Document, id=document_id, owner=request.user)
    answer = None
    question = None

    if request.method == "POST":
        question = (request.POST.get("question") or "").strip()

        if question:
            try:
                answer = answer_question(question, document.id)["answer"]
            except Exception:
                answer = "I could not answer that question right now. Please try again."

    return render(
        request,
        "ask_pdf.html",
        {
            "document": document,
            "documents": Document.objects.filter(owner=request.user).exclude(
                pk=document.pk
            ).order_by("-uploaded_at"),
            "chat_history": list(
                document.chat_messages.order_by("created_at").values("question", "answer")
            ),
            "question": question,
            "answer": answer,
        },
    )


def guest_pdf_upload(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests are supported."}, status=405)

    pdf = request.FILES.get("pdf")
    if not pdf or not pdf.name.lower().endswith(".pdf"):
        return JsonResponse({"error": "Choose a PDF file to start a temporary chat."}, status=400)
    if pdf.size > MAX_GUEST_PDF_BYTES:
        return JsonResponse({"error": "Guest PDFs must be 10 MB or smaller."}, status=413)

    try:
        with TemporaryDirectory(prefix="smartstudy-guest-") as temp_dir:
            temp_path = Path(temp_dir) / "guest.pdf"
            with temp_path.open("wb") as temp_file:
                for chunk in pdf.chunks():
                    temp_file.write(chunk)
            pages = extract_pdf_pages(str(temp_path))
    except Exception:
        return JsonResponse({"error": "Could not read this PDF. Try a text-based PDF."}, status=400)

    if len(pages) > 100:
        return JsonResponse({"error": "Guest PDFs can contain up to 100 text pages."}, status=413)

    context = "\n\n".join(
        f"[Page {page['page_number']}]\n{page['text']}" for page in pages
    )[:MAX_GUEST_CONTEXT_CHARS]
    return JsonResponse({
        "filename": Path(pdf.name).name,
        "context": context,
        "page_count": len(pages),
    })


def chat_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests are supported."}, status=405)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    question = (payload.get("question") or "").strip()
    if not question:
        return JsonResponse({"error": "Question cannot be empty."}, status=400)

    if not request.user.is_authenticated:
        context = payload.get("context")
        if not isinstance(context, str) or not context.strip():
            return JsonResponse({"error": "Upload a PDF before starting a guest chat."}, status=400)
        if len(context) > MAX_GUEST_CONTEXT_CHARS:
            return JsonResponse({"error": "Guest PDF context is too large. Upload a smaller PDF."}, status=413)
        try:
            answer = generate_answer(question, context)
        except Exception:
            return JsonResponse({"error": "The guest PDF could not be answered right now."}, status=503)
        return JsonResponse({"question": question, "answer": answer, "sources": []})

    document_id = payload.get("document_id")
    if document_id:
        document = Document.objects.filter(id=document_id, owner=request.user).first()
        if document is None:
            return JsonResponse({"error": "The requested document does not exist."}, status=404)
    else:
        document = Document.objects.filter(owner=request.user).order_by("-uploaded_at").first()
    if document is None:
        return JsonResponse({"error": "Upload a PDF before asking a question."}, status=404)

    try:
        result = answer_question(question, document.id)
    except Exception:
        return JsonResponse({"error": "The PDF could not be searched right now."}, status=503)

    ChatMessage.objects.create(
        document=document,
        question=question,
        answer=result["answer"],
    )

    return JsonResponse({
        "question": question,
        "answer": result["answer"],
        "sources": result["sources"],
    })