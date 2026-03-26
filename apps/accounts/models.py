from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
import random
import string


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