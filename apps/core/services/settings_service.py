from decimal import Decimal
from apps.core.models import PlatformSetting


class SettingsService:

    @classmethod
    def get(cls, key, default=0):
        try:
            setting = PlatformSetting.objects.get(key=key)
            return setting.value
        except PlatformSetting.DoesNotExist:
            return Decimal(str(default))

    @classmethod
    def set(cls, key, value, description=''):
        setting, created = PlatformSetting.objects.get_or_create(
            key=key,
            defaults={'value': Decimal(str(value)), 'description': description}
        )
        if not created:
            setting.value = Decimal(str(value))
            if description:
                setting.description = description
            setting.save()
        return setting

    @classmethod
    def get_yield_rate(cls):
        """Get current monthly yield rate (default 10%)"""
        return cls.get('monthly_yield_rate', 10)

    @classmethod
    def get_hourly_yield_rate(cls):
        """Get hourly yield rate (monthly / 720)"""
        monthly = cls.get_yield_rate()
        return monthly / 720