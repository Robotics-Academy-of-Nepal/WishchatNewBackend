from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework import status
from registration.models import Chatbot, ChatbotQuota, SubscriptionPlan, Organization
from registration.serializers import (
    GracePeriodUpdateSerializer,
    SendingStatusUpdateSerializer,
    MessageLimitUpdateSerializer,
    SubscriptionPlanSerializer,
    TemporaryMessageBoostSerializer,
    OrganizationDetailSerializer
)
from django.utils import timezone
from .models import AdminActivityLog
from .serializers import AdminActivityLogSerializer
from rest_framework.exceptions import PermissionDenied
from django.core.exceptions import ObjectDoesNotExist


class GracePeriodModificationView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota
            serializer = GracePeriodUpdateSerializer(quota, data=request.data)
            if serializer.is_valid():
                serializer.save()
                AdminActivityLog.objects.create(
                    user=request.user,
                    action=f"updated grace period to {serializer.data['grace_period_days']} days for chatbot {chatbot.name}",
                    target_chatbot=chatbot
                )
                return Response({
                    "message": "Grace period updated successfully",
                    "grace_period": serializer.data["grace_period_days"]
                }, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Chatbot.DoesNotExist:
            return Response({"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND)
        

class UpdateSendingStatusView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota
            serializer = SendingStatusUpdateSerializer(quota, data=request.data)
            if serializer.is_valid():
                serializer.save()
                AdminActivityLog.objects.create(
                    user=request.user,
                    action=f"{'enabled' if serializer.data['is_sending_enabled'] else 'disabled'} message sending for chatbot {chatbot.name}",
                    target_chatbot=chatbot
                )
                return Response({
                    "message": "Message sending status successfully changed",
                    "sending_status": serializer.data["is_sending_enabled"]
                }, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Chatbot.DoesNotExist:
            return Response({"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND)
        

class UpdateMessageLimitView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota
            serializer = MessageLimitUpdateSerializer(quota, data=request.data)
            if serializer.is_valid():
                serializer.save()
                AdminActivityLog.objects.create(
                    user=request.user,
                    action=f"updated message limit to {serializer.data['message_limit']} for chatbot {chatbot.name}",
                    target_chatbot=chatbot
                )
                return Response({
                    "message": "Message limit successfully changed",
                    "message_limit": serializer.data["message_limit"]
                }, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Chatbot.DoesNotExist:
            return Response({"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND)
        
class CreateSubscriptionPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Only staff or superadmin users can delete subscription plans.")
        
        serializer = SubscriptionPlanSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            AdminActivityLog.objects.create(
                    user=request.user,
                    action=f"created subscription plan {serializer.instance.name}",
                    target_plan=serializer.instance
                )
            return Response({
                "message": "Subscription plan created successfully",
                "plan": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ListSubscriptionPlansView(APIView):
    permission_classes = [IsAuthenticated]  

    def get(self, request):
        
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Only staff or superadmin users can delete subscription plans.")
        
        plans = SubscriptionPlan.objects.filter(is_active=True)
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response({
            "message": "Active subscription plans retrieved successfully",
            "plans": serializer.data
        }, status=status.HTTP_200_OK)

class SubscriptionPlanDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Only staff or superadmin users can delete subscription plans.")

        try:
            
            plan = SubscriptionPlan.objects.get(pk=pk)
        except ObjectDoesNotExist:
            return Response(
                {"detail": "Subscription plan not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        
        plan_name = plan.name

        
        plan.delete()

        
        AdminActivityLog.objects.create(
            user=request.user,
            action=f"deleted subscription plan '{plan_name}'"
        )

        return Response(
            {"detail": f"Subscription plan '{plan_name}' deleted successfully."},
            status=status.HTTP_200_OK
        )


class AssignLifetimePlanView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota
            quota.is_lifetime_free = True
            quota.subscription_plan = None
            quota.is_paid = False
            quota.is_trial = False
            quota.subscription_end_date = None
            quota.messages_used = 0
            quota.temporary_message_boost = 0
            quota.save()

            AdminActivityLog.objects.create(
                user=request.user,
                action=f"assigned lifetime free plan to chatbot {chatbot.name}",
                target_chatbot=chatbot
            )

            return Response({
                "message": "Chatbot set as free for lifetime with unlimited messages"
            }, status=status.HTTP_200_OK)
        except Chatbot.DoesNotExist:
            return Response({"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND)


class TemporaryMessageBoostView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota
            serializer = TemporaryMessageBoostSerializer(data=request.data)
            if serializer.is_valid():
                additional_messages = serializer.validated_data['additional_messages']
                quota.add_temporary_boost(additional_messages)

                AdminActivityLog.objects.create(
                    user=request.user,
                    action=f"added temporary message boost of {additional_messages} messages to chatbot {chatbot.name}",
                    target_chatbot=chatbot
                )

                return Response({
                    "message": "Temporary message boost added successfully",
                    "additional_messages": additional_messages,
                    "new_message_limit": quota.get_message_limit()
                }, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Chatbot.DoesNotExist:
            return Response({"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND)
        

class RevokeLifetimeStatusView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, chatbot_id):
        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
            quota = chatbot.quota
            if not quota.is_lifetime_free and (not quota.subscription_plan or not quota.subscription_plan.is_lifetime):
                return Response({
                    "error": "Chatbot is not on a lifetime free or lifetime plan"
                }, status=status.HTTP_400_BAD_REQUEST)
            quota.revoke_lifetime_plan()
            # Assign a default plan (e.g., free plan with 5000 messages)
            default_plan = SubscriptionPlan.objects.filter(is_active=True, price=0).first()
            if default_plan:
                quota.subscription_plan = default_plan
                quota.is_trial = True
                quota.trial_start_date = timezone.now()
                quota.save()

            AdminActivityLog.objects.create(
                user=request.user,
                action=f"revoked lifetime status for chatbot {chatbot.name}",
                target_chatbot=chatbot
            )

            return Response({
                "message": "Lifetime status revoked successfully"
            }, status=status.HTTP_200_OK)
        except Chatbot.DoesNotExist:
            return Response({"error": "Chatbot not found"}, status=status.HTTP_404_NOT_FOUND)
        
class AdminOrganizationOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            print(request.user)
            if not (request.user.is_superuser or request.user.is_staff):
                return Response({
                    "error": "Only superadmins and staffs can access this data."
                }, status=status.HTTP_403_FORBIDDEN)
            month_param = request.query_params.get('month', None)

            # Get all organizations
            organizations = Organization.objects.all()
            organization_count = organizations.count()

            # Serialize data with month_param in context
            serializer = OrganizationDetailSerializer(
                organizations,
                many=True,
                context={'month_param': month_param}
            )

            # Prepare response
            response_data = {
                "organization_count": organization_count,
                "organizations": serializer.data
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": "Failed",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class AdminActivityLogListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logs = AdminActivityLog.objects.all().order_by('-timestamp')
        serializer = AdminActivityLogSerializer(logs, many=True)
        return Response({
            "message": "Activity logs retrieved successfully",
            "logs": serializer.data
        }, status=status.HTTP_200_OK)