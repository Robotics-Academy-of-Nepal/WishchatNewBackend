from django.urls import path
from .views import PaymentSuccessView, ChatbotPaymentListView, ChatbotQuotaView

urlpatterns = [
    path('payment-success/', PaymentSuccessView.as_view(), name='payment-success'),
    path('chatbot-payments/', ChatbotPaymentListView.as_view(), name='chatbot-payments'),
    path('/<int:chatbot_id>/chatbot-quota/', ChatbotQuotaView.as_view(), name='Chatbot Quota'),
]