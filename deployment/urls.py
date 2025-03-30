from django.urls import path
from .views import whatsapp_credentials , whatsAppWebhook, facebook_messenger_webhook, messenger_credentials

urlpatterns = [
    path('credentials/', whatsapp_credentials, name='whatsapp_credentials'),
    path('messenger-credentials/', messenger_credentials, name='messenger_credentials'),
    path('1dfb88d7-85fb-4e62-ba34-2446150ad8e5/',whatsAppWebhook, name="whatsAppWebhook"),
    path('facebook/',facebook_messenger_webhook, name="facebook_messenger_webhook")
]