import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get('user')

        if self.user and self.user.is_authenticated:
            if self.user.is_staff:
                self.room_group_name = 'admin_chat'
            else:
                self.room_group_name = f'user_chat_{self.user.id}'

            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()

            # Send unread messages count to user
            if not self.user.is_staff:
                unread_count = await self.get_unread_count()
                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': unread_count
                }))
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'message')

        if message_type == 'message':
            message = data.get('message', '')

            if message.strip():
                # Save message to database
                chat_message = await self.save_message(message)

                # Send to admin group if user message
                if not self.user.is_staff:
                    await self.channel_layer.group_send(
                        'admin_chat',
                        {
                            'type': 'chat_message',
                            'message': message,
                            'user_id': str(self.user.id),
                            'username': self.user.username,
                            'timestamp': chat_message['timestamp'],
                            'message_id': chat_message['id']
                        }
                    )
                    # Confirm to user
                    await self.send(text_data=json.dumps({
                        'type': 'message_sent',
                        'message': message,
                        'timestamp': chat_message['timestamp']
                    }))

                # Send to user group if admin reply
                else:
                    user_id = data.get('user_id')
                    if user_id:
                        await self.channel_layer.group_send(
                            f'user_chat_{user_id}',
                            {
                                'type': 'chat_message',
                                'message': message,
                                'is_admin': True,
                                'username': 'Support',
                                'timestamp': chat_message['timestamp'],
                                'message_id': chat_message['id']
                            }
                        )

        elif message_type == 'mark_read':
            await self.mark_messages_read()

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'username': event.get('username', 'User'),
            'is_admin': event.get('is_admin', False),
            'timestamp': event.get('timestamp'),
            'user_id': event.get('user_id'),
            'message_id': event.get('message_id')
        }))

    @database_sync_to_async
    def save_message(self, message):
        from .models import ChatMessage
        msg = ChatMessage.objects.create(
            user=self.user,
            message=message,
            is_admin_reply=self.user.is_staff
        )
        return {
            'id': str(msg.id),
            'timestamp': msg.created_at.strftime('%H:%M')
        }

    @database_sync_to_async
    def get_unread_count(self):
        from .models import ChatMessage
        return ChatMessage.objects.filter(
            user=self.user,
            is_read=False,
            is_admin_reply=True
        ).count()

    @database_sync_to_async
    def mark_messages_read(self):
        from .models import ChatMessage
        ChatMessage.objects.filter(
            user=self.user,
            is_read=False,
            is_admin_reply=True
        ).update(is_read=True)