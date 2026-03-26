from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import ChatMessage


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