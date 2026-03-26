from django.core.management.base import BaseCommand
from apps.yield_earnings.services.yield_service import YieldService


class Command(BaseCommand):
    help = 'Process yield distributions'

    def add_arguments(self, parser):
        parser.add_argument('--action', type=str, choices=['create', 'credit'], required=True)

    def handle(self, *args, **options):
        action = options['action']

        if action == 'create':
            from django.contrib.auth import get_user_model
            User = get_user_model()
            users = User.objects.filter(is_active=True)

            for user in users:
                distributions = YieldService.create_yield_distributions(user)
                self.stdout.write(
                    self.style.SUCCESS(f'Created distributions for {user.email}')
                )

        elif action == 'credit':
            credited = YieldService.credit_yield_distributions()
            self.stdout.write(
                self.style.SUCCESS(f'Credited {credited} distributions')
            )