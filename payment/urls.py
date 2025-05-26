from django.urls import path
from .views import (
    PaymentSuccessView,
    ChatbotPaymentListView,
    ChatbotQuotaView,
    MessageQuotaView,
    InitiateEsewaPaymentView,
    InitiateKhaltiPaymentView,
)

urlpatterns = [
    path(
        "initiate-esewa-payment/",
        InitiateEsewaPaymentView.as_view(),
        name="initiate-esewa-payment",
    ),
    path(
        "initiate-khalti-payment/",
        InitiateKhaltiPaymentView.as_view(),
        name="initiate-khalti-payment",
    ),
    path("payment-success/", PaymentSuccessView.as_view(), name="payment-success"),
    path(
        "chatbot-payments/", ChatbotPaymentListView.as_view(), name="chatbot-payments"
    ),
    path(
        "<int:chatbot_id>/chatbot-quota/",
        ChatbotQuotaView.as_view(),
        name="Chatbot Quota",
    ),
    path(
        "<int:chatbot_id>/message-quota/",
        MessageQuotaView.as_view(),
        name="Message Quota",
    ),
]
