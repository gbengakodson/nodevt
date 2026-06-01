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

    user_type = models.CharField(max_length=20, default='MICRO', choices=[
        ('MICRO', 'Micro-Investor'),
        ('SALARY', 'Salary Earner'),
        ('BUSINESS', 'Business Owner / HNI'),
        ('REFERRAL', 'Referral Builder'),
        ('DIASPORA', 'Diaspora Nigerian'),
    ])
    profile_picture = models.URLField(blank=True, null=True)
    profile_caption = models.TextField(max_length=200, blank=True, null=True)

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


class ExchangeAPIConnection(models.Model):
    EXCHANGE_CHOICES = [
        ('BINANCE', 'Binance'),
        ('BYBIT', 'Bybit'),
        ('OKX', 'OKX'),
        ('KUCOIN', 'KuCoin'),
        ('GATEIO', 'Gate.io'),
        ('MEXC', 'MEXC'),
        ('BITGET', 'Bitget'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exchange_connections')
    exchange = models.CharField(max_length=20, choices=EXCHANGE_CHOICES)
    api_key = models.TextField()
    api_secret = models.TextField()
    label = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    min_capital = models.DecimalField(max_digits=20, decimal_places=8, default=1000)
    fee_per_trade = models.DecimalField(max_digits=10, decimal_places=4, default=0.01)
    created_at = models.DateTimeField(auto_now_add=True)
    # Add to ExchangeAPIConnection model
    aum_amount = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    monthly_fee = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    fee_last_charged = models.DateTimeField(null=True, blank=True)
    grids_paused = models.BooleanField(default=False)
    warning_sent_at = models.DateTimeField(null=True, blank=True)  # When first warning was sent

    def set_api_secret(self, secret):
        from apps.wallets.security.encryption import EncryptionService
        self.api_secret = EncryptionService.encrypt(secret)

    def get_api_secret(self):
        from apps.wallets.security.encryption import EncryptionService
        return EncryptionService.decrypt(self.api_secret)

    def set_api_key(self, key):
        from apps.wallets.security.encryption import EncryptionService
        self.api_key = EncryptionService.encrypt(key)

    def get_api_key(self):
        from apps.wallets.security.encryption import EncryptionService
        return EncryptionService.decrypt(self.api_key)

    def test_connection(self):
        """Test if the API credentials work"""
        try:
            if self.exchange == 'BINANCE':
                from binance.client import Client
                client = Client(self.get_api_key(), self.get_api_secret())
                account = client.get_account()
                return {'success': True, 'can_trade': account.get('canTrade', False)}
            else:
                return {'success': True, 'message': f'{self.exchange} connection stored'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_client(self):
        """Get exchange client instance"""
        if self.exchange == 'BINANCE':
            from binance.client import Client
            return Client(self.get_api_key(), self.get_api_secret())
        # Add other exchanges as needed
        return None


class ExchangeRequest(models.Model):
    DIRECTION_CHOICES = [
        ('BUY', 'Buy Crypto (Naira → Crypto)'),
        ('SELL', 'Sell Crypto (Crypto → Naira)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField()  # User's email (may not be a NODE user)
    amount = models.DecimalField(max_digits=20, decimal_places=8)  # USDC/USDT amount
    destination_wallet = models.CharField(max_length=42)  # External wallet address
    direction = models.CharField(max_length=4, choices=DIRECTION_CHOICES)
    pin_hash = models.CharField(max_length=64)  # Hashed PIN
    pin_expiry = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    is_processed = models.BooleanField(default=False)
    tx_hash = models.CharField(max_length=66, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']