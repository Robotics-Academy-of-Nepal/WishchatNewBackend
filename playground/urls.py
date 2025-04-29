from django.urls import path
from .views import (handle_query, 
    set_chatbot_prompt, 
    chatbot_traffic_stats, 
    chatbot_quota_data
)
urlpatterns = [
    path('query/', handle_query, name='handle_query'),
    path('system-prompt/', set_chatbot_prompt, name='set_chatbot_prompt'),
    path('chatbot/<int:chatbot_id>/traffic-stats/', chatbot_traffic_stats, name='chatbot_traffic_stats'),
    path('<int:chatbot_id>/chatbot-stats/', chatbot_quota_data, name='chatbot_quota_data'),
]