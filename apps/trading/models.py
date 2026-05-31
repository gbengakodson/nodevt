from django.db import models
from django.conf import settings
import uuid
from decimal import Decimal


class GridBot(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('STOPPED', 'Stopped'),
        ('COMPLETED', 'Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='grid_bots')
    token = models.ForeignKey('tokens.CryptoToken', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    lower_price = models.DecimalField(max_digits=20, decimal_places=8)
    upper_price = models.DecimalField(max_digits=20, decimal_places=8)
    grids = models.IntegerField(default=100)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    grid_profit = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    pnl = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    pnl_percent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_yield_earned = models.DecimalField(max_digits=20, decimal_places=8, default=0)  # NEW


    # ADD THESE FIELDS
    price_at_creation = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    stopped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def current_grid_level(self):
        if not self.token.current_price:
            return 0
        price_range = self.upper_price - self.lower_price
        if price_range <= 0:
            return self.grids // 2
        grid_step = price_range / self.grids
        level = (self.token.current_price - self.lower_price) / grid_step
        return max(0, min(self.grids, int(level)))



class MasterGridBot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.ForeignKey('tokens.CryptoToken', on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=20, decimal_places=8)
    lower_price = models.DecimalField(max_digits=20, decimal_places=8)
    upper_price = models.DecimalField(max_digits=20, decimal_places=8)
    grids = models.IntegerField(default=100)
    status = models.CharField(max_length=10, choices=[('ACTIVE','Active'),('STOPPED','Stopped'),('COMPLETED','Completed')], default='ACTIVE')
    grid_profit = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    price_at_creation = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
