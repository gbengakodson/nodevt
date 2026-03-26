from django.db import models
from django.conf import settings
import uuid


class YieldDistribution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='yield_distributions')
    token_balance = models.ForeignKey('tokens.UserTokenBalance', on_delete=models.CASCADE,
                                      related_name='yield_distributions')
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    distribution_number = models.IntegerField()  # 1-720
    month_year = models.CharField(max_length=7)  # Format: YYYY-MM
    is_credited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    credited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - Distribution {self.distribution_number} - {self.amount}"