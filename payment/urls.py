from django.urls import path
from .views import PaymentSuccessView, ChatbotPaymentListView

urlpatterns = [
    path('payment-success/', PaymentSuccessView.as_view(), name='payment-success'),
    path('chatbot-payments/', ChatbotPaymentListView.as_view(), name='chatbot-payments'),
]