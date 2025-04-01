from rest_framework import serializers
from .models import (
    Organization,
    CustomUser,
    Chatbot,
    ChatbotQuota,
    ChatbotPaymentTransaction,
    OrganizationInvitation,
    ChatbotFAQ,
    ChatbotColor
)
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

class GoogleAuthSerializer(serializers.Serializer):
    """Serializer to validate Google OAuth token."""
    auth_token = serializers.CharField()

class GoogleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone_number']
        read_only_fields = ['id', 'username', 'email']


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name']


class CustomUserSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_name = serializers.CharField(write_only=True, required=False)
    is_owner = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'first_name',
            'last_name',
            'email',
            'username',
            'phone_number',
            'password',
            'organization',
            'organization_name',
            'is_owner',
            'is_active',
            'is_staff',
            'is_superuser',
        ]
        read_only_fields = ['is_active', 'is_staff', 'is_superuser']
        extra_kwargs = {'password': {'write_only': True}}
    
    def create(self, validated_data):
        """Handles user creation via API."""
        password = validated_data.pop('password', None)
        organization_name = validated_data.pop('organization_name', None)
        
        # Check if the organization exists or create a new one
        organization = None
        if organization_name:
            organization, created = Organization.objects.get_or_create(name=organization_name)
        
        # User who creates an organization becomes its owner
        is_owner = bool(organization_name)
        
        user = CustomUser(
            **validated_data,
            organization=organization,
            is_owner=is_owner
        )
        
        if password:
            user.set_password(password)
        
        user.save()
        return user
    
    def update(self, instance, validated_data):
        """Handle user updates."""
        # Remove password from update if present
        password = validated_data.pop('password', None)
        
        # Remove organization_name from update
        organization_name = validated_data.pop('organization_name', None)
        
        # Update the remaining fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Handle password update if provided
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class ChatbotQuotaSerializer(serializers.ModelSerializer):
    is_trial_valid = serializers.SerializerMethodField()
    is_subscription_valid = serializers.SerializerMethodField()
    can_send_message = serializers.SerializerMethodField()
    trial_end_date = serializers.SerializerMethodField()

    class Meta:
        model = ChatbotQuota
        fields = [
            'id',
            'chatbot',
            'messages_used',
            'message_limit',
            'is_trial',
            'trial_start_date',
            'trial_end_date',
            'is_paid',
            'subscription_end_date',
            'last_reset',
            'is_trial_valid',
            'is_subscription_valid',
            'can_send_message',
            'grace_period_days',  
            'is_sending_enabled',  
        ]
        read_only_fields = [
            'messages_used',
            'is_trial',
            'trial_start_date',
            'is_paid',
            'subscription_end_date',
            'last_reset',
        ]

    def get_is_trial_valid(self, obj):
        return obj.is_trial_valid()

    def get_is_subscription_valid(self, obj):
        return obj.is_subscription_valid()

    def get_can_send_message(self, obj):
        return obj.can_send_message()
    
    def get_trial_end_date(self, obj):
        """Calculate trial end date (7 days from start)"""
        return obj.trial_start_date + timezone.timedelta(days=7)


class ChatbotSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    quota = ChatbotQuotaSerializer(read_only=True)

    class Meta:
        model = Chatbot
        fields = [
            'id',
            'organization',
            'name',
            'api_key',
            'azure_index_name',
            'created_at',
            'updated_at',
            'quota',
            'system_prompt',
            'domain_name'
        ]
        read_only_fields = ['api_key', 'created_at', 'updated_at']

    def create(self, validated_data):
        organization = validated_data.pop('organization')
        chatbot = Chatbot.objects.create(**validated_data, organization=organization)

        # Automatically create the quota for the chatbot (7-day trial, 5000 messages)
        ChatbotQuota.objects.create(chatbot=chatbot)

        return chatbot


class ChatbotPaymentTransactionSerializer(serializers.ModelSerializer):
    chatbot = ChatbotSerializer(read_only=True)

    class Meta:
        model = ChatbotPaymentTransaction
        fields = ['id', 'chatbot', 'transaction_id', 'payment_date', 'amount']
        read_only_fields = ['transaction_id', 'payment_date']

    def create(self, validated_data):
        chatbot = validated_data['chatbot']
        amount = validated_data['amount']

        # Use the custom method to handle payment and quota update
        transaction = ChatbotPaymentTransaction.create_transaction(chatbot, amount)
        return transaction

class OrganizationInvitationSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    invited_by_name = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = OrganizationInvitation
        fields = [
            'id', 
            'organization_name',  
            'invited_by_name',    
            'email', 
            'invitation_code', 
            'status', 
            'created_at', 
            'expires_at',
            'is_valid'
        ]
        read_only_fields = ['invitation_code', 'created_at', 'expires_at']

    def get_organization_name(self, obj):
        return obj.organization.name

    def get_invited_by_name(self, obj):
        return f"{obj.invited_by.first_name} {obj.invited_by.last_name}"
    
    def get_is_valid(self, obj):
        return obj.is_valid()
    
    def create(self, validated_data):
        invited_by = self.context.get('request').user
        
        # Check if the user is the owner of the organization
        if not invited_by.is_owner and not invited_by.is_staff:
            raise serializers.ValidationError("Only organization owners can send invitations.")
        
        organization = invited_by.organization
        
        # Check if invitation already exists
        existing_invitation = OrganizationInvitation.objects.filter(
            organization=organization,
            email=validated_data['email'],
            status='pending'
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
        validated_data['organization'] = organization
        validated_data['invited_by'] = invited_by
        
        invitation = super().create(validated_data)

        # Send the invitation email
        from .utils import send_invitation_email
        frontend_url = settings.FRONTEND_URL
        send_invitation_email(invitation, frontend_url)
        
        return invitation
    

class ChatbotFAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotFAQ
        fields = ['id', 'question', 'answer', 'created_at', 'updated_at']  
        read_only_fields = ['created_at', 'updated_at']  

class ChatbotColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotColor
        fields = [
            'id', 
            'bubbleBgColor',
            'bubbleColor',
            'chatBackgroundColor',
            'chatBorder',
            'headerBackgroundColor',
            'headerTextColor',
            'footerBackgroundColor',
            'sendButtonColor',
            'sendTextColor',
            'headerText',
            'inputBorderColor',
            'placeholderText',
            'inputTextColor',
            'inputBgColor',
            'questionTextColor',
            'questionBackgroundColor',
            'answerTextColor',
            'answerBackgroundColor',
            'faqTextColor',
            'faqBackgroundColor',
            'faqSectionBackgroundColor',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    
    def to_representation(self, instance):
        """Customize the order of fields in the response, putting headerText first, then placeholderText."""
        # Get the default representation
        data = super().to_representation(instance)
        
        # Create a new ordered dictionary
        from collections import OrderedDict
        ordered_data = OrderedDict()
        
        # Add headerText first
        ordered_data['headerText'] = data.pop('headerText')
        # Add placeholderText second
        ordered_data['placeholderText'] = data.pop('placeholderText')
        
        # Add the remaining fields in their original order
        for key, value in data.items():
            ordered_data[key] = value
            
        return ordered_data
    

class GracePeriodUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotQuota
        fields = ['grace_period_days']


class SendingStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotQuota
        fields = ['is_sending_enabled']

class MessageLimitUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotQuota
        fields = ['message_limit']