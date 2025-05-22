from rest_framework import serializers
from registration.models import ChatbotQuota


class MessageCountSerializer(serializers.ModelSerializer):
    
    message_limit = serializers.SerializerMethodField()

    class Meta:
        model = ChatbotQuota    
        fields = [
            'messages_used',
            'message_limit',
        ]

        read_only_fields = [
            'messages_used',
            'message_limit',
        ]

    def get_message_limit(self, obj):
        return obj.get_message_limit()