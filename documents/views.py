from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.shortcuts import redirect, render

from .models import Document
from .rag import index_document


def signup(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            if not get_user_model().objects.exclude(pk=user.pk).exists():
                Document.objects.filter(owner__isnull=True).update(owner=user)
        login(request, user)
        return redirect("home")

    return render(request, "auth.html", {"form": form, "mode": "signup"})


def home(request):
    if not request.user.is_authenticated:
        if request.method == "POST":
            return redirect("login")
        return render(request, "ask_pdf.html", {"document": None, "documents": []})

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        pdf = request.FILES.get("pdf")

        if not pdf:
            messages.error(request, "Please choose a PDF file.")
            return redirect("home")

        if not pdf.name.lower().endswith(".pdf"):
            messages.error(request, "Only PDF files are supported.")
            return redirect("home")

        document = Document.objects.create(
            owner=request.user,
            title=title or pdf.name,
            pdf=pdf,
        )

        try:
            pages, _chunks = index_document(document)
            document.extracted_text = "\n\n".join(page["text"] for page in pages)
            document.save(update_fields=["extracted_text"])
        except Exception as error:
            document.delete()
            messages.error(request, str(error))
            return redirect("home")

        messages.success(request, "PDF uploaded and indexed successfully.")
        return redirect("home")

    documents = Document.objects.filter(owner=request.user).order_by("-uploaded_at")
    document = documents.first()
    if document:
        return render(
            request,
            "ask_pdf.html",
            {"document": document, "documents": documents.exclude(pk=document.pk)},
        )

    return render(request, "ask_pdf.html", {"document": None, "documents": []})