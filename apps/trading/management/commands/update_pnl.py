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
                if pnl_percent >= 20:
                    total_return = bot.amount + bot.grid_profit + bot.pnl

                    # Check liquidity
                    from apps.wallets.services.web3_service import Web3Service
                    ws = Web3Service()
                    central_balance = ws.get_usdc_balance(settings.CENTRAL_WALLET_ADDRESS)

                    if central_balance < total_return:
                        self.stdout.write(f'⚠️ Liquidity gap for {token.symbol} bot ({bot.user.email})')
                        notify_user(
                            bot.user,
                            f'⏳ {token.symbol} Close Pending',
                            f'Your {token.symbol} tracker reached +{float(pnl_percent):.1f}% PNL but close is delayed due to platform liquidity. Processing within 24 hours.',
                            'ALERT'
                        )
                        continue

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

                            # Settle performance fees
                            fee_due = bot.fee_reserve or 0
                            referrer_due = bot.referrer_reserve or 0

                            if fee_due > 0:
                                Transaction.objects.create(
                                    user=bot.user, transaction_type='PERFORMANCE_FEE',
                                    amount=fee_due, fee=0, status='COMPLETED',
                                    metadata={'grid_bot_id': str(bot.id), 'token': token.symbol,
                                              'reason': 'auto_close'},
                                    completed_at=timezone.now()
                                )

                            if referrer_due > 0:
                                from apps.referrals.models import ReferralRelationship
                                ref_rel = ReferralRelationship.objects.filter(referred=bot.user).first()
                                if ref_rel:
                                    try:
                                        ref_wallet = WalletKey.objects.get(user=ref_rel.referrer)
                                        TradingViewSet._sweep_from_user_wallet(
                                            settings.CENTRAL_WALLET_ADDRESS,
                                            settings.CENTRAL_WALLET_PRIVATE_KEY,
                                            ref_wallet.address,
                                            referrer_due
                                        )
                                        Transaction.objects.create(
                                            user=ref_rel.referrer, transaction_type='REFERRAL',
                                            amount=referrer_due, fee=0, status='COMPLETED',
                                            metadata={'from_user': bot.user.email, 'grid_bot_id': str(bot.id),
                                                      'reason': 'auto_close'},
                                            completed_at=timezone.now()
                                        )
                                    except WalletKey.DoesNotExist:
                                        pass


                            bot.status = 'COMPLETED'
                            bot.save()
                            closed += 1

                            notify_user(
                                bot.user,
                                f'🎉 {token.symbol} Auto-Closed at +{float(pnl_percent):.1f}%',
                                f'${float(total_return):.2f} returned to your wallet. Reactivate anytime to keep earning.',
                                'PORTFOLIO'
                            )

                            self.stdout.write(f'🔒 Auto-closed {token.symbol} for {bot.user.email} at +{float(pnl_percent):.1f}%')
                        else:
                            self.stdout.write(f'⚠️ Sweep failed: {sweep_result.get("error")}')
                    except Exception as e:
                        self.stdout.write(f'⚠️ Auto-close error: {e}')

        self.stdout.write(self.style.SUCCESS(f'Updated PNL for {updated} bots | Auto-closed {closed} bots'))