import random
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from .models import OTPCode


class OTPService:

    @classmethod
    def generate_otp(cls, user, purpose='LOGIN'):
        """Generate 6-digit OTP and send via email"""
        # Expire old codes
        OTPCode.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)

        code = str(random.randint(100000, 999999))
        expires_at = timezone.now() + timedelta(minutes=10)

        OTPCode.objects.create(
            user=user,
            code=code,
            purpose=purpose,
            expires_at=expires_at
        )

        # Send email
        subject = f'NODE - Your OTP Code ({purpose})'
        message = f'''Hello {user.username or user.email},

Your OTP code is: {code}

Purpose: {purpose}
Expires in: 10 minutes

If you didn't request this, ignore this email.

NODE AI Autotrader
'''
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )

        return {'success': True, 'message': 'OTP sent to your email'}

    @classmethod
    def verify_otp(cls, user, code, purpose='LOGIN'):
        """Verify OTP code"""
        otp = OTPCode.objects.filter(
            user=user,
            code=code,
            purpose=purpose,
            is_used=False,
            expires_at__gte=timezone.now()
        ).first()

        if not otp:
            return {'success': False, 'error': 'Invalid or expired OTP'}

        otp.is_used = True
        otp.save()

        return {'success': True}