from django.core.management.base import BaseCommand
from apps.trading.models import GridBot
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from apps.core.notifications import notify_user







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

                # Notify if nearing 20%
                if 15 <= float(pnl_percent) < 20:
                    notify_user(
                        bot.user,
                        f'📈 {token.symbol} Nearing Auto-Close',
                        f'Your {token.symbol} tracker is at +{float(pnl_percent):.1f}% PNL. At 20% it will auto-close and return funds to your wallet.',
                        'INFO'
                    )

                # Auto-close at 20%+ PNL
                # Auto-close at 20%+ PNL and automatically reactivate
                if pnl_percent >= 20:
                    old_capital = bot.amount or Decimal('0')
                    pnl = bot.pnl or Decimal('0')
                    grid_profit = bot.grid_profit or Decimal('0')

                    # 10% management fee on the new capital (old capital + PNL)
                    new_capital_total = old_capital + pnl
                    fee = new_capital_total * Decimal('0.10')
                    new_invested = new_capital_total - fee

                    # Sweep only the grid profit to the user's wallet
                    from apps.wallets.services.web3_service import Web3Service
                    from apps.wallets.models import WalletKey, Transaction
                    from apps.trading.views import TradingViewSet

                    try:
                        wallet_key = WalletKey.objects.get(user=bot.user)
                        user_address = wallet_key.address

                        if grid_profit > 0:
                            profit_sweep = TradingViewSet._sweep_from_user_wallet(
                                settings.CENTRAL_WALLET_ADDRESS,
                                settings.CENTRAL_WALLET_PRIVATE_KEY,
                                user_address,
                                grid_profit
                            )
                        else:
                            profit_sweep = {'success': True, 'tx_hash': None}

                        if not profit_sweep['success']:
                            self.stdout.write(f'⚠️ Grid profit sweep failed: {profit_sweep.get("error")}')
                            continue

                        # Record grid profit withdrawal
                        if grid_profit > 0:
                            Transaction.objects.create(
                                user=bot.user,
                                transaction_type='GRID_CLOSE',
                                amount=grid_profit,
                                fee=0,
                                status='COMPLETED',
                                tx_hash=profit_sweep.get('tx_hash', ''),
                                metadata={
                                    'grid_bot_id': str(bot.id),
                                    'token': token.symbol,
                                    'reason': 'auto_reactivate_grid_profit',
                                    'to_address': user_address
                                },
                                completed_at=timezone.now()
                            )

                        # Create new GridBot with capital + PNL (after 10% fee)
                        upper_price = current_price * Decimal('1.15')
                        lower_price = current_price * Decimal('0.85')
                        new_bot = GridBot.objects.create(
                            user=bot.user,
                            token=token,
                            amount=new_invested,
                            lower_price=lower_price,
                            upper_price=upper_price,
                            grids=100,
                            status='ACTIVE',
                            grid_profit=Decimal('0'),
                            pnl=Decimal('0'),
                            pnl_percent=Decimal('0'),
                            price_at_creation=current_price,
                            created_at=timezone.now(),
                        )

                        # Record the 10% management fee
                        Transaction.objects.create(
                            user=bot.user,
                            transaction_type='PURCHASE',
                            amount=new_capital_total,
                            fee=fee,
                            status='COMPLETED',
                            metadata={
                                'token_id': str(token.id),
                                'token_symbol': token.symbol,
                                'reason': 'auto_reactivate_20_percent',
                                'new_bot_id': str(new_bot.id),
                                'old_bot_id': str(bot.id),
                            },
                            completed_at=timezone.now()
                        )

                        # Mark old bot as completed
                        bot.status = 'COMPLETED'
                        bot.save()
                        closed += 1

                        # Notify user
                        notify_user(
                            bot.user,
                            f'🔄 {token.symbol} Auto-Renewed at +{float(pnl_percent):.1f}%',
                            f'${float(grid_profit):.2f} profit was sent to your wallet. '
                            f'${float(new_invested):.2f} has been automatically reinvested in a new {token.symbol} tracker (after 10% fee).',
                            'PORTFOLIO'
                        )

                        self.stdout.write(
                            f'🔄 Auto-renewed {token.symbol} for {bot.user.email} with ${float(new_invested):.2f}')
                    except Exception as e:
                        self.stdout.write(f'⚠️ Auto-renew error: {e}')
                        continue

        self.stdout.write(self.style.SUCCESS(f'Updated PNL for {updated} bots | Auto-closed {closed} bots'))