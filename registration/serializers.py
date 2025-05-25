import uuid
from rest_framework import serializers
from .models import (
    Organization,
    CustomUser,
    Chatbot,
    ChatbotQuota,
    ChatbotPaymentTransaction,
    OrganizationInvitation,
    ChatbotFAQ,
    ChatbotColor,
    CouponCode,
    SubscriptionPlan,
    ChatbotTokenUsage,
)
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.db.models import Sum


class GoogleAuthSerializer(serializers.Serializer):
    """Serializer to validate Google OAuth token."""

    auth_token = serializers.CharField()


class GoogleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "first_name", "last_name", "phone_number"]
        read_only_fields = ["id", "username", "email"]


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name"]


class CustomUserSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_name = serializers.CharField(write_only=True, required=False)
    is_owner = serializers.BooleanField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "username",
            "phone_number",
            "password",
            "organization",
            "organization_name",
            "is_owner",
            "is_active",
            "is_staff",
            "is_superuser",
        ]
        read_only_fields = ["is_active", "is_staff", "is_superuser"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        """Handles user creation via API."""
        password = validated_data.pop("password", None)
        organization_name = validated_data.pop("organization_name", None)

        # Check if the organization exists or create a new one
        organization = None
        if organization_name:
            organization, created = Organization.objects.get_or_create(
                name=organization_name
            )

        # User who creates an organization becomes its owner
        is_owner = bool(organization_name)

        user = CustomUser(
            **validated_data, organization=organization, is_owner=is_owner
        )

        if password:
            user.set_password(password)

        user.save()
        return user

    def update(self, instance, validated_data):
        """Handle user updates."""
        # Remove password from update if present
        password = validated_data.pop("password", None)

        # Remove organization_name from update
        organization_name = validated_data.pop("organization_name", None)

        # Update the remaining fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Handle password update if provided
        if password:
            instance.set_password(password)

        instance.save()
        return instance


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "price",
            "message_limit",
            "trial_days",
            "is_active",
            "is_lifetime",
            "auto_reset_quota",
            "created_at",
            "updated_at",
            "features",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ChatbotQuotaSerializer(serializers.ModelSerializer):
    is_trial_valid = serializers.SerializerMethodField()
    is_subscription_valid = serializers.SerializerMethodField()
    can_send_message = serializers.SerializerMethodField()
    trial_end_date = serializers.SerializerMethodField()
    subscription_plan = SubscriptionPlanSerializer(read_only=True)
    message_limit = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = ChatbotQuota
        fields = [
            "id",
            "chatbot",
            "subscription_plan",
            "messages_used",
            "message_limit",
            "temporary_message_boost",
            "is_trial",
            "trial_start_date",
            "trial_end_date",
            "is_paid",
            "subscription_end_date",
            "last_reset",
            "is_trial_valid",
            "is_subscription_valid",
            "can_send_message",
            "grace_period_days",
            "is_sending_enabled",
            "last_payment_date",
            "created_at",
        ]
        read_only_fields = [
            "messages_used",
            "temporary_message_boost",
            "is_trial",
            "trial_start_date",
            "is_paid",
            "subscription_end_date",
            "last_reset",
            "created_at",
        ]

    def get_is_trial_valid(self, obj):
        return obj.is_trial_valid()

    def get_is_subscription_valid(self, obj):
        return obj.is_subscription_valid()

    def get_can_send_message(self, obj):
        return obj.can_send_message()

    def get_trial_end_date(self, obj):
        if not obj.subscription_plan:
            return obj.trial_start_date + timedelta(days=7)
        return obj.trial_start_date + timedelta(days=obj.subscription_plan.trial_days)

    def get_message_limit(self, obj):
        return obj.get_message_limit()

    def get_created_at(self, obj):
        return obj.chatbot.created_at


class ChatbotSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    quota = ChatbotQuotaSerializer(read_only=True)

    class Meta:
        model = Chatbot
        fields = [
            "id",
            "organization",
            "name",
            "api_key",
            "azure_index_name",
            "created_at",
            "updated_at",
            "quota",
            "system_prompt",
            "domain_name",
        ]
        read_only_fields = ["api_key", "created_at", "updated_at"]

    def create(self, validated_data):
        organization = validated_data.pop("organization")
        chatbot = Chatbot.objects.create(**validated_data, organization=organization)
        ChatbotQuota.objects.create(chatbot=chatbot)

        return chatbot


class ChatbotListQuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotQuota
        fields = ["messages_used"]


class ChatbotListSerializer(serializers.ModelSerializer):
    quota = ChatbotListQuotaSerializer(read_only=True)

    class Meta:
        model = Chatbot
        fields = [
            "id",
            "name",
            "api_key",
            "azure_index_name",
            "quota",
            "system_prompt",
            "domain_name",
        ]


class ChatbotPaymentTransactionSerializer(serializers.ModelSerializer):
    chatbot = ChatbotSerializer(read_only=True)
    subscription_plan = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.filter(is_active=True)
    )
    coupon_code = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    class Meta:
        model = ChatbotPaymentTransaction
        fields = [
            "id",
            "chatbot",
            "subscription_plan",
            "transaction_id",
            "payment_date",
            "amount",
            "coupon_code",
            "discounted_amount",
        ]
        read_only_fields = [
            "transaction_id",
            "payment_date",
            "amount",
            "discounted_amount",
        ]

    def create(self, validated_data):
        chatbot = validated_data["chatbot"]
        subscription_plan = validated_data["subscription_plan"]
        payment_amount = validated_data["amount"]
        coupon_code = validated_data.pop("coupon_code", None)
        transaction_id = str(uuid.uuid4())

        transaction = ChatbotPaymentTransaction.create_and_confirm_transaction(
            chatbot=chatbot,
            payment_amount=payment_amount,
            payment_transaction_code=transaction_id,
            subscription_plan_id=subscription_plan.id,
            coupon_code=coupon_code,
        )
        return transaction


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    invited_by_name = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationInvitation
        fields = [
            "id",
            "organization_name",
            "invited_by_name",
            "email",
            "invitation_code",
            "status",
            "created_at",
            "expires_at",
            "is_valid",
        ]
        read_only_fields = ["invitation_code", "created_at", "expires_at"]

    def get_organization_name(self, obj):
        return obj.organization.name

    def get_invited_by_name(self, obj):
        return f"{obj.invited_by.first_name} {obj.invited_by.last_name}"

    def get_is_valid(self, obj):
        return obj.is_valid()

    def create(self, validated_data):
        invited_by = self.context.get("request").user

        # Check if the user is the owner of the organization
        if not invited_by.is_owner and not invited_by.is_staff:
            raise serializers.ValidationError(
                "Only organization owners can send invitations."
            )

        organization = invited_by.organization

        # Check if invitation already exists
        existing_invitation = OrganizationInvitation.objects.filter(
            organization=organization, email=validated_data["email"], status="pending"
        ).first()

        if existing_invitation:
            # Return the existing invitation if it's still valid
            if existing_invitation.is_valid():
                return existing_invitation
            # Otherwise, update the existing invitation
            existing_invitation.expires_at = timezone.now() + timedelta(days=7)
            existing_invitation.save()
            return existing_invitation

        # Create new invitation (use organization and invited_by from context)
        validated_data["organization"] = organization
        validated_data["invited_by"] = invited_by

        invitation = super().create(validated_data)

        # Send the invitation email
        from .utils import send_invitation_email

        frontend_url = settings.FRONTEND_URL
        send_invitation_email(invitation, frontend_url)

        return invitation


class ChatbotFAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotFAQ
        fields = ["id", "question", "answer", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class ChatbotColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotColor
        fields = [
            "id",
            "bubbleBgColor",
            "bubbleColor",
            "chatBackgroundColor",
            "chatBorder",
            "headerBackgroundColor",
            "headerTextColor",
            "footerBackgroundColor",
            "sendButtonColor",
            "sendTextColor",
            "headerText",
            "inputBorderColor",
            "placeholderText",
            "inputTextColor",
            "inputBgColor",
            "questionTextColor",
            "questionBackgroundColor",
            "answerTextColor",
            "answerBackgroundColor",
            "faqTextColor",
            "faqBackgroundColor",
            "faqSectionBackgroundColor",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def to_representation(self, instance):
        """Customize the order of fields in the response, putting headerText first, then placeholderText."""
        # Get the default representation
        data = super().to_representation(instance)

        # Create a new ordered dictionary
        from collections import OrderedDict

        ordered_data = OrderedDict()

        # Add headerText first
        ordered_data["headerText"] = data.pop("headerText")
        # Add placeholderText second
        ordered_data["placeholderText"] = data.pop("placeholderText")

        # Add the remaining fields in their original order
        for key, value in data.items():
            ordered_data[key] = value

        return ordered_data


class GracePeriodUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotQuota
        fields = ["grace_period_days"]


class SendingStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotQuota
        fields = ["is_sending_enabled"]


class MessageLimitUpdateSerializer(serializers.Serializer):
    message_limit = serializers.IntegerField(min_value=0)

    def update(self, instance, validated_data):
        message_limit = validated_data["message_limit"]
        # Create or update a custom subscription plan for this chatbot
        if instance.subscription_plan and not instance.subscription_plan.is_lifetime:
            # Update existing plan if it's not shared by other chatbots
            if instance.subscription_plan.quotas.count() == 1:
                instance.subscription_plan.message_limit = message_limit
                instance.subscription_plan.save()
            else:
                # Create a new custom plan if the current one is shared
                custom_plan = SubscriptionPlan.objects.create(
                    name=f"Custom Plan for {instance.chatbot.name}",
                    price=instance.subscription_plan.price,
                    message_limit=message_limit,
                    trial_days=instance.subscription_plan.trial_days,
                    is_active=True,
                    is_lifetime=False,
                    auto_reset_quota=instance.subscription_plan.auto_reset_quota,
                )
                instance.subscription_plan = custom_plan
        else:
            # Create a new custom plan if no plan or lifetime plan
            custom_plan = SubscriptionPlan.objects.create(
                name=f"Custom Plan for {instance.chatbot.name}",
                price=0,
                message_limit=message_limit,
                trial_days=7,
                is_active=True,
                is_lifetime=False,
                auto_reset_quota=True,
            )
            instance.subscription_plan = custom_plan
        instance.temporary_message_boost = 0  # Reset temporary boost
        instance.save()

        # Store the message_limit in validated_data for access through serializer.data
        self._validated_data["message_limit"] = message_limit

        return instance

    def to_representation(self, instance):
        """Return the message limit for the response."""
        # If we have validated data (after update), use that value
        if hasattr(self, "_validated_data") and "message_limit" in self._validated_data:
            return {"message_limit": self._validated_data["message_limit"]}

        # Otherwise get it from the instance's subscription plan
        if instance.subscription_plan:
            return {"message_limit": instance.subscription_plan.message_limit}
        else:
            return {"message_limit": 0}


class TemporaryMessageBoostSerializer(serializers.Serializer):
    additional_messages = serializers.IntegerField(min_value=0)


class CouponCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CouponCode
        fields = [
            "id",
            "code",
            "discount_percent",
            "max_usage",
            "times_used",
            "created_at",
            "updated_at",
            "is_active",
        ]
        read_only_fields = ["times_used", "created_at", "updated_at"]

    def validate_discount_percent(self, value):
        """Ensure discount percentage is between 0 and 100."""
        if not 0 <= value <= 100:
            raise serializers.ValidationError(
                "Discount percent must be between 0 and 100."
            )
        return value

    def validate(self, data):
        """Ensure max_usage is positive."""
        if data["max_usage"] <= 0:
            raise serializers.ValidationError("Max usage must be a positive integer.")
        return data


class CouponCodeRedemptionSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    chatbot_id = serializers.IntegerField()
    subscription_plan_id = serializers.IntegerField()

    def validate(self, data):
        chatbot_id = data["chatbot_id"]
        subscription_plan_id = data["subscription_plan_id"]
        code = data["code"]

        try:
            chatbot = Chatbot.objects.get(id=chatbot_id)
        except Chatbot.DoesNotExist:
            raise serializers.ValidationError("Chatbot with this ID does not exist.")

        try:
            plan = SubscriptionPlan.objects.get(id=subscription_plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError(
                "Subscription plan does not exist or is inactive."
            )

        try:
            coupon = CouponCode.objects.get(code=code)
            if not coupon.is_valid(chatbot):
                raise serializers.ValidationError(
                    "Coupon code is invalid, expired, or already used by this chatbot."
                )
        except CouponCode.DoesNotExist:
            raise serializers.ValidationError("Coupon code does not exist.")

        data["chatbot"] = chatbot
        data["subscription_plan"] = plan
        return data

    def redeem(self):
        code = self.validated_data["code"]
        subscription_plan = self.validated_data["subscription_plan"]
        chatbot = self.validated_data["chatbot"]
        coupon = CouponCode.objects.get(code=code)

        discount = (coupon.discount_percent / 100) * float(subscription_plan.price)
        discounted_amount = float(subscription_plan.price) - discount

        return {
            "original_amount": float(subscription_plan.price),
            "discounted_amount": discounted_amount,
            "discount_applied": coupon.discount_percent,
            "coupon_code": code,
            "subscription_plan_id": subscription_plan.id,
        }


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["email"]


class ChatbotTokenSerializer(serializers.ModelSerializer):
    chatbot_token_count = serializers.SerializerMethodField()

    class Meta:
        model = Chatbot
        fields = ["id", "name", "chatbot_token_count"]

    def get_chatbot_token_count(self, obj):
        month_param = self.context.get("month_param")
        if month_param:
            try:
                year, month = map(int, month_param.split("-"))
                token_usage = ChatbotTokenUsage.objects.filter(
                    chatbot=obj, timestamp__year=year, timestamp__month=month
                ).aggregate(total=Sum("total_tokens"))
                return token_usage["total"] or 0
            except (ValueError, TypeError):
                return 0
        else:
            token_usage = ChatbotTokenUsage.objects.filter(chatbot=obj).aggregate(
                total=Sum("total_tokens")
            )
            return token_usage["total"] or 0


class OrganizationDetailSerializer(serializers.ModelSerializer):
    organization_token_count = serializers.SerializerMethodField()
    organization_members = MemberSerializer(many=True, source="members")
    chatbots = ChatbotTokenSerializer(many=True)

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "organization_token_count",
            "organization_members",
            "chatbots",
        ]

    def get_organization_token_count(self, obj):
        month_param = self.context.get("month_param")
        if month_param:
            try:
                year, month = map(int, month_param.split("-"))
                token_usage = obj.total_tokens_used_by_month(year, month)
                return token_usage["total"] or 0
            except (ValueError, TypeError):
                return 0
        else:
            token_usage = obj.total_tokens_used()
            return token_usage["total"] or 0
