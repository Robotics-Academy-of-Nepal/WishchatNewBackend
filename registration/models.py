from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
import uuid
from django.utils import timezone
from datetime import timedelta
import uuid
import json, pickle


class SubscriptionPlan(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the subscription plan (e.g., Basic, Pro)",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Monthly price in NPR (0 for free plans)",
    )
    message_limit = models.IntegerField(
        default=5000, help_text="Monthly message quota (0 for unlimited)"
    )
    trial_days = models.IntegerField(
        default=7, help_text="Trial period in days (0 for no trial)"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this plan is available for selection"
    )
    is_lifetime = models.BooleanField(
        default=False,
        help_text="If true, chatbots on this plan have unlimited messages and no expiry",
    )
    auto_reset_quota = models.BooleanField(
        default=False, help_text="If true, quota resets monthly for free plans"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    features = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.price} NPR, {self.message_limit} messages)"

    class Meta:
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"


class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True, null=True)

    def total_messages_used(self):
        """Get total messages used across all chatbots in this organization."""
        from django.db.models import Sum

        return self.chatbots.aggregate(total=Sum("quota__messages_used"))["total"] or 0

    def total_tokens_used(self):
        """Get total tokens used across all chatbots."""
        from django.db.models import Sum

        return ChatbotTokenUsage.objects.filter(chatbot__organization=self).aggregate(
            total=Sum("total_tokens"),
            input=Sum("input_tokens"),
            output=Sum("output_tokens"),
        )

    def total_tokens_used_by_month(self, year, month):
        """Get total tokens used across all chatbots."""
        from django.db.models import Sum

        return ChatbotTokenUsage.objects.filter(
            chatbot__organization=self, timestamp__year=year, timestamp__month=month
        ).aggregate(
            total=Sum("total_tokens"),
            input=Sum("input_tokens"),
            output=Sum("output_tokens"),
        )

    def __str__(self):
        return self.name


class CustomUserManager(BaseUserManager):
    def create_user(
        self, email, username, password=None, organization=None, **extra_fields
    ):
        if not email:
            raise ValueError("The Email field is required")

        email = self.normalize_email(email)

        # New signups without an organization become owners
        is_owner = organization is None
        user = self.model(
            email=email,
            username=username,
            organization=organization,
            is_owner=is_owner,
            **extra_fields,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, username, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    # User Information
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=15, unique=False, null=True, blank=True)

    # Organization Link
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members",
        null=True,
        blank=True,
    )
    is_owner = models.BooleanField(
        default=False
    )  # To track if the user is an organization owner

    # Permissions
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Custom User Manager
    objects = CustomUserManager()

    is_enterprise = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    def __str__(self):
        return self.email


class Chatbot(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="chatbots"
    )
    name = models.CharField(max_length=100)
    api_key = models.CharField(max_length=100, unique=True, editable=False)
    azure_index_name = models.CharField(
        max_length=200, unique=True, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    system_prompt = models.TextField(
        max_length=200000, null=True, unique=False, blank=True
    )
    whatsapp_url = models.TextField(max_length=200, null=True, unique=False, blank=True)
    whatsapp_token = models.CharField(
        max_length=1000, null=True, blank=True, unique=False
    )
    whatsapp_id = models.CharField(max_length=50, null=True, blank=True, unique=False)
    messenger_url = models.TextField(
        max_length=200, null=True, unique=False, blank=True
    )
    messenger_token = models.CharField(
        max_length=1000, null=True, blank=True, unique=False
    )
    messenger_page_id = models.CharField(
        max_length=50, null=True, blank=True, unique=False
    )
    instagram_url = models.TextField(
        max_length=200, null=True, unique=False, blank=True
    )
    instagram_token = models.CharField(
        max_length=1000, null=True, blank=True, unique=False
    )
    instagram_page_id = models.CharField(
        max_length=50, null=True, blank=True, unique=False
    )
    domain_name = models.TextField(max_length=1000, null=True, unique=True, blank=True)
    verify_token = models.CharField(max_length=36, default=uuid.uuid4, unique=True)

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = self.generate_api_key()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_api_key():
        return str(uuid.uuid4()).replace("-", "")

    def __str__(self):
        return f"{self.name} - {self.organization.name}"


class ChatbotFAQ(models.Model):
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name="faqs")
    question = models.TextField(max_length=1000)  # FAQ question
    answer = models.TextField(max_length=10000)  # FAQ answer
    created_at = models.DateTimeField(
        auto_now_add=True
    )  # Optional: track when FAQ was added
    updated_at = models.DateTimeField(
        auto_now=True
    )  # Optional: track when FAQ was last updated

    def __str__(self):
        return f"FAQ for {self.chatbot.name}: {self.question[:50]}..."

    class Meta:
        # Optional: Ensure no duplicate FAQs for the same chatbot
        unique_together = ("chatbot", "question")


