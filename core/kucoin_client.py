import ccxt
import time
from typing import Dict, Any, Optional, List
from utils.config import config
from utils.logger import logger

class KuCoinClient:
    def __init__(self):
        self.exchange = None
        self.is_connected = False
        self._initialize_exchange()
    
    def _initialize_exchange(self):
        """Initialize KuCoin exchange connection"""
        try:
            # Validate API credentials
            if not config.validate_secrets():
                raise ValueError("Missing KuCoin API credentials in environment variables")
            
            # Initialize exchange
            self.exchange = ccxt.kucoin({
                'apiKey': config.get_secret('api_key'),
                'secret': config.get_secret('api_secret'),
                'password': config.get_secret('api_passphrase'),
                'sandbox': config.is_sandbox_mode(),
                'enableRateLimit': True,
                'options': {
                    'fetchCurrencies': True,
                }
            })
            
            # Test connection
            self._test_connection()
            self.is_connected = True
            logger.info(f"KuCoin client initialized - Sandbox: {config.is_sandbox_mode()}")
            
        except Exception as e:
            logger.error(f"Failed to initialize KuCoin client: {str(e)}")
            self.is_connected = False
            raise
    
    def _test_connection(self):
        """Test API connection"""
        try:
            self.exchange.fetch_balance()
            logger.info("KuCoin API connection successful")
        except Exception as e:
            logger.error(f"KuCoin API connection failed: {str(e)}")
            raise
    
    def get_balance(self, currency: str = 'USDT') -> float:
        """Get balance for specific currency"""
        try:
            balance = self.exchange.fetch_balance()
            return float(balance.get(currency, {}).get('free', 0))
        except Exception as e:
            logger.error(f"Error fetching balance for {currency}", e)
            return 0.0
    
    def get_btc_balance(self) -> float:
        """Get BTC balance"""
        return self.get_balance('BTC')
    
    def get_usdt_balance(self) -> float:
        """Get USDT balance"""
        return self.get_balance('USDT')
    
    def get_current_price(self, symbol: str = None) -> Optional[float]:
        """Get current market price"""
        symbol = symbol or config.get_trading_symbol()
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}", e)
            return None
    
    def get_order_book(self, symbol: str = None, limit: int = 20) -> Optional[Dict]:
        """Get order book"""
        symbol = symbol or config.get_trading_symbol()
        try:
            return self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}", e)
            return None
    
    def get_bid_ask_spread(self, symbol: str = None) -> Optional[Dict[str, float]]:
        """Get current bid/ask prices and spread"""
        symbol = symbol or config.get_trading_symbol()
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            bid = float(ticker['bid'])
            ask = float(ticker['ask'])
            spread = ask - bid
            spread_percent = (spread / bid) * 100
            
            return {
                'bid': bid,
                'ask': ask,
                'spread': spread,
                'spread_percent': spread_percent
            }
        except Exception as e:
            logger.error(f"Error fetching bid/ask for {symbol}", e)
            return None
    
    def place_market_buy_order(self, symbol: str, amount_usdt: float) -> Optional[Dict]:
        """Place market buy order using USDT amount"""
        try:
            # Get current price to calculate BTC amount
            current_price = self.get_current_price(symbol)
            if not current_price:
                logger.error("Cannot place order: Unable to fetch current price")
                return None
            
            # Calculate BTC amount
            btc_amount = amount_usdt / current_price
            btc_amount = round(btc_amount, 8)  # Round to 8 decimal places
            
            # Place market buy order
            order = self.exchange.create_market_buy_order(symbol, btc_amount)
            
            logger.trade(
                action="BUY_MARKET",
                symbol=symbol,
                price=current_price,
                amount=btc_amount,
                mode="LIVE" if not config.is_sandbox_mode() else "SANDBOX"
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error placing market buy order: {str(e)}")
            return None
    
    def place_limit_buy_order(self, symbol: str, amount: float, price: float) -> Optional[Dict]:
        """Place limit buy order"""
        try:
            order = self.exchange.create_limit_buy_order(symbol, amount, price)
            
            logger.trade(
                action="BUY_LIMIT",
                symbol=symbol,
                price=price,
                amount=amount,
                mode="LIVE" if not config.is_sandbox_mode() else "SANDBOX"
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error placing limit buy order: {str(e)}")
            return None
    
    def place_conditional_buy_order(self, symbol: str, amount_usdt: float, trigger_price: float) -> Optional[Dict]:
        """Place buy order that triggers when price drops to trigger_price"""
        try:
            # Calculate BTC amount based on trigger price
            btc_amount = amount_usdt / trigger_price
            btc_amount = round(btc_amount, 8)
            
            # Place limit buy order at trigger price
            order = self.place_limit_buy_order(symbol, btc_amount, trigger_price)
            return order
            
        except Exception as e:
            logger.error(f"Error placing conditional buy order: {str(e)}")
            return None
    
    def place_limit_sell_order(self, symbol: str, amount: float, price: float) -> Optional[Dict]:
        """Place limit sell order"""
        try:
            order = self.exchange.create_limit_sell_order(symbol, amount, price)
            
            logger.trade(
                action="SELL_LIMIT",
                symbol=symbol,
                price=price,
                amount=amount,
                mode="LIVE" if not config.is_sandbox_mode() else "SANDBOX"
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error placing limit sell order: {str(e)}")
            return None
    
    def place_conditional_sell_order(self, symbol: str, amount: float, target_price: float) -> Optional[Dict]:
        """Place sell order that triggers when price rises to target_price"""
        try:
            order = self.place_limit_sell_order(symbol, amount, target_price)
            return order
            
        except Exception as e:
            logger.error(f"Error placing conditional sell order: {str(e)}")
            return None
    
    def place_market_sell_order(self, symbol: str, amount: float) -> Optional[Dict]:
        """Place market sell order"""
        try:
            order = self.exchange.create_market_sell_order(symbol, amount)
            
            current_price = self.get_current_price(symbol)
            logger.trade(
                action="SELL_MARKET",
                symbol=symbol,
                price=current_price or 0,
                amount=amount,
                mode="LIVE" if not config.is_sandbox_mode() else "SANDBOX"
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error placing market sell order: {str(e)}")
            return None
    
    def get_order_status(self, order_id: str, symbol: str = None) -> Optional[Dict]:
        """Get order status"""
        symbol = symbol or config.get_trading_symbol()
        try:
            return self.exchange.fetch_order(order_id, symbol)
        except Exception as e:
            logger.error(f"Error fetching order status for {order_id}", e)
            return None
    
    def cancel_order(self, order_id: str, symbol: str = None) -> bool:
        """Cancel order"""
        symbol = symbol or config.get_trading_symbol()
        try:
            self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}", e)
            return False
    
    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """Get open orders"""
        symbol = symbol or config.get_trading_symbol()
        try:
            return self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            logger.error(f"Error fetching open orders for {symbol}", e)
            return []
    
    def get_trade_history(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """Get trade history"""
        symbol = symbol or config.get_trading_symbol()
        try:
            return self.exchange.fetch_my_trades(symbol, limit=limit)
        except Exception as e:
            logger.error(f"Error fetching trade history for {symbol}", e)
            return []
    
    def get_order_fills(self, order_id: str, symbol: str = None) -> List[Dict]:
        """Get fills for a specific order"""
        symbol = symbol or config.get_trading_symbol()
        try:
            return self.exchange.fetch_order_trades(order_id, symbol)
        except Exception as e:
            logger.error(f"Error fetching order fills for {order_id}", e)
            return []
    
    def calculate_average_fill_price(self, order_id: str, symbol: str = None) -> Optional[float]:
        """Calculate average fill price for an order"""
        fills = self.get_order_fills(order_id, symbol)
        if not fills:
            # Fallback to order info
            order = self.get_order_status(order_id, symbol)
            if order and order.get('average'):
                return float(order['average'])
            return None
        
        total_cost = sum(float(fill['cost']) for fill in fills)
        total_amount = sum(float(fill['amount']) for fill in fills)
        
        return total_cost / total_amount if total_amount > 0 else None
    
    def get_trading_fees(self, symbol: str = None) -> Dict[str, float]:
        """Get trading fees"""
        symbol = symbol or config.get_trading_symbol()
        try:
            markets = self.exchange.load_markets()
            market = markets.get(symbol, {})
            return {
                'maker': market.get('maker', 0.001),  # Default 0.1%
                'taker': market.get('taker', 0.001)   # Default 0.1%
            }
        except Exception as e:
            logger.error(f"Error fetching trading fees for {symbol}", e)
            return {'maker': 0.001, 'taker': 0.001}
    
    def get_minimum_order_size(self, symbol: str = None) -> Dict[str, float]:
        """Get minimum order size constraints"""
        symbol = symbol or config.get_trading_symbol()
        try:
            markets = self.exchange.load_markets()
            market = markets.get(symbol, {})
            limits = market.get('limits', {})
            
            return {
                'amount_min': float(limits.get('amount', {}).get('min', 0.00001)),
                'amount_max': float(limits.get('amount', {}).get('max', 1000000)),
                'cost_min': float(limits.get('cost', {}).get('min', 1)),
                'cost_max': float(limits.get('cost', {}).get('max', 1000000))
            }
        except Exception as e:
            logger.error(f"Error fetching minimum order size for {symbol}", e)
            return {
                'amount_min': 0.00001,
                'amount_max': 1000000,
                'cost_min': 1,
                'cost_max': 1000000
            }
    
    def validate_order_size(self, symbol: str, amount: float, price: float) -> tuple[bool, str]:
        """Validate if order meets minimum size requirements"""
        try:
            limits = self.get_minimum_order_size(symbol)
            cost = amount * price
            
            if amount < limits['amount_min']:
                return False, f"Amount too small. Minimum: {limits['amount_min']:.8f}"
            
            if amount > limits['amount_max']:
                return False, f"Amount too large. Maximum: {limits['amount_max']:.8f}"
            
            if cost < limits['cost_min']:
                return False, f"Order value too small. Minimum: ${limits['cost_min']:.2f}"
            
            if cost > limits['cost_max']:
                return False, f"Order value too large. Maximum: ${limits['cost_max']:.2f}"
            
            return True, "Order size is valid"
            
        except Exception as e:
            logger.error(f"Error validating order size: {str(e)}")
            return False, f"Validation error: {str(e)}"

# Global client instance
kucoin_client = KuCoinClient()