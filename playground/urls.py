from django.urls import path
from .views import handle_query, set_chatbot_prompt

urlpatterns = [
    path('query/', handle_query, name='handle_query'),
    path('system-prompt/', set_chatbot_prompt, name='set_chatbot_prompt'),
]