from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('wallets', '0002_walletkey'),
    ]

    operations = [
        migrations.AddField(
            model_name='walletkey',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]