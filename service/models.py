from django.db import models
from registration.models import CustomUser, Chatbot, CouponCode, SubscriptionPlan
from django.utils import timezone

class AdminActivityLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='activity_logs', help_text="User who performed the action")
    action = models.CharField(max_length=255, help_text="Description of the action (e.g., 'created staff user', 'created coupon code')")
    target_chatbot = models.ForeignKey(Chatbot, on_delete=models.SET_NULL, null=True, blank=True, help_text="Chatbot affected by the action, if applicable")
    target_coupon = models.ForeignKey(CouponCode, on_delete=models.SET_NULL, null=True, blank=True, help_text="Coupon code affected by the action, if applicable")
    target_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, help_text="Subscription plan affected by the action, if applicable")
    timestamp = models.DateTimeField(default=timezone.now, help_text="When the action was performed")

    def __str__(self):
        username = self.user.username if self.user else "Unknown"
        return f"{username} {self.action}"

    class Meta:
        verbose_name = "Admin Activity Log"
        verbose_name_plural = "Admin Activity Logs"
        ordering = ['-timestamp']