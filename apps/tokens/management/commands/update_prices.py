from django.core.management.base import BaseCommand
from apps.tokens.services import PriceService

class Command(BaseCommand):
    help = 'Update token prices from CoinGecko'
    
    def handle(self, *args, **options):
        self.stdout.write('Fetching token prices from CoinGecko...')
        updated = PriceService.update_token_prices()
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated} tokens'))