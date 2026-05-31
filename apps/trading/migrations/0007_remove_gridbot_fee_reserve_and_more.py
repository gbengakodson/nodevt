
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0006_add_fee_reserves'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='gridbot',
            name='fee_reserve',
        ),
        migrations.RemoveField(
            model_name='gridbot',
            name='referrer_reserve',
        ),
    ]