from django.urls import path
from .views import PaymentSuccessView

urlpatterns = [
    path('payment-success/', PaymentSuccessView.as_view(), name='payment-success'),
]