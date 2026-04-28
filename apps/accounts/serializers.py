from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    referral_code = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=5)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2', 'referral_code')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        referral_code = attrs.get('referral_code')
        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                attrs['referrer'] = referrer
            except User.DoesNotExist:
                raise serializers.ValidationError({"referral_code": "Invalid referral code."})
        # No validation error if referral_code is empty or not provided

        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        referral_code = validated_data.pop('referral_code', None)
        referrer = validated_data.pop('referrer', None)

        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            referrer=referrer
        )
        user.set_password(validated_data['password'])
        user.save()

        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

class UserSerializer(serializers.ModelSerializer):
    referral_code = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'referral_code', 'wallet_address', 'created_at')