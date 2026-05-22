def notify_user(user, title, message, notif_type='INFO'):
    """Send notification to user"""
    from apps.chatbot.models import UserNotification
    UserNotification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notif_type
    )