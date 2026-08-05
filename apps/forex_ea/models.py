import uuid
import hashlib
from django.db import models
from django.conf import settings

class UserForexProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forex_profile')
    mt5_account = models.CharField(max_length=20, unique=True)
    broker = models.CharField(max_length=50)
    api_key_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def generate_api_key(cls):
        raw = uuid.uuid4().hex + uuid.uuid4().hex
        return 'nv_' + raw[:40]

    def set_api_key(self, raw_key):
        self.api_key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    def check_api_key(self, raw_key):
        return self.api_key_hash == hashlib.sha256(raw_key.encode()).hexdigest()


class ForexTrade(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    mt5_account = models.CharField(max_length=20)
    ticket = models.BigIntegerField()
    symbol = models.CharField(max_length=20)
    open_time = models.DateTimeField()
    close_time = models.DateTimeField()
    profit = models.DecimalField(max_digits=15, decimal_places=2)
    volume = models.DecimalField(max_digits=10, decimal_places=2)
    trade_type = models.CharField(max_length=10)
    magic_number = models.IntegerField()
    fee_deducted = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class ForexMLM(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mlm_profile')
    sponsor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sponsored_users')
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get_upline(cls, user, levels=5):
        upline = []
        current = user.mlm_profile.sponsor if hasattr(user, 'mlm_profile') else None
        while current and len(upline) < levels:
            upline.append(current)
            current = current.mlm_profile.sponsor if hasattr(current, 'mlm_profile') else None
        return upline


class ForexCommission(models.Model):
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='commission_given')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='commission_received')
    trade = models.ForeignKey(ForexTrade, on_delete=models.CASCADE)
    level = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

class MasterAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='master_account')
    mt5_account = models.CharField(max_length=20)
    api_key_hash = models.CharField(max_length=128)  # master EA uses this
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SlaveAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='slave_accounts')
    mt5_account = models.CharField(max_length=20)
    mt5_password_encrypted = models.TextField()  # encrypted with EncryptionService
    broker_server = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)



class MasterTrade(models.Model):
    # The user who reported the trade (the master)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    master_mt5_account = models.CharField(max_length=20)
    symbol = models.CharField(max_length=20)
    direction = models.CharField(max_length=4)  # BUY/SELL
    volume = models.FloatField()
    open_price = models.FloatField()
    open_time = models.DateTimeField()
    ticket = models.BigIntegerField()
    magic_number = models.IntegerField()
    status = models.CharField(max_length=20, default='pending')  # pending, executing, closed
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SlaveTrade(models.Model):
    master_trade = models.ForeignKey(MasterTrade, on_delete=models.CASCADE, related_name='slave_trades')
    slave_account = models.ForeignKey(SlaveAccount, on_delete=models.CASCADE)
    slave_ticket = models.BigIntegerField(null=True, blank=True)
    closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)



class MarketWeather(models.Model):
    symbol = models.CharField(max_length=20, unique=True)   # e.g. EURUSD, BTC, AAPL
    category = models.CharField(max_length=20, default='forex')  # forex, crypto, stock
    weather = models.CharField(max_length=50, default='Sunny')   # e.g. "Storm", "Rainy in the Plateau"
    trend = models.CharField(max_length=20, default='NEUTRAL')   # UPTREND, DOWNTREND, CONSOLIDATION
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol} - {self.weather}"


class DailyIntelligence(models.Model):
    CATEGORY_CHOICES = [
        ('forex', 'Forex'),
        ('crypto', 'Crypto'),
        ('stock', 'Stock'),
        ('economic', 'Economic'),
    ]
    TREND_CHOICES = [
        ('UPTREND', 'Uptrend'),
        ('DOWNTREND', 'Downtrend'),
        ('CONSOLIDATION', 'Consolidation'),
    ]

    symbol = models.CharField(max_length=20)          # e.g. EURUSD, BTC, AAPL, NGN
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    caption = models.CharField(max_length=100)        # "Strong Sell", "Deep Discount -22%", etc.
    trend = models.CharField(max_length=20, choices=TREND_CHOICES, default='CONSOLIDATION')
    image_url = models.URLField(blank=True, null=True)
    created_at = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('symbol', 'created_at')    # one entry per symbol per day

    def __str__(self):
        return f"{self.symbol} ({self.created_at}) - {self.caption}"


class CoinReaction(models.Model):
    REACTION_CHOICES = [
        ('like', 'Like'),
        ('love', 'Love'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    coin_symbol = models.CharField(max_length=10)
    reaction = models.CharField(max_length=5, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'coin_symbol', 'reaction')