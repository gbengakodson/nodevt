import requests
from decimal import Decimal
from django.utils import timezone
from apps.tokens.models import CryptoToken
from apps.trading.models import MasterGridBot


class FadakkaService:
    """Fadakka Index (99-week EMA) grid activation system"""

    # Manual Fadakka Index values (99-week EMA) - Updated weekly
    FADAKKA_VALUES = {
        'BTC': Decimal('82035'), 'ETH': Decimal('2762'), 'SOL': Decimal('132.02'),
        'BNB': Decimal('680.22'), 'XRP': Decimal('1.7635'), 'DOGE': Decimal('0.15536'),
        'NEAR': Decimal('2.667'), 'TRX': Decimal('0.2622'), 'LINK': Decimal('13.659'),
        'AVAX': Decimal('19.238'), 'ADA': Decimal('0.5057'), 'PEPE': Decimal('0.00000675'),
        'DOT': Decimal('3.893'), 'ALGO': Decimal('0.1861'), 'UNI': Decimal('6.819'),
        'THETA': Decimal('0.826'), 'VET': Decimal('0.01995'), 'ATOM': Decimal('4.474'),
        'LTC': Decimal('80.73'), 'EGLD': Decimal('17.81'),
    }

    # Minimum investment per coin (USDC)
    MIN_INVESTMENT = {
        'BTC': Decimal('1000'), 'ETH': Decimal('500'), 'SOL': Decimal('200'),
        'BNB': Decimal('300'), 'DOT': Decimal('200'), 'AVAX': Decimal('300'),
        'ADA': Decimal('200'), 'ATOM': Decimal('200'), 'EGLD': Decimal('200'),
        'THETA': Decimal('100'), 'VET': Decimal('100'),
    }

    @classmethod
    def get_fadakka(cls, symbol):
        """Get Fadakka Index for a coin"""
        return cls.FADAKKA_VALUES.get(symbol)

    @classmethod
    def get_alpha_levels(cls, symbol):
        """Calculate alpha levels from Fadakka Index"""
        k = cls.get_fadakka(symbol)
        if not k:
            return None

        return {
            'k': float(k),
            'a1': float(k * Decimal('0.5')),
            'a2': float(k * Decimal('0.33')),
            'a3': float(k * Decimal('0.7')),
            'exit_price': float(k * Decimal('2.0')),
        }

    @classmethod
    def check_trigger(cls, symbol, current_price):
        """Check which alpha level is triggered"""
        k = cls.get_fadakka(symbol)
        if not k or current_price <= 0:
            return None

        price = Decimal(str(current_price))

        if price <= k * Decimal('0.33'):
            return {'tier': 1, 'level': 'a2', 'discount': float((1 - price / k) * 100)}
        elif price <= k * Decimal('0.5'):
            return {'tier': 2, 'level': 'a1', 'discount': float((1 - price / k) * 100)}
        elif price <= k * Decimal('0.7'):
            return {'tier': 3, 'level': 'a3', 'discount': float((1 - price / k) * 100)}

        return None

    @classmethod
    def should_exit(cls, symbol, current_price):
        """Check if price has reached 2k (exit)"""
        k = cls.get_fadakka(symbol)
        if not k:
            return False
        return Decimal(str(current_price)) >= k * Decimal('2.0')

    @classmethod
    def has_active_grid(cls, symbol):
        """Check if master grid exists for this coin"""
        return MasterGridBot.objects.filter(
            token__symbol=symbol,
            status='ACTIVE'
        ).exists()

    @classmethod
    def get_min_investment(cls, symbol):
        """Get minimum investment for a coin"""
        return cls.MIN_INVESTMENT.get(symbol, Decimal('200'))

    @classmethod
    def scan_and_activate(cls, available_capital):
        """
        Scan all coins in priority order and activate grids if conditions met.
        Returns list of actions taken.
        """
        from apps.tokens.models import CryptoToken

        actions = []
        remaining_capital = Decimal(str(available_capital))

        # Get all active tokens with current prices
        tokens = CryptoToken.objects.filter(is_active=True)

        # Build scan list with trigger info
        scan_list = []
        for token in tokens:
            trigger = cls.check_trigger(token.symbol, token.current_price)
            should_exit = cls.should_exit(token.symbol, token.current_price)
            has_grid = cls.has_active_grid(token.symbol)

            scan_list.append({
                'symbol': token.symbol,
                'current_price': float(token.current_price),
                'trigger': trigger,
                'should_exit': should_exit,
                'has_grid': has_grid,
                'min_investment': float(cls.get_min_investment(token.symbol)),
            })

        # Step 1: Close grids that hit exit (2k)
        for item in scan_list:
            if item['has_grid'] and item['should_exit']:
                cls._close_grid(item['symbol'])
                actions.append({
                    'action': 'CLOSED',
                    'symbol': item['symbol'],
                    'reason': f'Price reached 2k exit level'
                })

        # Step 2: Activate new grids in priority order
        # Sort by tier (1 first, then 2, then 3), then by discount (highest first)
        candidates = [s for s in scan_list if s['trigger'] and not s['has_grid']]
        candidates.sort(key=lambda x: (x['trigger']['tier'], -x['trigger']['discount']))

        for item in candidates:
            min_invest = Decimal(str(item['min_investment']))

            if remaining_capital >= min_invest:
                success = cls._activate_grid(item['symbol'], item['trigger']['level'])
                if success:
                    remaining_capital -= min_invest
                    actions.append({
                        'action': 'ACTIVATED',
                        'symbol': item['symbol'],
                        'level': item['trigger']['level'],
                        'tier': item['trigger']['tier'],
                        'discount': item['trigger']['discount'],
                        'remaining_capital': float(remaining_capital)
                    })

        return actions

    @classmethod
    def _activate_grid(cls, symbol, level):
        """Activate a master grid for a coin"""
        try:
            token = CryptoToken.objects.get(symbol=symbol)

            # Calculate grid range based on current price
            current_price = token.current_price
            upper = current_price * Decimal('1.8')
            lower = current_price * Decimal('0.2')
            min_invest = cls.get_min_investment(symbol)

            # Create master grid record
            MasterGridBot.objects.create(
                token=token,
                total_amount=min_invest,
                lower_price=lower,
                upper_price=upper,
                grids=100,
                status='ACTIVE',
                price_at_creation=current_price,
                metadata={
                    'fadakka_level': level,
                    'fadakka_k': float(cls.get_fadakka(symbol)),
                    'activation_price': float(current_price),
                }
            )

            print(f"✅ Grid activated: {symbol} at {level} (Price: ${float(current_price):.4f})")
            return True

        except Exception as e:
            print(f"Error activating grid for {symbol}: {e}")
            return False

    @classmethod
    def _close_grid(cls, symbol):
        """Close all active grids for a coin"""
        try:
            count = MasterGridBot.objects.filter(
                token__symbol=symbol,
                status='ACTIVE'
            ).update(status='COMPLETED')
            print(f"🔒 Closed {count} grid(s) for {symbol} (hit 2k exit)")
        except Exception as e:
            print(f"Error closing grid for {symbol}: {e}")