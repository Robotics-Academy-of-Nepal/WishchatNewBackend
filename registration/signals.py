from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Chatbot, ChatbotColor

@receiver(post_save, sender=Chatbot)
def create_chatbot_color(sender, instance, created, **kwargs):
    if created:
        # Create a ChatbotColor instance with default values when a new Chatbot is created
        ChatbotColor.objects.create(chatbot=instance)