from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from .models import UserForexProfile

class EAApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise exceptions.AuthenticationFailed('Invalid authorization header')
        api_key = parts[1]
        for profile in UserForexProfile.objects.select_related('user').all():
            if profile.check_api_key(api_key):
                return (profile.user, api_key)
        raise exceptions.AuthenticationFailed('Invalid API key')
