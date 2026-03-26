from django.contrib import admin
from .models import YieldDistribution

@admin.register(YieldDistribution)
class YieldDistributionAdmin(admin.ModelAdmin):
    list_display = ('user', 'token_balance', 'amount', 'distribution_number', 'month_year', 'is_credited', 'created_at')
    list_filter = ('is_credited', 'month_year', 'created_at')
    search_fields = ('user__email', 'token_balance__token__symbol')
    readonly_fields = ('created_at',)
    list_editable = ('is_credited',)