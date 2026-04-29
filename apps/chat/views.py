from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import ChatMessage
from rest_framework.permissions import AllowAny, IsAuthenticated


class ChatMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            messages = ChatMessage.objects.all().order_by('-created_at')[:50]
        else:
            messages = ChatMessage.objects.filter(user=request.user).order_by('-created_at')[:50]

        data = []
        for msg in reversed(messages):  # Show oldest first
            data.append({
                'id': str(msg.id),
                'message': msg.message,
                'is_admin': msg.is_admin_reply,
                'time': msg.created_at.strftime('%H:%M'),
                'date': msg.created_at.strftime('%Y-%m-%d %H:%M')
            })

        return Response(data)


class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get('message', '').strip()

        if not message:
            return Response({'error': 'Message cannot be empty'}, status=status.HTTP_400_BAD_REQUEST)

        chat_message = ChatMessage.objects.create(
            user=request.user,
            message=message,
            is_admin_reply=request.user.is_staff
        )

        return Response({
            'success': True,
            'message_id': str(chat_message.id),
            'time': chat_message.created_at.strftime('%H:%M')
        })


from .models import TransparencyChatMessage


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
            'parent_id': str(msg.parent_id) if msg.parent_id else None
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