from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import ChatMessage
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action


class ChatMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            messages = ChatMessage.objects.all().order_by('-created_at')[:100]
        else:
            messages = ChatMessage.objects.filter(user=request.user).order_by('-created_at')[:50]

        data = []
        for msg in reversed(messages):
            data.append({
                'id': str(msg.id),
                'message': msg.message,
                'is_admin': msg.is_admin_reply,
                'time': msg.created_at.strftime('%H:%M'),
                'date': msg.created_at.strftime('%Y-%m-%d %H:%M'),
                'user_email': msg.user.email,
                'user_id': str(msg.user.id)
            })

        return Response(data)


class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get('message', '').strip()
        target_user_id = request.data.get('target_user_id', None)

        if not message:
            return Response({'error': 'Message cannot be empty'}, status=status.HTTP_400_BAD_REQUEST)

        if request.user.is_staff and target_user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            target_user = User.objects.get(id=target_user_id)
            chat_message = ChatMessage.objects.create(
                user=target_user,
                message=message,
                is_admin_reply=True
            )
        else:
            chat_message = ChatMessage.objects.create(
                user=request.user,
                message=message,
                is_admin_reply=request.user.is_staff
            )

        if not request.user.is_staff:
            from apps.chatbot.models import UserNotification
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admins = User.objects.filter(is_staff=True)
            for admin in admins:
                UserNotification.objects.create(
                    user=admin,
                    title='💬 New Support Message',
                    message=f'{request.user.email}: {message[:100]}',
                    notification_type='ALERT'
                )

        return Response({
            'success': True,
            'message_id': str(chat_message.id),
            'time': chat_message.created_at.strftime('%H:%M')
        })


class ReviewView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from .models import Review
        reviews = Review.objects.filter(is_approved=True).order_by('-created_at')[:20]
        data = [{
            'id': str(r.id),
            'username': r.user.username or r.user.email.split('@')[0],
            'rating': r.rating,
            'message': r.message,
            'time': r.created_at.strftime('%b %d')
        } for r in reviews]
        return Response(data)

    def post(self, request):
        from .models import Review
        if not request.user.is_authenticated:
            return Response({'error': 'Login required'}, status=401)
        rating = int(request.data.get('rating', 5))
        message = request.data.get('message', '').strip()
        if not message:
            return Response({'error': 'Message required'}, status=400)
        Review.objects.create(user=request.user, rating=rating, message=message)
        return Response({'success': True})



class TransparencyChatView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        messages = TransparencyChatMessage.objects.all().order_by('created_at')
        data = [{
            'id': str(msg.id),
            'username': msg.user.username or msg.user.email.split('@')[0],
            'message': msg.message,
            'created_at': msg.created_at.isoformat(),
            'is_admin': msg.user.is_staff,
            'parent_id': str(msg.parent_id) if msg.parent_id else None,
            'likes': msg.likes.count()
        } for msg in messages]
        return Response(data)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Please login to comment'}, status=401)

        message = request.data.get('message', '').strip()
        parent_id = request.data.get('parent_id')

        if not message:
            return Response({'error': 'Message cannot be empty'}, status=400)

        if len(message) > 500:
            return Response({'error': 'Message too long'}, status=400)

        parent = None
        if parent_id:
            try:
                parent = TransparencyChatMessage.objects.get(id=parent_id)
            except TransparencyChatMessage.DoesNotExist:
                return Response({'error': 'Parent message not found'}, status=400)

        chat_msg = TransparencyChatMessage.objects.create(
            user=request.user,
            message=message,
            parent=parent
        )

        return Response({'success': True, 'id': str(chat_msg.id)})

    @action(detail=False, methods=['post'])
    def like(self, request):
        post_id = request.data.get('post_id')
        if not request.user.is_authenticated:
            return Response({'error': 'Login required'}, status=401)
        try:
            post = TransparencyChatMessage.objects.get(id=post_id)
            if request.user in post.likes.all():
                post.likes.remove(request.user)
            else:
                post.likes.add(request.user)
            return Response({'likes': post.likes.count()})
        except TransparencyChatMessage.DoesNotExist:
            return Response({'error': 'Post not found'}, status=404)
