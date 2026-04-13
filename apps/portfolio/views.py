from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserGoal
from decimal import Decimal


class UserGoalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        goal, created = UserGoal.objects.get_or_create(user=request.user)
        return Response({
            'target_amount': float(goal.target_amount),
            'target_years': goal.target_years,
            'monthly_addition': float(goal.monthly_addition)
        })

    def post(self, request):
        goal, created = UserGoal.objects.get_or_create(user=request.user)
        goal.target_amount = Decimal(str(request.data.get('target_amount', 10000)))
        goal.target_years = int(request.data.get('target_years', 2))
        goal.monthly_addition = Decimal(str(request.data.get('monthly_addition', 0)))
        goal.save()

        return Response({
            'success': True,
            'target_amount': float(goal.target_amount),
            'target_years': goal.target_years,
            'monthly_addition': float(goal.monthly_addition)
        })