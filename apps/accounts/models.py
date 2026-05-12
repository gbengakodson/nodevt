from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
import random
import string
from django.conf import settings


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    wallet_address = models.CharField(max_length=100, blank=True, null=True)
    referral_code = models.CharField(max_length=5, unique=True, blank=True, null=True)
    referrer = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_users'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_set',
        blank=True,
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    # KYC Fields
    is_verified = models.BooleanField(default=False)
    kyc_status = models.CharField(max_length=20, default='NONE', choices=[
        ('NONE', 'Not Submitted'),
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ])
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True)
    date_verified = models.DateTimeField(null=True, blank=True)

    id_type = models.CharField(max_length=20, blank=True, null=True, choices=[
        ('NIN', 'NIN'),
        ('PASSPORT', 'Passport'),
        ('DRIVERS', 'Driver\'s License'),
        ('VOTER', 'Voter\'s Card'),
        ('NATIONAL_ID', 'National ID'),
    ])
    id_number = models.CharField(max_length=50, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)

    def generate_referral_code(self):
        """Generate a unique 5-digit numeric code"""
        while True:
            code = ''.join(random.choices(string.digits, k=5))
            if not User.objects.filter(referral_code=code).exists():
                return code

    def __str__(self):
        return self.email



class OTPCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otp_codes')
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=[
        ('LOGIN', 'Login'),
        ('WITHDRAWAL', 'Withdrawal'),
    ])
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
