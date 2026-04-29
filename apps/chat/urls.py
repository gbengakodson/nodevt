from django.urls import path
from .views import ChatMessagesView, SendMessageView

urlpatterns = [
    path('messages/', ChatMessagesView.as_view(), name='chat_messages'),
    path('send/', SendMessageView.as_view(), name='send_message'),
    path('transparency/', TransparencyChatView.as_view(), name='transparency_chat'),
]