from rest_framework import serializers
from registration.models import ChatbotQuota


class MessageCountSerializer(serializers.ModelSerializer):
    message_limit = serializers.SerializerMethodField()

    class Meta:
        model = ChatbotQuota
        fields = [
            "messages_used",
            "message_limit",
        ]

        read_only_fields = [
            "messages_used",
            "message_limit",
        ]

    def get_message_limit(self, obj):
        return obj.get_message_limit()


class PaymentInitiateSerializer(serializers.Serializer):
    total_amount = serializers.FloatField(min_value=0.01)
    coupon = serializers.CharField(max_length=100, required=False, allow_blank=True)
    plan_id = serializers.IntegerField()
