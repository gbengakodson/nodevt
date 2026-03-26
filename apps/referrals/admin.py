from django.contrib import admin
from .models import ReferralLevel, ReferralRelationship, ReferralEarning

@admin.register(ReferralLevel)
class ReferralLevelAdmin(admin.ModelAdmin):
    list_display = ('level', 'percentage', 'created_at')
    list_editable = ('percentage',)
    readonly_fields = ('created_at',)

@admin.register(ReferralRelationship)
class ReferralRelationshipAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referred', 'level', 'created_at')
    list_filter = ('level', 'created_at')
    search_fields = ('referrer__email', 'referred__email')
    readonly_fields = ('created_at',)

@admin.register(ReferralEarning)
class ReferralEarningAdmin(admin.ModelAdmin):
    list_display = ('user', 'from_user', 'level', 'amount', 'created_at')
    list_filter = ('level', 'created_at')
    search_fields = ('user__email', 'from_user__email')
    readonly_fields = ('created_at',)