from django.db import models

class PlatformSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_settings'

    def __str__(self):
        return f"{self.key}: {self.value}%"