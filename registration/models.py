from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid
from django.utils import timezone
from datetime import timedelta

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
    domain_name = models.TextField(max_length=1000,null=True, unique=False,blank=True)

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
    

class ChatbotPaymentTransaction(models.Model):
    PACKAGE_CHOICES = [
        (5000, '5000 NPR - 5000 Messages'),
        (7000, '7000 NPR - 7000 Messages'),
        (10000, '10000 NPR - 10000 Messages'),
    ]

    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name="transactions")
    transaction_id = models.CharField(max_length=255, unique=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    amount = models.IntegerField(choices=PACKAGE_CHOICES)

    def __str__(self):
        return f"{self.chatbot.name} - {self.transaction_id} - {self.amount} NPR"

    @staticmethod
    def create_transaction(chatbot, amount):
        """
        Creates a payment transaction and updates chatbot quota.
        Each package provides equivalent messages and extends validity by 30 days.
        """
        if amount not in [5000, 7000, 10000]:
            raise ValueError("Invalid package amount.")

        # Create the payment transaction
        transaction = ChatbotPaymentTransaction.objects.create(
            chatbot=chatbot,
            transaction_id=str(uuid.uuid4()),
            amount=amount
        )

        # Update chatbot quota
        quota = chatbot.quota
        quota.is_paid = True
        quota.message_limit += amount  # Each NPR amount corresponds to message count

        # Extend subscription by 30 days (or start a new subscription if none exists)
        if quota.subscription_end_date and quota.subscription_end_date > timezone.now():
            quota.subscription_end_date += timedelta(days=30)
        else:
            quota.subscription_end_date = timezone.now() + timedelta(days=30)

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