import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from documents.models import Document
from unittest.mock import patch

from .models import ChatMessage


class ChatApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="chatstudent",
            password="Secure-Test-Password-934!",
        )
        self.client.force_login(self.user)

    def test_chat_lists_other_uploaded_documents(self):
        current = Document.objects.create(
            owner=self.user,
            title="Current PDF",
            pdf="pdfs/current.pdf",
        )
        saved = Document.objects.create(
            owner=self.user,
            title="Earlier PDF",
            pdf="pdfs/earlier.pdf",
        )

        response = self.client.get(reverse("ask_pdf", args=[current.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Earlier PDF")
        self.assertContains(response, reverse("ask_pdf", args=[saved.id]))

    @patch("chat.views.extract_pdf_pages")
    def test_guest_pdf_upload_is_temporary_and_not_saved(self, mock_extract):
        mock_extract.return_value = [{"page_number": 1, "text": "Temporary PDF context."}]
        self.client.logout()
        pdf = SimpleUploadedFile(
            "guest.pdf",
            b"%PDF-1.4\n%%EOF",
            content_type="application/pdf",
        )

        response = self.client.post(reverse("guest_pdf_upload"), {"pdf": pdf})

        temporary_path = Path(mock_extract.call_args.args[0])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["filename"], "guest.pdf")
        self.assertIn("Temporary PDF context.", response.json()["context"])
        self.assertFalse(temporary_path.exists())
        self.assertFalse(Document.objects.exists())

    @patch("chat.views.generate_answer", return_value="Temporary answer.")
    def test_guest_chat_does_not_save_conversation(self, mock_generate_answer):
        self.client.logout()

        response = self.client.post(
            reverse("chat_api"),
            data=json.dumps({
                "question": "What is in this PDF?",
                "context": "Temporary PDF context.",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Temporary answer.")
        self.assertFalse(ChatMessage.objects.exists())
        mock_generate_answer.assert_called_once_with(
            "What is in this PDF?",
            "Temporary PDF context.",
        )

    @patch("chat.views.answer_question", return_value={"answer": "Saved answer.", "sources": []})
    def test_signed_in_chat_is_saved_and_restored(self, mock_answer_question):
        document = Document.objects.create(
            owner=self.user,
            title="History PDF",
            pdf="pdfs/history.pdf",
        )

        response = self.client.post(
            reverse("chat_api"),
            data=json.dumps({
                "question": "Saved question?",
                "document_id": document.id,
            }),
            content_type="application/json",
        )

        saved_message = ChatMessage.objects.get(document=document)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(saved_message.question, "Saved question?")
        self.assertEqual(saved_message.answer, "Saved answer.")

        chat_page = self.client.get(reverse("ask_pdf", args=[document.id]))
        self.assertContains(chat_page, "saved-chat-history")
        self.assertContains(chat_page, "Saved question?")

    def test_user_cannot_open_another_users_document(self):
        other_user = get_user_model().objects.create_user(
            username="otherstudent",
            password="Secure-Test-Password-934!",
        )
        document = Document.objects.create(
            owner=other_user,
            title="Private PDF",
            pdf="pdfs/private.pdf",
        )

        response = self.client.get(reverse("ask_pdf", args=[document.id]))

        self.assertEqual(response.status_code, 404)

    def test_chat_api_cannot_search_another_users_document(self):
        other_user = get_user_model().objects.create_user(
            username="otherstudent",
            password="Secure-Test-Password-934!",
        )
        document = Document.objects.create(
            owner=other_user,
            title="Private PDF",
            pdf="pdfs/private.pdf",
        )

        response = self.client.post(
            reverse("chat_api"),
            data=json.dumps({"question": "What is in this PDF?", "document_id": document.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "The requested document does not exist.")

    def test_guest_chat_api_requires_temporary_pdf_context(self):
        self.client.logout()

        response = self.client.post(
            reverse("chat_api"),
            data=json.dumps({"question": "What is in this PDF?"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Upload a PDF before starting a guest chat.")

    def test_empty_question_returns_json_error(self):
        response = self.client.post(
            reverse("chat_api"),
            data=json.dumps({"question": " "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Question cannot be empty.")

    def test_chat_without_document_returns_json_error(self):
        response = self.client.post(
            reverse("chat_api"),
            data=json.dumps({"question": "What is this PDF about?"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "Upload a PDF before asking a question.")
