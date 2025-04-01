from django.urls import path, include
from .views import (
    GoogleLoginView,  
    OrganizationMemberViewSet,
    OrganizationInvitationViewSet,
    CreateOrganizationView,
    ChatbotViewSet,
    LogoutView,
    DeleteOrganizationMemberView,
    DeleteOrganizationView,
    ChatbotFAQViewSet,
    ChatbotColorViewSet,
    AdminOrganizationView,
    AdminChatbotlistView,
    TotalTokenUsageView,
    OrganizationTokenCountView,
    ChatbotTokenCountView,
    GracePeriodModificationView,
    UpdateSendingStatusView,
    UpdateMessageLimitView,
    AddDomainNameView,
    ChatbotPublicInfoView,
    privacy_policy
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'invitations', OrganizationInvitationViewSet, basename='invitations')
router.register(r'chatbots', ChatbotViewSet, basename='chatbot')
router.register(r'organization-members', OrganizationMemberViewSet, basename='organization-member')

faq_router = DefaultRouter()
faq_router.register(r'faqs', ChatbotFAQViewSet, basename='chatbot-faq')

# Use a custom path instead of router for ChatbotColorViewSet
urlpatterns = [
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('google-login/', GoogleLoginView.as_view(), name='google-login'),
    path('organizations/create/', CreateOrganizationView.as_view(), name='create-organization'),
    path('organization/members/<int:member_id>/', DeleteOrganizationMemberView.as_view(), name='delete-member'),
    path('organization/delete/', DeleteOrganizationView.as_view(), name='delete-organization'),
    path('organizations/list/', AdminOrganizationView.as_view(), name='AdminOrganizationView'),
    path('token-usage/', TotalTokenUsageView.as_view(), name="TotalTokenUsage"),
    path('<int:org_id>/token-usage/', OrganizationTokenCountView.as_view(), name="OrganizationTokenCount"),
    path('chatbots/<int:chatbot_id>/token-usage/', ChatbotTokenCountView.as_view(), name="ChatbotTokenCount"),
    path('chatbots/<int:chatbot_id>/update-grace-period/', GracePeriodModificationView.as_view(), name="GracePeriodModification"),
    path('chatbots/<int:chatbot_id>/update-sending-status/', UpdateSendingStatusView.as_view(), name="UpdateSendingStatus"),
    path('chatbots/<int:chatbot_id>/update-message-limit/', UpdateMessageLimitView.as_view(), name="UpdateMessageLimit"),
    path('<int:chatbot_id>/add/domain/', AddDomainNameView.as_view(), name="AddDomainName"),
    path('chatbot/public-info/', ChatbotPublicInfoView.as_view(), name='chatbot-public-info'),
    path('<int:org_id>/chatbots/list/', AdminChatbotlistView.as_view(), name='AdminChatbotlist'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', include(router.urls)),
    path('chatbots/<int:chatbot_id>/', include([
        path('', include(faq_router.urls)),  
        path('colors/', ChatbotColorViewSet.as_view({'get': 'list', 'post': 'create'}), name='chatbot-colors'),
    ])),
    
]