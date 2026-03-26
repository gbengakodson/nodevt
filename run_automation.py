import os
import sys
import time
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command
from apps.tokens.services import PriceService
from apps.yield_earnings.services import YieldService

print("Starting automation runner...")
print("Press Ctrl+C to stop")

try:
    while True:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        
        # Update prices every 2 minutes
        print("Updating token prices...")
        call_command('update_prices')
        
        # Check and execute take profit at 20% gain
        print("Checking take profit (20% gain)...")
        call_command('check_take_profit')
        
        # Credit yield (hourly)
        print("Crediting yield...")
        call_command('credit_yield')
        
        print(f"Waiting 2 minutes...")
        time.sleep(120)
        
except KeyboardInterrupt:
    print("\nStopped by user")