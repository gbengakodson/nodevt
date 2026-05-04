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

    @property
    def pnl(self):
        if self.price_at_creation == 0:
            return Decimal('0')
        price_diff = self.token.current_price - self.price_at_creation
        price_diff_percent = price_diff / self.price_at_creation
        return price_diff_percent * self.amount

    @property
    def pnl_percent(self):
        if self.price_at_creation == 0:
            return Decimal('0')
        return ((self.token.current_price - self.price_at_creation) / self.price_at_creation) * 100