from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone


class Command(BaseCommand):
    help = 'Send all notifications (morning, afternoon, evening)'

    def handle(self, *args, **options):
        self.stdout.write('Sending all daily notifications...')

        # Send morning notifications (8 AM)
        self.stdout.write('Sending morning notifications...')
        call_command('send_daily_notifications', time_slot='morning')

        # Send afternoon notifications (1 PM)
        self.stdout.write('Sending afternoon notifications...')
        call_command('send_daily_notifications', time_slot='afternoon')

        # Send evening notifications (7 PM)
        self.stdout.write('Sending evening notifications...')
        call_command('send_daily_notifications', time_slot='evening')

        self.stdout.write(self.style.SUCCESS('All daily notifications sent!'))