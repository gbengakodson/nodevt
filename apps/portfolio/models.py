from django.db import models
from django.conf import settings
import uuid


class UserGoal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goal')
    target_amount = models.DecimalField(max_digits=20, decimal_places=2, default=10000)
    target_years = models.IntegerField(default=2)
    monthly_addition = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - Target: ${self.target_amount} in {self.target_years} years"