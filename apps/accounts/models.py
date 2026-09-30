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
    api_passphrase = models.TextField(blank=True, default='')
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

    # New fields for the redesigned service
    fee_paid_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    withdrawal_disabled = models.BooleanField(default=False)


    def get_api_secret(self):
        from apps.wallets.security.encryption import EncryptionService
        return EncryptionService.decrypt(self.api_secret)

    def set_api_passphrase(self, passphrase):
        from apps.wallets.security.encryption import EncryptionService
        if passphrase:
            self.api_passphrase = EncryptionService.encrypt(passphrase)
        else:
            self.api_passphrase = ''

    def get_api_passphrase(self):
        from apps.wallets.security.encryption import EncryptionService
        if not self.api_passphrase:
            return ''
        return EncryptionService.decrypt(self.api_passphrase)

    def set_api_key(self, key):
        from apps.wallets.security.encryption import EncryptionService
        if key:
            self.api_key = EncryptionService.encrypt(key)
        else:
            self.api_key = ''

    def set_api_secret(self, secret):
        from apps.wallets.security.encryption import EncryptionService
        if secret:
            self.api_secret = EncryptionService.encrypt(secret)
        else:
            self.api_secret = ''

    def get_api_key(self):
        from apps.wallets.security.encryption import EncryptionService
        return EncryptionService.decrypt(self.api_key)

    def get_client(self):
        """Return a unified CCXT client for the connection's exchange."""
        import ccxt
        exchange_id = self.exchange.lower()
        if not hasattr(ccxt, exchange_id):
            return None
        exchange_class = getattr(ccxt, exchange_id)

        params = {
            'apiKey': self.get_api_key(),
            'secret': self.get_api_secret(),
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
        }

        # OKX, KuCoin, Bitget require an API passphrase
        if self.exchange in ('OKX', 'KUCOIN', 'BITGET'):
            params['password'] = self.get_api_passphrase()

        return exchange_class(params)

    def test_connection(self):
        """
        Verify API credentials work and return the stablecoin balance.
        Returns: success, can_trade, stable_balance (USDT + USDC), and error if any.
        """
        try:
            client = self.get_client()
            if not client:
                return {'success': False, 'error': f'Unsupported exchange: {self.exchange}'}

            # Fetch balance — proves credentials are valid
            balance = client.fetch_balance()

            # Extract stablecoin balance
            total = balance.get('total', {}) or {}
            usdt = float(total.get('USDT', 0) or 0)
            usdc = float(total.get('USDC', 0) or 0)
            stable = usdt + usdc

            # Confirm trading capability
            can_trade = client.has.get('createOrder', False)

            # Update last sync time
            from django.utils import timezone
            self.last_sync_at = timezone.now()
            self.save(update_fields=['last_sync_at'])

            return {
                'success': True,
                'can_trade': can_trade,
                'stable_balance': stable,
                'usdt': usdt,
                'usdc': usdc,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def check_withdrawal_disabled(self):
        """
        Verify that the API key does not have withdrawal permission.
        Returns True if we can confirm withdrawal is disabled, False otherwise.
        """
        try:
            client = self.get_client()
            if not client:
                return False

            exchange = self.exchange.lower()

            if exchange == 'binance':
                try:
                    resp = client.sapi_get_account_apirestrictions()
                    return not resp.get('enableWithdrawals', True)
                except Exception:
                    return False

            if exchange == 'okx':
                try:
                    resp = client.private_get_account_config()
                    perms = resp.get('data', [{}])[0].get('perm', '')
                    return 'withdraw' not in perms
                except Exception:
                    return False

            # Bybit, KuCoin, Gate.io, MEXC, Bitget — CCXT doesn't expose a
            # unified permission check. Attempt a probe where possible.
            if exchange in ('bybit', 'kucoin', 'gateio', 'mexc', 'bitget'):
                # Attempt to read the API key's info. Most of these exchanges
                # will not allow a "read-only" method that reveals permissions,
                # so we default to unverified (False).
                return False

            return False
        except Exception:
            return False


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