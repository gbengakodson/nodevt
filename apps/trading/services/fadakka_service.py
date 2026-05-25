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

    # 20 Trigger Levels with deviation from K
    TRIGGER_LEVELS = [
        {'level': 'L1', 'deviation': -0.20, 'exit_multiplier': 2.0},
        {'level': 'L2', 'deviation': -0.25, 'exit_multiplier': 2.0},
        {'level': 'L3', 'deviation': -0.30, 'exit_multiplier': 2.0},
        {'level': 'L4', 'deviation': -0.35, 'exit_multiplier': 2.0},
        {'level': 'L5', 'deviation': -0.40, 'exit_multiplier': 2.0},
        {'level': 'L6', 'deviation': -0.45, 'exit_multiplier': 1.5},
        {'level': 'L7', 'deviation': -0.50, 'exit_multiplier': 1.5},
        {'level': 'L8', 'deviation': -0.55, 'exit_multiplier': 1.5},
        {'level': 'L9', 'deviation': -0.60, 'exit_multiplier': 1.5},
        {'level': 'L10', 'deviation': -0.65, 'exit_multiplier': 1.5},
        {'level': 'L11', 'deviation': -0.70, 'exit_multiplier': 1.0},
        {'level': 'L12', 'deviation': -0.75, 'exit_multiplier': 1.0},
        {'level': 'L13', 'deviation': -0.80, 'exit_multiplier': 1.0},
        {'level': 'L14', 'deviation': -0.90, 'exit_multiplier': 1.0},
        {'level': 'L15', 'deviation': -1.00, 'exit_multiplier': 1.0},
        {'level': 'L16', 'deviation': -1.20, 'exit_multiplier': 0.5},
        {'level': 'L17', 'deviation': -1.40, 'exit_multiplier': 0.5},
        {'level': 'L18', 'deviation': -1.60, 'exit_multiplier': 0.5},
        {'level': 'L19', 'deviation': -1.80, 'exit_multiplier': 0.5},
        {'level': 'L20', 'deviation': -2.00, 'exit_multiplier': 0.5},
    ]

    @classmethod
    def check_trigger(cls, symbol, current_price):
        """Check which level is triggered based on deviation from K"""
        k = cls.get_fadakka(symbol)
        if not k or current_price <= 0:
            return None

        price = Decimal(str(current_price))
        deviation = float((price - k) / k)  # e.g., -0.35 means 35% below K

        # Find the deepest level triggered
        triggered_level = None
        for level in cls.TRIGGER_LEVELS:
            if deviation <= level['deviation']:
                triggered_level = level

        if triggered_level:
            return {
                'level': triggered_level['level'],
                'deviation': triggered_level['deviation'],
                'exit_multiplier': triggered_level['exit_multiplier'],
                'discount': abs(float(deviation) * 100),
                'exit_price': float(k * Decimal(str(triggered_level['exit_multiplier'])))
            }
        return None

    @classmethod
    def should_exit(cls, symbol, current_price):
        """Check if price has reached the exit target for this coin's level"""
        k = cls.get_fadakka(symbol)
        if not k:
            return False

        # Find active grid for this coin to get its activation level
        active_grid = MasterGridBot.objects.filter(
            token__symbol=symbol,
            status='ACTIVE'
        ).first()

        if not active_grid:
            return False

        activation_level = active_grid.metadata.get('fadakka_level', 'L1')

        # Find the exit multiplier for this level
        exit_multiplier = 2.0  # Default
        for level in cls.TRIGGER_LEVELS:
            if level['level'] == activation_level:
                exit_multiplier = level['exit_multiplier']
                break

        exit_price = k * Decimal(str(exit_multiplier))
        return Decimal(str(current_price)) >= exit_price



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
        Scan all coins with expanded rules.
        Rules:
        1. Must be at a trigger level (L1-L20)
        2. Volume > $1M
        3. Not crashing (-30% in 24h)
        4. Market cap > $10M
        5. One coin per level
        6. Deepest discounts first
        7. Tiered exits based on level
        """
        from apps.tokens.models import CryptoToken
        import requests

        actions = []
        remaining_capital = Decimal(str(available_capital))

        tokens = CryptoToken.objects.filter(is_active=True)

        # Fetch market data for expanded rules
        cg_ids_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin', 'SOL': 'solana',
            'XRP': 'ripple', 'ADA': 'cardano', 'DOGE': 'dogecoin', 'AVAX': 'avalanche-2',
            'DOT': 'polkadot', 'LINK': 'chainlink', 'UNI': 'uniswap', 'LTC': 'litecoin',
            'NEAR': 'near', 'ATOM': 'cosmos', 'ALGO': 'algorand', 'VET': 'vechain',
            'FTM': 'fantom', 'EGLD': 'elrond-erd-2', 'THETA': 'theta-token', 'PEPE': 'pepe'
        }

        market_data = {}
        try:
            ids = ','.join(set(cg_ids_map.values()))
            url = f'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids}&order=market_cap_desc&sparkline=false&price_change_percentage=24h'
            resp = requests.get(url, timeout=10)
            for coin in resp.json():
                symbol = coin['symbol'].upper()
                for s, cg in cg_ids_map.items():
                    if cg == coin['id']:
                        market_data[s] = {
                            'volume': coin.get('total_volume', 0),
                            'change_24h': coin.get('price_change_percentage_24h', 0),
                            'market_cap': coin.get('market_cap', 0)
                        }
                        break
        except Exception as e:
            print(f"Market data fetch error: {e}")

        # Build scan list
        scan_list = []
        for token in tokens:
            trigger = cls.check_trigger(token.symbol, token.current_price)
            should_exit = cls.should_exit(token.symbol, token.current_price)
            has_grid = cls.has_active_grid(token.symbol)

            level_num = int(trigger['level'].replace('L', '')) if trigger else 99

            mdata = market_data.get(token.symbol, {})
            volume = mdata.get('volume', 0)
            change_24h = mdata.get('change_24h', 0)
            market_cap = mdata.get('market_cap', 0)

            scan_list.append({
                'symbol': token.symbol,
                'current_price': float(token.current_price),
                'trigger': trigger,
                'should_exit': should_exit,
                'has_grid': has_grid,
                'level_num': level_num,
                'min_investment': float(cls.get_min_investment(token.symbol)),
                'volume': volume,
                'change_24h': change_24h,
                'market_cap': market_cap,
            })

        # Step 1: Close grids that hit exit
        for item in scan_list:
            if item['has_grid'] and item['should_exit']:
                cls._close_grid(item['symbol'])
                actions.append({
                    'action': 'CLOSED',
                    'symbol': item['symbol'],
                    'reason': f"Price reached exit target"
                })

        # Step 2: Filter candidates by expanded rules
        candidates = []
        for s in scan_list:
            if not s['trigger'] or s['has_grid']:
                continue

            volume_ok = s['volume'] > 1_000_000
            not_crashing = s['change_24h'] > -30
            mcap_ok = s['market_cap'] > 10_000_000

            if volume_ok and not_crashing and mcap_ok:
                candidates.append(s)

        # Sort by level number (L20 first = deepest discount)
        candidates.sort(key=lambda x: -x['level_num'])

        # Track which levels are already taken
        taken_levels = set()
        for item in scan_list:
            if item['has_grid'] and item['trigger']:
                taken_levels.add(item['level_num'])

        # Step 3: Allocate capital using tiered half-of-remaining rule
        allocation_actions = cls._allocate_capital(
            remaining_capital, candidates, taken_levels
        )

        for item in allocation_actions:
            success = cls._activate_grid(
                item['symbol'],
                item['level'],
                exit_multiplier=item.get('exit_multiplier', 2.0),
                amount=item['amount']
            )
            if success:
                actions.append({
                    'action': 'ACTIVATED',
                    'symbol': item['symbol'],
                    'level': item['level'],
                    'amount': item['amount'],
                    'tier': item['tier']
                })

        return actions

    @classmethod
    def _allocate_capital(cls, available_capital, candidates, taken_levels):
        """
        Allocate capital using half-of-remaining rule.
        Tier 1: BTC, ETH, BNB, TRX, SOL
        Tier 2: XRP, ADA, UNI, ALGO, LINK
        Tier 3: All others

        For each coin in tier:
        - Check 1: 50% of pool >= minimum? Activate with 50%, continue.
        - Check 2: Entire pool >= minimum? Activate with entire pool, STOP tier.
        - Neither: Skip coin, pool unchanged.
        """
        TIER1_COINS = {'BTC', 'ETH', 'BNB', 'TRX', 'SOL'}
        TIER2_COINS = {'XRP', 'ADA', 'UNI', 'ALGO', 'LINK'}

        pool = available_capital
        actions = []
        taken_levels = set(taken_levels)  # Don't mutate original

        tiers = [
            ('Tier 1', [c for c in candidates if c['symbol'] in TIER1_COINS]),
            ('Tier 2', [c for c in candidates if c['symbol'] in TIER2_COINS]),
            ('Tier 3', [c for c in candidates if c['symbol'] not in TIER1_COINS and c['symbol'] not in TIER2_COINS]),
        ]

        for tier_name, tier_candidates in tiers:
            if pool <= 0:
                break

            for item in tier_candidates:
                if item['level_num'] in taken_levels:
                    continue
                if pool <= 0:
                    break

                min_invest = Decimal(str(item['min_investment']))
                half_allocation = pool * Decimal('0.5')

                # Check 1: 50% >= minimum?
                if half_allocation >= min_invest:
                    actions.append({
                        'symbol': item['symbol'],
                        'level': item['trigger']['level'],
                        'amount': float(half_allocation),
                        'tier': tier_name
                    })
                    taken_levels.add(item['level_num'])
                    pool -= half_allocation
                    continue

                # Check 2: Entire pool >= minimum?
                if pool >= min_invest:
                    actions.append({
                        'symbol': item['symbol'],
                        'level': item['trigger']['level'],
                        'amount': float(pool),
                        'tier': tier_name
                    })
                    taken_levels.add(item['level_num'])
                    pool = Decimal('0')
                    break  # Stop this tier

                # Neither check passed — skip coin

        return actions

    @classmethod
    def _activate_grid(cls, symbol, level, exit_multiplier=2.0, amount=None):
        """Activate a master grid for a coin on Binance"""
        try:
            from apps.wallets.services.binance_service import BinanceService

            token = CryptoToken.objects.get(symbol=symbol)
            current_price = token.current_price
            upper = current_price * Decimal('1.8')
            lower = current_price * Decimal('0.2')
            invest = Decimal(str(amount)) if amount else cls.get_min_investment(symbol)

            # Calculate max grids based on $10 minimum per order
            max_grids = int(invest / Decimal('10'))
            if max_grids > 100:
                max_grids = 100
            if max_grids < 2:
                max_grids = 2

            bs = BinanceService()
            result = bs.place_grid_orders(
                symbol=symbol,
                lower_price=lower,
                upper_price=upper,
                total_amount=invest,
                grids=max_grids
            )

            if not result['success']:
                print(f"Failed to place Binance orders for {symbol}: {result.get('error')}")
                return False

            MasterGridBot.objects.create(
                token=token,
                total_amount=invest,
                lower_price=lower,
                upper_price=upper,
                grids=result['orders_placed'],
                status='ACTIVE',
                price_at_creation=current_price,
                metadata={
                    'fadakka_level': level,
                    'exit_multiplier': exit_multiplier,
                    'fadakka_k': float(cls.get_fadakka(symbol)),
                    'activation_price': float(current_price),
                    'binance_order_ids': result['order_ids'],
                    'binance_symbol': result['symbol'],
                }
            )

            print(
                f"✅ Grid activated: {symbol} at {level} (${float(invest):.2f}, {max_grids} grids, Exit: {exit_multiplier}K)")
            return True

        except Exception as e:
            print(f"Error activating grid for {symbol}: {e}")
            return False

    @classmethod
    def _close_grid(cls, symbol):
        """Close all active master grids for a coin on Binance"""
        try:
            from apps.wallets.services.binance_service import BinanceService

            bs = BinanceService()

            grids = MasterGridBot.objects.filter(
                token__symbol=symbol,
                status='ACTIVE'
            )

            for grid in grids:
                # Cancel open orders on Binance
                order_ids = grid.metadata.get('binance_order_ids', [])
                cancel_result = bs.cancel_grid_orders(symbol, order_ids)
                print(f"Cancelled {cancel_result.get('cancelled', 0)} orders for {symbol}")

                # Sell accumulated position at market
                sell_result = bs.market_sell_position(symbol)

                # Get filled trades for profit calculation
                trade_history = bs.get_filled_grid_orders(
                    symbol,
                    start_time=grid.created_at
                )

                profit = Decimal(str(trade_history.get('profit', 0)))

                # Update grid record
                grid.grid_profit = profit
                grid.status = 'COMPLETED'
                grid.metadata['close_price'] = str(sell_result.get('avg_price', 0))
                grid.metadata['close_profit'] = str(profit)
                grid.metadata['close_trades'] = trade_history.get('total_trades', 0)
                grid.save()

                print(f"🔒 Closed grid for {symbol}: Profit ${float(profit):.2f}")

        except Exception as e:
            print(f"Error closing grid for {symbol}: {e}")