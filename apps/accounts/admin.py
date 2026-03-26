from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'wallet_address', 'is_active', 'created_at')
    search_fields = ('email', 'username')
    ordering = ('-created_at',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Crypto Info', {'fields': ('wallet_address',)}),
    )

admin.site.register(User, CustomUserAdmin)