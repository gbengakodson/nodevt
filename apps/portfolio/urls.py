from django.urls import path
from .views import UserGoalView

urlpatterns = [
    path('goal/', UserGoalView.as_view(), name='user_goal'),
]