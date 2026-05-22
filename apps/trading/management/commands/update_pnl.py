from django.core.management.base import BaseCommand
from apps.trading.models import GridBot
from decimal import Decimal
from django.utils import timezone
from django.conf import settings


class Command(BaseCommand):
    help = 'Update PNL for all active grid bots and auto-close at 20%+'

    def handle(self, *args, **options):
        bots = GridBot.objects.filter(status='ACTIVE').select_related('token')
        updated = 0
        closed = 0

        for bot in bots:
            token = bot.token
            if not token or token.current_price <= 0:
                continue

            current_price = token.current_price
            entry_price = bot.price_at_creation

            if entry_price > 0:
                quantity = bot.amount / entry_price
                current_value = quantity * current_price
                pnl = current_value - bot.amount
                pnl_percent = (pnl / bot.amount * 100) if bot.amount > 0 else Decimal('0')

                bot.pnl = pnl
                bot.pnl_percent = pnl_percent
                bot.save()
                updated += 1

                # Auto-close at 20%+ PNL
                if pnl_percent >= 20:
                    total_return = bot.amount + bot.grid_profit + bot.pnl

                    # Sweep to user's wallet
                    from apps.wallets.models import WalletKey, Transaction
                    from apps.trading.views import TradingViewSet

                    try:
                        wallet_key = WalletKey.objects.get(user=bot.user)
                        user_address = wallet_key.address

                        sweep_result = TradingViewSet._sweep_from_user_wallet(
                            settings.CENTRAL_WALLET_ADDRESS,
                            settings.CENTRAL_WALLET_PRIVATE_KEY,
                            user_address,
                            total_return
                        )

                        if sweep_result['success']:
                            Transaction.objects.create(
                                user=bot.user,
                                transaction_type='GRID_CLOSE',
                                amount=total_return,
                                fee=0,
                                status='COMPLETED',
                                tx_hash=sweep_result.get('tx_hash', ''),
                                metadata={
                                    'grid_bot_id': str(bot.id),
                                    'token': token.symbol,
                                    'reason': 'auto_close_20_percent',
                                    'pnl_percent': float(pnl_percent),
                                    'to_address': user_address
                                },
                                completed_at=timezone.now()
                            )

                            bot.status = 'COMPLETED'
                            bot.save()
                            closed += 1
                            self.stdout.write(
                                f'🔒 Auto-closed {token.symbol} bot for {bot.user.email} at +{float(pnl_percent):.1f}% PNL')
                        else:
                            self.stdout.write(f'⚠️ Sweep failed for auto-close: {sweep_result.get("error")}')
                    except Exception as e:
                        self.stdout.write(f'⚠️ Auto-close error: {e}')

        self.stdout.write(self.style.SUCCESS(f'Updated PNL for {updated} bots | Auto-closed {closed} bots'))