from django.db import models
from django.conf import settings
from registration.models import Chatbot


class ChatbotDocument(models.Model):
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='documents')
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.chatbot.name} - {self.filename}"

class ChatbotDocumentGroup(models.Model):
    chatbot = models.OneToOneField(Chatbot, on_delete=models.CASCADE, related_name='document_group')
    active_documents = models.ManyToManyField(ChatbotDocument)
    index_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.chatbot.name}'s Document Group"
    
    def can_add_document(self):
        return self.active_documents.count() < 3

class ChatbotUpload(models.Model):
    chatbot = models.ForeignKey(
        Chatbot,
        on_delete=models.CASCADE,
        related_name='uploads'
    )
    index_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.chatbot.name} - {self.index_name}"