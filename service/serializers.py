from rest_framework import serializers
from .models import AdminActivityLog
from registration.models import CustomUser, Chatbot, CouponCode, SubscriptionPlan

class AdminActivityLogSerializer(serializers.ModelSerializer):
    activity = serializers.SerializerMethodField()

    class Meta:
        model = AdminActivityLog
        fields = ['id', 'activity', 'timestamp']
        read_only_fields = ['id', 'activity', 'timestamp']

    def get_activity(self, obj):
        return str(obj)  
    

class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'is_staff',
            'is_superuser',
        ]