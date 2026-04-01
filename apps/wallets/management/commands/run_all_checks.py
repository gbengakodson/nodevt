from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Run all automated tasks: check deposits and credit yield'

    def handle(self, *args, **options):
        self.stdout.write("=" * 50)
        self.stdout.write("Running all automated checks...")
        self.stdout.write("=" * 50)

        # Check deposits
        self.stdout.write("\n1. Checking deposits...")
        call_command('check_credits')

        # Credit yield
        self.stdout.write("\n2. Crediting yield...")
        call_command('credit_yield')

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("All checks completed!")
        self.stdout.write("=" * 50)