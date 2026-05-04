from django.db import models
from django.conf import settings
import uuid


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

    # New fields
    price_at_creation = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    auto_closed_at = models.DateTimeField(null=True, blank=True)

    @property
    def current_grid_level(self):
        if not self.token.current_price:
            return 0
        price_range = self.upper_price - self.lower_price
        if price_range == 0:
            return 0
        grid_step = price_range / self.grids
        level = (self.token.current_price - self.lower_price) / grid_step
        return max(0, min(self.grids, int(level)))

    @property
    def pnl(self):
        """Calculate PNL based on current grid level vs entry"""
        entry_level = self.grids // 2
        current_level = self.current_grid_level
        if entry_level == 0:
            return 0
        price_diff_percent = ((current_level - entry_level) / entry_level) * 100
        return (price_diff_percent / 100) * float(self.amount)

    @property
    def pnl_percent(self):
        if self.amount == 0:
            return 0
        return (self.pnl / float(self.amount)) * 100

    @property
    def should_auto_close(self):
        """Auto close when PNL reaches 20%"""
        return self.pnl_percent >= 20 and self.status == 'ACTIVE'

    def __str__(self):
        return f"{self.user.email} - {self.token.symbol} - ${self.amount}"