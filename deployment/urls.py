# chatbot_app/urls.py
from django.urls import path
from .views import (whatsapp_credentials, 
    messenger_credentials, 
    unified_webhook, 
    instagram_credentials,
    whatsapp_oauth,
    whatsapp_oauth_callback,
    messenger_oauth,
    messenger_oauth_callback,
    instagram_oauth,
    instagram_oauth_callback)

urlpatterns = [
    path('credentials/', whatsapp_credentials, name='whatsapp_credentials'),
    path('messenger-credentials/', messenger_credentials, name='messenger_credentials'),
    path('instagram-credentials/', instagram_credentials, name='instagram_credentials'),
    path('webhook/<str:chatbot_id>/<str:platform>/', unified_webhook, name='unified_webhook'),
    path('oauth/messenger/', messenger_oauth, name='messenger_oauth'),
    path('oauth/callback/messenger/', messenger_oauth_callback, name='messenger_oauth_callback'),
    path('oauth/instagram/', instagram_oauth, name='instagram_oauth'),
    path('oauth/callback/instagram/', instagram_oauth_callback, name='instagram_oauth_callback'),
]