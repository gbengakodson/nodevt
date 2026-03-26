from django.contrib import admin
from .models import CryptoToken, UserTokenBalance, Purchase

@admin.register(CryptoToken)
class CryptoTokenAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'current_price', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('symbol', 'name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(UserTokenBalance)
class UserTokenBalanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'quantity', 'average_buy_price', 'current_value')
    list_filter = ('token', 'created_at')
    search_fields = ('user__email', 'token__symbol')
    readonly_fields = ('created_at', 'updated_at')
    
    def current_value(self, obj):
        return obj.current_value
    current_value.short_description = 'Current Value'

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'quantity', 'price_per_token', 'total_amount', 'node_fee', 'created_at')
    list_filter = ('token', 'created_at')
    search_fields = ('user__email', 'token__symbol')
    readonly_fields = ('created_at',)