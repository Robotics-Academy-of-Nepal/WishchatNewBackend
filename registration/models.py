from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid
from django.utils import timezone
from datetime import timedelta
import uuid
import json, pickle

class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True, null=True)


    def total_messages_used(self):
        """Get total messages used across all chatbots in this organization."""
        from django.db.models import Sum
        return self.chatbots.aggregate(
            total=Sum('quota__messages_used')
        )['total'] or 0

    def total_tokens_used(self):
        """Get total tokens used across all chatbots."""
        from django.db.models import Sum
        return ChatbotTokenUsage.objects.filter(
            chatbot__organization=self
        ).aggregate(
            total=Sum('total_tokens'),
            input=Sum('input_tokens'),
            output=Sum('output_tokens')
        )
    
    def total_tokens_used_by_month(self, year, month):
        """Get total tokens used across all chatbots."""
        from django.db.models import Sum
        return ChatbotTokenUsage.objects.filter(
            chatbot__organization=self,
            timestamp__year=year,
            timestamp__month=month
        ).aggregate(
            total=Sum('total_tokens'),
            input=Sum('input_tokens'),
            output=Sum('output_tokens')
        )

    def __str__(self):
        return self.name


class CustomUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, organization=None, **extra_fields):
        if not email:
            raise ValueError('The Email field is required')

        email = self.normalize_email(email)
        
        # New signups without an organization become owners
        is_owner = organization is None
        user = self.model(
            email=email,
            username=username,
            organization=organization,
            is_owner=is_owner,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, username, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    # User Information
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=15, unique=False, null=True, blank=True)

    # Organization Link
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members', null=True, blank=True)
    is_owner = models.BooleanField(default=False)  # To track if the user is an organization owner

    # Permissions
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Custom User Manager
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.email

class Chatbot(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='chatbots')
    name = models.CharField(max_length=100)
    api_key = models.CharField(max_length=100, unique=True, editable=False)
    azure_index_name = models.CharField(max_length=200, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    system_prompt = models.TextField(max_length=200000,null=True, unique=False,blank=True)
    whatsapp_url = models.TextField(max_length=200,null=True, unique=False,blank=True)
    whatsapp_token = models.CharField(max_length=1000,null=True,blank=True,unique=False)
    whatsapp_id = models.CharField(max_length=50,null=True,blank=True,unique=False)
    messenger_url = models.TextField(max_length=200,null=True, unique=False,blank=True)
    messenger_token = models.CharField(max_length=1000,null=True,blank=True,unique=False)
    messenger_page_id = models.CharField(max_length=50,null=True,blank=True,unique=False)
    instagram_url = models.TextField(max_length=200,null=True, unique=False,blank=True)
    instagram_token = models.CharField(max_length=1000,null=True,blank=True,unique=False)
    instagram_page_id = models.CharField(max_length=50,null=True,blank=True,unique=False)
    domain_name = models.TextField(max_length=1000,null=True, unique=True,blank=True)
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
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='faqs')
    question = models.TextField(max_length=1000)  # FAQ question
    answer = models.TextField(max_length=10000)   # FAQ answer
    created_at = models.DateTimeField(auto_now_add=True)  # Optional: track when FAQ was added
    updated_at = models.DateTimeField(auto_now=True)      # Optional: track when FAQ was last updated

    def __str__(self):
        return f"FAQ for {self.chatbot.name}: {self.question[:50]}..."

    class Meta:
        # Optional: Ensure no duplicate FAQs for the same chatbot
        unique_together = ('chatbot', 'question')

class ChatbotColor(models.Model):
    chatbot = models.OneToOneField(Chatbot, on_delete=models.CASCADE, related_name='colors')
    bubbleBgColor = models.CharField(max_length=10, default="#111827")  # Hex color code
    bubbleColor = models.CharField(max_length=10, default="#FAFAFA")    # Hex color code
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
    chatbot = models.OneToOneField(Chatbot, on_delete=models.CASCADE, related_name="quota")
    
    # Message tracking
    messages_used = models.IntegerField(default=0)
    message_limit = models.IntegerField(default=5000)  # Free trial default: 5000 messages

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

    def is_trial_valid(self):
        """Check if the chatbot's trial period (7 days) is active."""
        return (timezone.now() - self.trial_start_date) <= timedelta(days=7)

    def is_subscription_valid(self):
        """Check if the chatbot's paid subscription is within the validity + configured grace."""
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
            
        if self.is_trial:
            return self.is_trial_valid() and self.messages_used < self.message_limit
        return self.is_subscription_valid() and self.messages_used < self.message_limit

    def reset_quota(self):
        """Resets the message usage and updates the reset timestamp."""
        self.messages_used = 0
        self.last_reset = timezone.now()
        self.grace_period_days = 3
        self.is_sending_enabled = True
        self.save()

    def __str__(self):
        return f"{self.chatbot.name} - {self.messages_used}/{self.message_limit}"
    

class CouponCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, help_text="Discount percentage (0-100)")
    max_usage = models.PositiveIntegerField(help_text="Maximum number of times this coupon can be used")
    times_used = models.PositiveIntegerField(default=0, help_text="Number of times this coupon has been used")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    used_by_chatbots = models.ManyToManyField('Chatbot', related_name='used_coupons', blank=True)

    def is_valid(self, chatbot):
        """Check if the coupon is valid: active, usage limit not exceeded, and not used by this chatbot."""
        return (
            self.is_active and 
            self.times_used < self.max_usage and 
            chatbot not in self.used_by_chatbots.all()
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
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name="transactions")
    transaction_id = models.CharField(max_length=255, unique=True, help_text="Payment portal transaction_code")
    payment_date = models.DateTimeField(auto_now_add=True)
    amount = models.IntegerField(help_text="Original package amount (5000, 7000, 10000)")
    discounted_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Amount paid after discount")
    coupon_code = models.ForeignKey(CouponCode, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")

    def __str__(self):
        return f"{self.chatbot.name} - {self.transaction_id} - {self.amount} NPR"

    @staticmethod
    def create_and_confirm_transaction(chatbot, payment_amount, payment_transaction_code, coupon_code=None):
        """Creates and confirms a transaction based on payment data."""
        if ChatbotPaymentTransaction.objects.filter(transaction_id=payment_transaction_code).exists():
            raise ValueError("Duplicate payment transaction code.")

        VALID_AMOUNTS = [5000, 7000, 10000]
        applied_coupon = None
        original_amount = None

        if coupon_code:  # Discount applied
            try:
                coupon = CouponCode.objects.get(code=coupon_code)
                if not coupon.is_valid(chatbot):
                    raise ValueError("Coupon code is invalid, expired, or already used by this chatbot.")
                # Map discounted amount back to original package
                for amt in VALID_AMOUNTS:
                    expected_discounted = amt * (1 - coupon.discount_percent / 100)
                    if abs(float(payment_amount) - float(expected_discounted)) < 1:  # Small float variance
                        original_amount = amt
                        applied_coupon = coupon
                        break
                if not original_amount:
                    raise ValueError("Payment amount does not match any discounted package.")
            except CouponCode.DoesNotExist:
                raise ValueError("Coupon code does not exist.")
        else:  # No discount
            if payment_amount not in VALID_AMOUNTS:
                raise ValueError("Payment amount must be 5000, 7000, or 10000 NPR.")
            original_amount = payment_amount

        transaction = ChatbotPaymentTransaction.objects.create(
            chatbot=chatbot,
            transaction_id=payment_transaction_code,
            amount=original_amount,
            discounted_amount=payment_amount if coupon_code else None,
            coupon_code=applied_coupon
        )

        if applied_coupon:
            applied_coupon.apply(chatbot)


        quota = chatbot.quota
        quota.is_paid = True
        quota.message_limit = original_amount  # Reset to original package amount
        quota.messages_used = 0
        quota.subscription_end_date = timezone.now() + timedelta(days=30)
        quota.last_payment_date = transaction.payment_date
        quota.save()

        return transaction
    
class OrganizationInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='invitations')
    invited_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_invitations')
    email = models.EmailField()
    invitation_code = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
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
        return self.status == 'pending' and timezone.now() < self.expires_at
    
    def accept(self, user):
        """Accept invitation and link user to the organization."""
        if not self.is_valid():
            return False
        
        # Link user to organization
        user.organization = self.organization
        user.is_owner = False  # Invited users are not owners
        user.save()
        
        # Mark invitation as accepted
        self.status = 'accepted'
        self.save()
        return True
    
    def decline(self):
        """Decline the invitation."""
        if self.status == 'pending':
            self.status = 'declined'
            self.save()
            return True
        return False
    
    def __str__(self):
        return f"Invitation to {self.email} for {self.organization.name}"
    

class ChatbotTokenUsage(models.Model):
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='token_usage')
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.chatbot.name} - {self.total_tokens} tokens on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def log_usage(cls, chatbot, input_tokens, output_tokens):
        total_tokens = input_tokens + output_tokens
        return cls.objects.create(
            chatbot=chatbot,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens
        )
    
class ChatbotConversation(models.Model):
    chatbot = models.ForeignKey('Chatbot', on_delete=models.CASCADE)
    user_id = models.CharField(max_length=100)  # Platform-specific ID
    platform = models.CharField(max_length=20, choices=[('whatsapp', 'WhatsApp'), ('messenger', 'Messenger'), ('instagram', 'Instagram')])
    history = models.TextField(default='[]')  # Store JSON as text
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('chatbot', 'user_id', 'platform')

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
    chatbot = models.ForeignKey('Chatbot', on_delete=models.CASCADE)
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
            models.Index(fields=['chatbot', 'timestamp']),
        ]

