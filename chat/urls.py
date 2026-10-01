from django.urls import path
from .views import ask_pdf, chat_api, guest_pdf_upload


urlpatterns = [
    path("", chat_api, name="chat_api"),
    path("guest-upload/", guest_pdf_upload, name="guest_pdf_upload"),
    path(
        "ask/<int:document_id>/",
        ask_pdf,
        name="ask_pdf"
    ),
]