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
