from django.urls import path
from .views import (
    GracePeriodModificationView,
    UpdateSendingStatusView,
    UpdateMessageLimitView,
    CreateSubscriptionPlanView,
    ListSubscriptionPlansView,
    AssignLifetimePlanView,
    TemporaryMessageBoostView,
    RevokeLifetimeStatusView,
    AdminOrganizationOverviewView,
    AdminActivityLogListView,
    SubscriptionPlanDeleteView
)

urlpatterns = [
    path('chatbots/<int:chatbot_id>/update-grace-period/', GracePeriodModificationView.as_view(), name="GracePeriodModification"),
    path('chatbots/<int:chatbot_id>/update-sending-status/', UpdateSendingStatusView.as_view(), name="UpdateSendingStatus"),
    path('chatbots/<int:chatbot_id>/update-message-limit/', UpdateMessageLimitView.as_view(), name="UpdateMessageLimit"),
    path('subscription-plans/create/', CreateSubscriptionPlanView.as_view(), name='create-subscription-plan'),
    path('subscription-plans/', ListSubscriptionPlansView.as_view(), name='list-subscription-plans'),
    path('chatbots/<int:chatbot_id>/lifetime-plan/', AssignLifetimePlanView.as_view(), name='assign-lifetime-plan'),
    path('chatbots/<int:chatbot_id>/temporary-boost/', TemporaryMessageBoostView.as_view(), name='temporary-message-boost'),
    path('chatbots/<int:chatbot_id>/revoke-lifetime/', RevokeLifetimeStatusView.as_view(), name='revoke-lifetime-status'),
    path('organization-overview/', AdminOrganizationOverviewView.as_view(), name='admin-organization-overview'),
    path('activity-logs/', AdminActivityLogListView.as_view(), name='admin_activity_log_list'),
    path('subscription-plans/<int:pk>/delete/', SubscriptionPlanDeleteView.as_view(), name='subscription-plan-delete'),
]   