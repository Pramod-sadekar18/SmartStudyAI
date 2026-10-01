from django.conf import settings
from django.db import models


class Document(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_documents",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    pdf = models.FileField(upload_to="pdfs/")
    extracted_text = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks"
    )

    chunk_number = models.IntegerField()
    text = models.TextField()

    def __str__(self):
        return f"{self.document.title} - Chunk {self.chunk_number}"