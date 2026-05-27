import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            self.room_group_name = f"chat_{self.user.id}"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message', '').strip()
        if not message:
            return

        # Save to database
        msg = await self.save_message(message)

        # Send to user
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'is_admin': False,
                'time': msg.created_at.strftime('%H:%M'),
            }
        )

        # Notify admins
        if not self.user.is_staff:
            await self.notify_admins(message)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'is_admin': event['is_admin'],
            'time': event['time'],
        }))

    @database_sync_to_async
    def save_message(self, message):
        from .models import ChatMessage
        return ChatMessage.objects.create(
            user=self.user,
            message=message,
            is_admin_reply=self.user.is_staff
        )

    @database_sync_to_async
    def notify_admins(self, message):
        from apps.chatbot.models import UserNotification
        admins = User.objects.filter(is_staff=True)
        for admin in admins:
            UserNotification.objects.create(
                user=admin,
                title='💬 New Support Message',
                message=f'{self.user.email}: {message[:100]}',
                notification_type='ALERT'
            )



class AdminChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_authenticated and self.user.is_staff:
            self.room_group_name = "admin_chat"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message', '')
        target_user_id = data.get('user_id', '')
        if not message or not target_user_id:
            return

        # Save as admin reply
        msg = await self.save_admin_reply(target_user_id, message)

        # Send to admin group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'admin_message',
                'message': message,
                'user_id': target_user_id,
                'time': msg.created_at.strftime('%H:%M'),
            }
        )

        # Send to user
        await self.channel_layer.group_send(
            f"chat_{target_user_id}",
            {
                'type': 'chat_message',
                'message': message,
                'is_admin': True,
                'time': msg.created_at.strftime('%H:%M'),
            }
        )

    async def admin_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'user_id': event['user_id'],
            'time': event['time'],
        }))

    @database_sync_to_async
    def save_admin_reply(self, user_id, message):
        from .models import ChatMessage
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(id=user_id)
        return ChatMessage.objects.create(
            user=user,
            message=message,
            is_admin_reply=True,
            is_read=True
        )