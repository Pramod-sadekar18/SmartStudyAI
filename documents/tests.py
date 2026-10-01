from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from .models import Document
from .vector_store import add_chunks, search_chunks


class HomeUploadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="studyuser",
            password="Secure-Test-Password-934!",
        )
        self.client.force_login(self.user)

    def test_empty_workspace_renders_chat_upload_page(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ask_pdf.html")
        self.assertContains(response, "Upload a PDF to open your study chat.")

    def test_home_renders_existing_document_chat_at_root(self):
        document = Document.objects.create(
            owner=self.user,
            title="Saved PDF",
            pdf="pdfs/saved.pdf",
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.path, "/")
        self.assertTemplateUsed(response, "ask_pdf.html")
        self.assertContains(response, document.title)

    def test_upload_pdf_without_text_is_rejected(self):
        pdf = SimpleUploadedFile(
            "sample.pdf",
            b"%PDF-1.4\n%%EOF",
            content_type="application/pdf",
        )

        response = self.client.post(reverse("home"), {"title": "Sample PDF", "pdf": pdf})

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(Document.objects.filter(title="Sample PDF").exists())

    @patch("documents.views.index_document")
    def test_successful_upload_returns_to_chat_at_root(self, mock_index_document):
        mock_index_document.return_value = ([{"text": "Sample content"}], [])
        pdf = SimpleUploadedFile(
            "sample.pdf",
            b"%PDF-1.4\n%%EOF",
            content_type="application/pdf",
        )

        response = self.client.post(reverse("home"), {"pdf": pdf})

        document = Document.objects.get(title="sample.pdf")
        self.assertEqual(document.extracted_text, "Sample content")
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        root_response = self.client.get(reverse("home"))
        self.assertEqual(root_response.wsgi_request.path, "/")
        self.assertContains(root_response, document.title)

    def test_search_is_limited_to_current_document(self):
        document_1_id = 910001
        document_2_id = 910002

        add_chunks(document_1_id, [
            "My name is Alice Johnson.",
            "I am a backend developer.",
        ])
        add_chunks(document_2_id, [
            "My name is Bob Smith.",
            "I am a designer.",
        ])

        results = search_chunks("My name is Alice Johnson.", document_id=document_1_id, n_results=3)
        documents = results["documents"][0]

        self.assertIn("My name is Alice Johnson.", documents)
        self.assertNotIn("My name is Bob Smith.", documents)


class AuthenticationFlowTests(TestCase):
    def test_anonymous_root_shows_chat_welcome_and_auth_choices(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Where should we begin?")
        self.assertContains(response, reverse("login"))
        self.assertContains(response, reverse("signup"))

    def test_anonymous_upload_redirects_to_sign_in(self):
        pdf = SimpleUploadedFile(
            "guest.pdf",
            b"%PDF-1.4\n%%EOF",
            content_type="application/pdf",
        )

        response = self.client.post(reverse("home"), {"pdf": pdf})

        self.assertRedirects(response, reverse("login"))
        self.assertFalse(Document.objects.filter(title="guest.pdf").exists())

    def test_signup_logs_in_first_user_and_claims_existing_history(self):
        legacy_document = Document.objects.create(
            title="Legacy PDF",
            pdf="pdfs/legacy.pdf",
        )

        response = self.client.post(
            reverse("signup"),
            {
                "username": "firststudent",
                "password1": "Secure-Test-Password-934!",
                "password2": "Secure-Test-Password-934!",
            },
        )

        user = get_user_model().objects.get(username="firststudent")
        legacy_document.refresh_from_db()
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(legacy_document.owner_id, user.pk)

        home_response = self.client.get(reverse("home"))
        self.assertContains(home_response, "Legacy PDF")

    def test_existing_account_can_log_in(self):
        get_user_model().objects.create_user(
            username="returningstudent",
            password="Secure-Test-Password-934!",
        )

        response = self.client.post(
            reverse("login"),
            {
                "username": "returningstudent",
                "password": "Secure-Test-Password-934!",
            },
        )

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)
