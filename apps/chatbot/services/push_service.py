import json
import requests
from django.conf import settings
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from base64 import urlsafe_b64decode, urlsafe_b64encode
import vapid


class PushNotificationService:

    @classmethod
    def send_push_notification(cls, subscription, title, body, url='/'):
        """Send push notification to a single user"""
        try:
            # VAPID keys (generate these once)
            vapid_private_key = settings.VAPID_PRIVATE_KEY
            vapid_public_key = settings.VAPID_PUBLIC_KEY
            vapid_claims = {
                'sub': 'mailto:admin@nodevt.com'
            }

            # Prepare notification data
            notification_data = {
                'title': title,
                'body': body,
                'url': url,
                'icon': '/static/favicon.svg',
                'badge': '/static/favicon.svg'
            }

            # Send to browser push service
            response = requests.post(
                subscription['endpoint'],
                headers={
                    'Content-Type': 'application/json',
                    'TTL': '86400',
                    'Urgency': 'high'
                },
                data=json.dumps(notification_data)
            )

            return response.status_code == 201

        except Exception as e:
            print(f"Push notification error: {e}")
            return False

    @classmethod
    def send_to_all_users(cls, title, body, url='/'):
        """Send push notification to all subscribed users"""
        from apps.chatbot.models import PushSubscription

        subscriptions = PushSubscription.objects.filter(is_active=True)
        sent_count = 0

        for sub in subscriptions:
            subscription_data = {
                'endpoint': sub.endpoint,
                'keys': {
                    'p256dh': sub.p256dh,
                    'auth': sub.auth
                }
            }

            if cls.send_push_notification(subscription_data, title, body, url):
                sent_count += 1

        return sent_count