class ChatbotColor(models.Model):
    chatbot = models.OneToOneField(
        Chatbot, on_delete=models.CASCADE, related_name="colors"
    )
    bubbleBgColor = models.CharField(max_length=10, default="#111827")  # Hex color code
    bubbleColor = models.CharField(max_length=10, default="#FAFAFA")  # Hex color code
    chatBackgroundColor = models.CharField(max_length=10, default="#FAFAFA")
    chatBorder = models.CharField(max_length=10, default="#E5E7EB")
    headerBackgroundColor = models.CharField(max_length=10, default="#111827")
    headerTextColor = models.CharField(max_length=10, default="#FAFAFA")
    footerBackgroundColor = models.CharField(max_length=10, default="#FAFAFA")
    sendButtonColor = models.CharField(max_length=10, default="#111827")
    sendTextColor = models.CharField(max_length=10, default="#FAFAFA")
    headerText = models.CharField(max_length=50, default="Chat")
    inputBorderColor = models.CharField(max_length=10, default="#D1D5DC")
    placeholderText = models.CharField(max_length=100, default="Type your query...")
    inputTextColor = models.CharField(max_length=10, default="#111827")
    inputBgColor = models.CharField(max_length=10, default="#FAFAFA")
    questionTextColor = models.CharField(max_length=10, default="#FAFAFA")
    questionBackgroundColor = models.CharField(max_length=10, default="#FAFAFA")
    answerTextColor = models.CharField(max_length=10, default="#FAFAFA")
    answerBackgroundColor = models.CharField(max_length=10, default="#FAFAFA")
    faqTextColor = models.CharField(max_length=10, default="#FAFAFA")
    faqBackgroundColor = models.CharField(max_length=10, default="#FAFAFA")
    faqSectionBackgroundColor = models.CharField(max_length=10, default="#FAFAFA")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Colors for {self.chatbot.name}"

    class Meta:
        verbose_name = "Chatbot Color"
        verbose_name_plural = "Chatbot Colors"


class ChatbotQuota(models.Model):
    chatbot = models.OneToOneField(
        Chatbot, on_delete=models.CASCADE, related_name="quota"
    )
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        related_name="quotas",
        help_text="Current subscription plan",
    )

    # Message tracking
    messages_used = models.IntegerField(default=0)
    temporary_message_boost = models.IntegerField(
        default=0, help_text="Temporary message boost that resets at cycle end"
    )

    # Trial and Subscription Status
    is_trial = models.BooleanField(default=True)
    trial_start_date = models.DateTimeField(auto_now_add=True)

    is_paid = models.BooleanField(default=False)
    subscription_end_date = models.DateTimeField(null=True, blank=True)

    # Support team controls
    grace_period_days = models.IntegerField(default=3)  # Configurable grace period
    is_sending_enabled = models.BooleanField(default=True)  # Manual override

    last_payment_date = models.DateTimeField(null=True, blank=True)

    # Last Reset (for tracking quota resets)
    last_reset = models.DateTimeField(auto_now_add=True)
    is_lifetime_free = models.BooleanField(
        default=False,
        help_text="If true, chatbot has unlimited messages without a plan",
    )

    def get_message_limit(self):
        if self.is_lifetime_free or (
            self.subscription_plan and self.subscription_plan.is_lifetime
        ):
            return 0
        base_limit = (
            self.subscription_plan.message_limit if self.subscription_plan else 5000
        )
        return base_limit + self.temporary_message_boost

    def is_trial_valid(self):
        if self.is_lifetime_free:
            return False
        if not self.is_trial:
            return False
        trial_days = self.subscription_plan.trial_days if self.subscription_plan else 7
        trial_period = timedelta(days=trial_days)
        time_elapsed = timezone.now() - self.trial_start_date
        return time_elapsed <= trial_period

    def is_subscription_valid(self):
        if self.is_lifetime_free:
            return True
        if self.subscription_plan and self.subscription_plan.is_lifetime:
            return True
        if not self.is_paid or not self.subscription_end_date:
            return False
        grace_period = timedelta(days=self.grace_period_days)
        return timezone.now() <= (self.subscription_end_date + grace_period)

    def can_send_message(self):
        """
        Check if the chatbot can send messages:
        - Manual override takes precedence
        - During the trial (if active).
        - During a valid subscription (including grace period).
        """
        if not self.is_sending_enabled:
            return False
        if self.is_lifetime_free or (
            self.subscription_plan and self.subscription_plan.is_lifetime
        ):
            return True
        message_limit = self.get_message_limit()
        if self.is_trial:
            return self.is_trial_valid() and (
                message_limit == 0 or self.messages_used < message_limit
            )
        return self.is_subscription_valid() and (
            message_limit == 0 or self.messages_used < message_limit
        )

    def reset_quota(self):
        """Resets the message usage, temporary boost, and updates the reset timestamp."""
        self.messages_used = 0
        self.temporary_message_boost = 0
        self.last_reset = timezone.now()
        if not self.is_lifetime_free:  # Preserve grace period for lifetime free
            self.grace_period_days = 3
        self.is_sending_enabled = True
        self.save()

    def add_temporary_boost(self, additional_messages):
        """Add a temporary message boost that resets at the end of the cycle."""
        if self.is_lifetime_free:
            raise ValueError("Cannot add temporary boost to a lifetime free chatbot.")
        if additional_messages < 0:
            raise ValueError("Temporary boost cannot be negative.")
        self.temporary_message_boost += additional_messages
        self.save()

    def revoke_lifetime_plan(self):
        """Revoke lifetime plan, requiring a new subscription."""
        if self.is_lifetime_free or (
            self.subscription_plan and self.subscription_plan.is_lifetime
        ):
            self.is_lifetime_free = False
            self.subscription_plan = None
            self.is_paid = False
            self.is_trial = False
            self.subscription_end_date = None
            self.last_payment_date = None
            self.save()

    def __str__(self):
        plan_name = self.subscription_plan.name if self.subscription_plan else "No Plan"
        limit = self.get_message_limit()
        limit_str = "Unlimited" if limit == 0 else str(limit)
        return f"{self.chatbot.name} - {self.messages_used}/{limit_str} ({plan_name})"


class CouponCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Discount percentage (0-100)"
    )
    max_usage = models.PositiveIntegerField(
        help_text="Maximum number of times this coupon can be used"
    )
    times_used = models.PositiveIntegerField(
        default=0, help_text="Number of times this coupon has been used"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    used_by_chatbots = models.ManyToManyField(
        "Chatbot", related_name="used_coupons", blank=True
    )

    def is_valid(self, chatbot):
        """Check if the coupon is valid: active, usage limit not exceeded, and not used by this chatbot."""
        return (
            self.is_active
            and self.times_used < self.max_usage
            and chatbot not in self.used_by_chatbots.all()
        )

    def apply(self, chatbot):
        """Increment usage count and link the chatbot when coupon is applied."""
        if self.is_valid(chatbot):
            self.times_used += 1
            self.used_by_chatbots.add(chatbot)
            self.save()
            return True
        return False

    def __str__(self):
        return f"{self.code} - {self.discount_percent}% off ({self.times_used}/{self.max_usage})"

    class Meta:
        verbose_name = "Coupon Code"
        verbose_name_plural = "Coupon Codes"


class ChatbotPaymentTransaction(models.Model):
    chatbot = models.ForeignKey(
        Chatbot, on_delete=models.CASCADE, related_name="transactions"
    )
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transactions",
    )
    transaction_id = models.CharField(max_length=255, unique=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Original plan price"
    )
    discounted_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    coupon_code = models.ForeignKey(
        CouponCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    def __str__(self):
        return f"{self.chatbot.name} - {self.transaction_id} - {self.amount} NPR"

    @staticmethod
    def create_and_confirm_transaction(
        chatbot,
        payment_amount,
        payment_transaction_code,
        subscription_plan_id,
        coupon_code=None,
    ):
        """Creates and confirms a transaction based on payment data and selected plan."""
        if ChatbotPaymentTransaction.objects.filter(
            transaction_id=payment_transaction_code
        ).exists():
            raise ValueError("Duplicate payment transaction code.")

        try:
            plan = SubscriptionPlan.objects.get(id=subscription_plan_id, is_active=True)
            if plan.is_lifetime:
                raise ValueError("Lifetime plans do not require payment.")
        except SubscriptionPlan.DoesNotExist:
            raise ValueError(
                "Selected subscription plan does not exist or is inactive."
            )

        applied_coupon = None
        original_amount = plan.price

        if coupon_code:
            try:
                coupon = CouponCode.objects.get(code=coupon_code)
                if not coupon.is_valid(chatbot):
                    raise ValueError(
                        "Coupon code is invalid, expired, or already used by this chatbot."
                    )
                expected_discounted = float(original_amount) * (
                    1 - float(coupon.discount_percent) / 100
                )
                if abs(float(payment_amount) - expected_discounted) > 1:
                    raise ValueError(
                        "Payment amount does not match the discounted plan price."
                    )
                applied_coupon = coupon
            except CouponCode.DoesNotExist:
                raise ValueError("Coupon code does not exist.")
        else:
            if float(payment_amount) != float(original_amount):
                raise ValueError(
                    f"Payment amount must be {original_amount} NPR for the selected plan."
                )

        transaction = ChatbotPaymentTransaction.objects.create(
            chatbot=chatbot,
            subscription_plan=plan,
            transaction_id=payment_transaction_code,
            amount=original_amount,
            discounted_amount=payment_amount if coupon_code else None,
            coupon_code=applied_coupon,
        )

        if applied_coupon:
            applied_coupon.apply(chatbot)

        quota = chatbot.quota
        quota.subscription_plan = plan
        quota.is_paid = True
        quota.is_trial = False
        quota.messages_used = 0
        quota.temporary_message_boost = 0
        quota.grace_period_days = 3
        quota.subscription_end_date = timezone.now() + timedelta(days=30)
        quota.last_payment_date = transaction.payment_date
        quota.save()

        return transaction


class OrganizationInvitation(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("expired", "Expired"),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    invited_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="sent_invitations"
    )
    email = models.EmailField()
    invitation_code = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        # Generate invitation code if it doesn't exist
        if not self.invitation_code:
            self.invitation_code = str(uuid.uuid4())

        # Set expiration date if not set (default 7 days)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)

        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if the invitation is still valid (pending and not expired)."""
        return self.status == "pending" and timezone.now() < self.expires_at

    def accept(self, user):
        """Accept invitation and link user to the organization."""
        if not self.is_valid():
            return False

        # Link user to organization
        user.organization = self.organization
        user.is_owner = False  # Invited users are not owners
        user.save()

        # Mark invitation as accepted
        self.status = "accepted"
        self.save()
        return True

    def decline(self):
        """Decline the invitation."""
        if self.status == "pending":
            self.status = "declined"
            self.save()
            return True
        return False

    def __str__(self):
        return f"Invitation to {self.email} for {self.organization.name}"


class ChatbotTokenUsage(models.Model):
    chatbot = models.ForeignKey(
        Chatbot, on_delete=models.CASCADE, related_name="token_usage"
    )
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.chatbot.name} - {self.total_tokens} tokens on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    @classmethod
    def log_usage(cls, chatbot, input_tokens, output_tokens):
        total_tokens = input_tokens + output_tokens
        return cls.objects.create(
            chatbot=chatbot,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


class ChatbotConversation(models.Model):
    chatbot = models.ForeignKey("Chatbot", on_delete=models.CASCADE)
    user_id = models.CharField(max_length=100)  # Platform-specific ID
    platform = models.CharField(
        max_length=20,
        choices=[
            ("whatsapp", "WhatsApp"),
            ("messenger", "Messenger"),
            ("instagram", "Instagram"),
        ],
    )
    history = models.TextField(default="[]")  # Store JSON as text
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("chatbot", "user_id", "platform")

    def get_history(self):
        """Deserialize history from text to list."""
        try:
            return json.loads(self.history)
        except json.JSONDecodeError:
            return []

    def set_history(self, history_list):
        """Serialize history list to text."""
        self.history = json.dumps(history_list)

    def trim_history(self, max_exchanges=10):
        """Trim history to last max_exchanges."""
        history = self.get_history()
        if len(history) > max_exchanges:
            self.set_history(history[-max_exchanges:])
            self.save()


class ChatbotAPILog(models.Model):
    chatbot = models.ForeignKey("Chatbot", on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    platform = models.CharField(max_length=50, null=True, blank=True)
    user_id = models.CharField(max_length=100, null=True, blank=True)
    query = models.TextField(null=True, blank=True)
    query_embedding = models.BinaryField(null=True, blank=True)

    def set_embedding(self, embedding):
        self.query_embedding = pickle.dumps(embedding)

    def get_embedding(self):
        return pickle.loads(self.query_embedding) if self.query_embedding else None

    class Meta:
        indexes = [
            models.Index(fields=["chatbot", "timestamp"]),
        ]
