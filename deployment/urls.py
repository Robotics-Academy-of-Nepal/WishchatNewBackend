# chatbot_app/urls.py
from django.urls import path
from .views import whatsapp_credentials, messenger_credentials, unified_webhook, instagram_credentials

urlpatterns = [
    path('credentials/', whatsapp_credentials, name='whatsapp_credentials'),
    path('messenger-credentials/', messenger_credentials, name='messenger_credentials'),
    path('instagram-credentials/', instagram_credentials, name='instagram_credentials'),
    path('webhook/<str:chatbot_id>/<str:platform>/', unified_webhook, name='unified_webhook'),
]