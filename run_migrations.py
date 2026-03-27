import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command

print("Running migrations...")
call_command('migrate', verbosity=3)
print("Migrations complete!")