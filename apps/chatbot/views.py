from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .services.chatbot_service import ChatbotService, NotificationService
from .models import ChatbotConversation
from .models import PushSubscription
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json


class ChatbotAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_message = request.data.get('message', '')

        if not user_message:
            return Response({'error': 'Message is required'}, status=400)

        # Get chatbot response
        response, intent = ChatbotService.get_response(user_message, request.user)

        # Save conversation
        ChatbotConversation.objects.create(
            user=request.user,
            message=user_message,
            response=response,
            intent=intent
        )

        return Response({
            'response': response,
            'intent': intent
        })

    def get(self, request):
        """Get conversation history"""
        conversations = ChatbotConversation.objects.filter(user=request.user)[:20]

        data = [{
            'message': c.message,
            'response': c.response,
            'created_at': c.created_at.strftime('%Y-%m-%d %H:%M')
        } for c in conversations]

        return Response(data)


class NotificationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user notifications"""
        unread_only = request.query_params.get('unread_only', 'false').lower() == 'true'
        notifications = NotificationService.get_user_notifications(
            request.user,
            unread_only=unread_only
        )

        data = [{
            'id': str(n.id),
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
        } for n in notifications]

        return Response(data)

    def post(self, request):
        """Mark notification as read"""
        notification_id = request.data.get('notification_id')
        if notification_id:
            NotificationService.mark_as_read(notification_id)
        return Response({'success': True})


class MarkAllNotificationsReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import UserNotification
        UserNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'success': True})


class MarkAllNotificationsReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import UserNotification
        UserNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'success': True})





class SubscribePushAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription_data = request.data

        PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=subscription_data.get('endpoint'),
            defaults={
                'p256dh': subscription_data.get('keys', {}).get('p256dh'),
                'auth': subscription_data.get('keys', {}).get('auth'),
                'is_active': True
            }
        )

        return Response({'success': True})


class UnsubscribePushAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        endpoint = request.data.get('endpoint')
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response({'success': True})