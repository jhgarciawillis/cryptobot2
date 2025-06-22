import time
import threading
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime

from utils.config import config
from utils.logger import logger
from utils.helpers import calculate_position_size, is_profitable_exit, calculate_required_sell_price, validate_profit_margin, get_timestamp
from core.kucoin_client import kucoin_client
from core.simulator import simulator
from core.position_manager import position_manager

class BotState(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

class TradingEngine:
    """Main trading engine implementing the limit order profit strategy"""
    
    def __init__(self):
        self.state = BotState.STOPPED
        self.symbol = config.get_trading_symbol()
        self.user_profit_margin = config.get_user_profit_margin()
        self.buy_trigger_percent = config.get_buy_trigger_percent()
        self.is_simulation = config.is_simulation_mode()
        
        # Trading thread
        self._trading_thread = None
        self._stop_event = threading.Event()
        
        # Client selection based on mode
        self.client = simulator if self.is_simulation else kucoin_client
        
        # State tracking
        self.last_price = None
        self.last_check_time = None
        self.pending_exit = False
        
        # Order tracking for limit orders
        self.pending_buy_orders = {}  # Track pending buy orders
        self.pending_sell_orders = {}  # Track pending sell orders
        
        # Order type preference
        self.order_type = config.get_order_type_preference()  # 'limit' or 'market'
        
        logger.info(f"Trading Engine initialized - Mode: {'SIMULATION' if self.is_simulation else 'LIVE'}")
        logger.info(f"Order type: {self.order_type} | Profit margin: {self.user_profit_margin*100:.3f}%")
    
    def start_trading(self) -> bool:
        """Start the trading bot"""
        try:
            if self.state == BotState.RUNNING:
                logger.warning("Trading bot is already running")
                return False
            
            # Validate setup
            if not self._validate_setup():
                return False
            
            # Get current price and make initial purchase
            current_price = self.client.get_current_price(self.symbol)
            if not current_price:
                logger.error("Cannot start trading: Unable to fetch current price")
                return False
            
            # Make initial purchase with available balance
            if not self._make_initial_purchase(current_price):
                return False
            
            # Start trading loop
            self.state = BotState.RUNNING
            self.pending_exit = False
            self._stop_event.clear()
            
            self._trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
            self._trading_thread.start()
            
            logger.info("Trading bot started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting trading bot: {str(e)}")
            self.state = BotState.ERROR
            return False
    
    def stop_trading(self):
        """Stop the trading bot and look for exit opportunity"""
        if self.state != BotState.RUNNING:
            logger.warning("Trading bot is not running")
            return
        
        logger.info("Stop signal received - Looking for profitable exit...")
        self.pending_exit = True
        # Don't stop the thread yet, let it find a profitable exit
    
    def force_stop(self):
        """Force stop the trading bot immediately"""
        logger.info("Force stopping trading bot...")
        self.state = BotState.STOPPING
        self._stop_event.set()
        
        # Cancel all pending orders
        self._cancel_all_pending_orders()
        
        if self._trading_thread and self._trading_thread.is_alive():
            self._trading_thread.join(timeout=5)
        
        self.state = BotState.STOPPED
        logger.info("Trading bot force stopped")
    
    def set_profit_margin(self, margin_percent: float) -> bool:
        """Set new profit margin"""
        try:
            # Convert percentage to decimal
            margin_decimal = margin_percent / 100
            
            # Validate margin
            is_valid, message, suggested = validate_profit_margin(margin_decimal)
            
            if not is_valid:
                logger.error(f"Invalid profit margin: {message}")
                return False
            
            self.user_profit_margin = margin_decimal
            config.set_user_profit_margin(self.user_profit_margin)
            
            logger.info(f"Profit margin set to {margin_percent:.3f}%")
            return True
            
        except Exception as e:
            logger.error(f"Error setting profit margin: {str(e)}")
            return False
    
    def set_order_type(self, order_type: str) -> bool:
        """Set order type preference"""
        if order_type in ['limit', 'market']:
            self.order_type = order_type
            config.set_order_type_preference(order_type)
            logger.info(f"Order type set to: {order_type}")
            return True
        return False
    
    def _validate_setup(self) -> bool:
        """Validate trading setup"""
        try:
            # Check API connection (skip for simulation)
            if not self.is_simulation and not kucoin_client.is_connected:
                logger.error("KuCoin API not connected")
                return False
            
            # Validate profit margin
            is_valid, message = config.validate_profit_margin_setting()
            if not is_valid:
                logger.error(f"Invalid profit margin: {message}")
                return False
            
            # Check minimum balance
            usdt_balance = self.client.get_usdt_balance()
            min_trade_amount = config.get('trading.min_trade_amount', 10)
            
            if usdt_balance < min_trade_amount:
                logger.error(f"Insufficient USDT balance: ${usdt_balance:.2f} < ${min_trade_amount}")
                return False
            
            logger.info(f"Setup validation passed - USDT Balance: ${usdt_balance:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Setup validation failed: {str(e)}")
            return False
    
    def _make_initial_purchase(self, current_price: float) -> bool:
        """Make initial BTC purchase"""
        try:
            usdt_balance = self.client.get_usdt_balance()
            purchase_amount = usdt_balance * 0.95  # Use 95% of balance, keep 5% buffer
            
            logger.info(f"Making initial purchase: ${purchase_amount:.2f} worth of BTC at ${current_price:.2f}")
            
            if self.order_type == 'limit':
                # Place limit order slightly below current price
                buy_price = current_price * 0.999  # 0.1% below market
                order = self._execute_limit_buy(buy_price, purchase_amount)
            else:
                # Use market order
                if self.is_simulation:
                    order = self.client.simulate_market_buy(self.symbol, purchase_amount)
                else:
                    order = self.client.place_market_buy_order(self.symbol, purchase_amount)
            
            if not order:
                logger.error("Failed to place initial buy order")
                return False
            
            # For market orders, add position immediately
            if self.order_type == 'market':
                btc_amount = purchase_amount / current_price  # Approximate
                position_manager.add_position(self.symbol, current_price, btc_amount)
            
            return True
            
        except Exception as e:
            logger.error(f"Error making initial purchase: {str(e)}")
            return False
    
    def _trading_loop(self):
        """Main trading loop for limit orders"""
        logger.info("Trading loop started with limit order strategy")
        
        try:
            while not self._stop_event.is_set() and self.state == BotState.RUNNING:
                
                # Check pending orders first
                self._check_pending_orders()
                
                # Get current price
                current_price = self.client.get_current_price(self.symbol)
                if not current_price:
                    logger.warning("Unable to fetch current price, retrying...")
                    time.sleep(5)
                    continue
                
                self.last_price = current_price
                self.last_check_time = datetime.now()
                
                # Check for profitable exit if stopping
                if self.pending_exit:
                    if self._check_profitable_exit(current_price):
                        break
                else:
                    # Normal trading logic
                    self._execute_trading_logic(current_price)
                
                # Check and fill any pending orders (simulation only)
                if self.is_simulation:
                    self.client.check_and_fill_orders()
                
                # Sleep before next iteration
                time.sleep(config.get('ui.refresh_interval', 5))
                
        except Exception as e:
            logger.error(f"Error in trading loop: {str(e)}")
            self.state = BotState.ERROR
        finally:
            self.state = BotState.STOPPED
            logger.info("Trading loop ended")
    
    def _execute_trading_logic(self, current_price: float):
        """Execute main trading logic"""
        try:
            # Check if we should place new buy orders
            if self._should_place_buy_order(current_price):
                trigger_price = self._calculate_buy_trigger_price(current_price)
                self._execute_buy_order(trigger_price)
            
            # For market orders, check immediate sell opportunities
            if self.order_type == 'market':
                self._check_sell_opportunities(current_price)
                
        except Exception as e:
            logger.error(f"Error in trading logic: {str(e)}")
    
    def _should_place_buy_order(self, current_price: float) -> bool:
        """Check if we should place a buy order"""
        # Check if we have enough USDT for another purchase
        usdt_balance = self.client.get_usdt_balance()
        min_trade_amount = config.get('trading.min_trade_amount', 10)
        
        if usdt_balance < min_trade_amount:
            return False
        
        # Check if price has dropped enough from last purchase
        return position_manager.should_buy_more(current_price, self.buy_trigger_percent)
    
    def _calculate_buy_trigger_price(self, current_price: float) -> float:
        """Calculate the price that should trigger a buy"""
        last_buy_price = position_manager.get_last_buy_price()
        
        if not last_buy_price:
            # First purchase - buy slightly below current price
            return current_price * (1 - self.buy_trigger_percent / 100)
        
        # Subsequent purchases - based on last buy price
        return last_buy_price * (1 - self.buy_trigger_percent / 100)
    
    def _execute_buy_order(self, trigger_price: float):
        """Execute buy order based on order type"""
        try:
            usdt_balance = self.client.get_usdt_balance()
            purchase_amount = min(usdt_balance * 0.95, usdt_balance - 5)  # Keep buffer
            
            if purchase_amount < config.get('trading.min_trade_amount', 10):
                return
            
            if self.order_type == 'limit':
                self._execute_limit_buy(trigger_price, purchase_amount)
            else:
                self._execute_market_buy(purchase_amount)
                
        except Exception as e:
            logger.error(f"Error executing buy order: {str(e)}")
    
    def _execute_limit_buy(self, trigger_price: float, amount_usdt: float = None) -> Optional[Dict]:
        """Execute limit buy order at trigger price"""
        try:
            if amount_usdt is None:
                usdt_balance = self.client.get_usdt_balance()
                amount_usdt = min(usdt_balance * 0.95, usdt_balance - 5)
            
            if amount_usdt < config.get('trading.min_trade_amount', 10):
                return None
            
            logger.info(f"Placing limit buy: ${amount_usdt:.2f} at ${trigger_price:.2f}")
            
            if self.is_simulation:
                order = self.client.simulate_conditional_buy(self.symbol, amount_usdt, trigger_price)
            else:
                order = self.client.place_conditional_buy_order(self.symbol, amount_usdt, trigger_price)
            
            if order:
                self.pending_buy_orders[order['id']] = {
                    'order': order,
                    'trigger_price': trigger_price,
                    'amount_usdt': amount_usdt,
                    'timestamp': get_timestamp()
                }
            
            return order
            
        except Exception as e:
            logger.error(f"Error executing limit buy: {str(e)}")
            return None
    
    def _execute_market_buy(self, amount_usdt: float):
        """Execute market buy order"""
        try:
            current_price = self.client.get_current_price(self.symbol)
            logger.info(f"Executing market buy: ${amount_usdt:.2f} at ${current_price:.2f}")
            
            if self.is_simulation:
                order = self.client.simulate_market_buy(self.symbol, amount_usdt)
            else:
                order = self.client.place_market_buy_order(self.symbol, amount_usdt)
            
            if order:
                # Add position immediately for market orders
                btc_amount = amount_usdt / current_price
                position = position_manager.add_position(self.symbol, current_price, btc_amount)
                
                # Place corresponding sell order
                self._place_sell_order_for_position(position, current_price)
            
        except Exception as e:
            logger.error(f"Error executing market buy: {str(e)}")
    
    def _check_pending_orders(self):
        """Check status of pending orders and update positions accordingly"""
        # Check buy orders
        for order_id in list(self.pending_buy_orders.keys()):
            order_data = self.pending_buy_orders[order_id]
            order_status = self.client.get_order_status(order_id, self.symbol)
            
            if order_status and order_status['status'] == 'closed':
                # Buy order filled - create position and place sell order
                fill_price = self.client.calculate_average_fill_price(order_id)
                if fill_price:
                    # Add position
                    btc_amount = order_data['amount_usdt'] / fill_price
                    position = position_manager.add_position(self.symbol, fill_price, btc_amount)
                    
                    # Place sell order
                    self._place_sell_order_for_position(position, fill_price)
                
                # Remove from pending
                del self.pending_buy_orders[order_id]
        
        # Check sell orders
        for order_id in list(self.pending_sell_orders.keys()):
            order_data = self.pending_sell_orders[order_id]
            order_status = self.client.get_order_status(order_id, self.symbol)
            
            if order_status and order_status['status'] == 'closed':
                # Sell order filled - close position
                fill_price = self.client.calculate_average_fill_price(order_id)
                if fill_price:
                    position = order_data['position']
                    position_manager.close_position(position, fill_price)
                    logger.info(f"Position closed at ${fill_price:.2f}")
                
                # Remove from pending
                del self.pending_sell_orders[order_id]
    
    def _place_sell_order_for_position(self, position, buy_price: float):
       """Place sell order for a position"""
       try:
           # Calculate sell target based on user's desired margin
           sell_target = calculate_required_sell_price(buy_price, self.user_profit_margin)
           
           logger.info(f"Placing sell order: {position.amount:.6f} BTC at ${sell_target:.2f}")
           
           if self.order_type == 'limit':
               if self.is_simulation:
                   order = self.client.simulate_conditional_sell(self.symbol, position.amount, sell_target)
               else:
                   order = self.client.place_conditional_sell_order(self.symbol, position.amount, sell_target)
               
               if order:
                   self.pending_sell_orders[order['id']] = {
                       'order': order,
                       'position': position,
                       'target_price': sell_target,
                       'timestamp': get_timestamp()
                   }
           else:
               # For market orders, we'll check for immediate opportunities in the trading loop
               pass
               
       except Exception as e:
           logger.error(f"Error placing sell order: {str(e)}")
   
    def _check_sell_opportunities(self, current_price: float):
       """Check for profitable sell opportunities (market orders)"""
       try:
           open_positions = position_manager.get_open_positions()
           
           for position in open_positions:
               sell_target = calculate_required_sell_price(position.buy_price, self.user_profit_margin)
               
               if current_price >= sell_target:
                   self._execute_sell(position, current_price)
                   
       except Exception as e:
           logger.error(f"Error checking sell opportunities: {str(e)}")
   
    def _execute_sell(self, position, current_price: float):
       """Execute sell order"""
       try:
           logger.info(f"Executing sell: {position.amount:.6f} BTC at ${current_price:.2f}")
           
           if self.is_simulation:
               order = self.client.simulate_market_sell(self.symbol, position.amount)
           else:
               order = self.client.place_market_sell_order(self.symbol, position.amount)
           
           if order:
               # Close position
               profit_pct = position_manager.close_position(position, current_price)
               logger.info(f"Position closed with {profit_pct:+.2f}% profit")
           
       except Exception as e:
           logger.error(f"Error executing sell: {str(e)}")
   
    def _check_profitable_exit(self, current_price: float) -> bool:
       """Check if we can exit all positions profitably"""
       try:
           open_positions = position_manager.get_open_positions()
           if not open_positions:
               logger.info("No open positions - exit complete")
               return True
           
           # Check each position against its individual profit target
           profitable_positions = []
           for position in open_positions:
               sell_target = calculate_required_sell_price(position.buy_price, self.user_profit_margin)
               if current_price >= sell_target:
                   profitable_positions.append(position)
           
           if len(profitable_positions) == len(open_positions):
               # All positions are profitable - sell everything
               logger.info("All positions profitable - executing complete exit")
               
               for position in profitable_positions:
                   self._execute_sell(position, current_price)
               
               return True
           else:
               remaining = len(open_positions) - len(profitable_positions)
               logger.info(f"Waiting for profitable exit - {remaining} positions still underwater")
               
               # Sell profitable positions to reduce risk
               for position in profitable_positions:
                   self._execute_sell(position, current_price)
               
               return False
               
       except Exception as e:
           logger.error(f"Error checking profitable exit: {str(e)}")
           return False
   
    def _cancel_all_pending_orders(self):
       """Cancel all pending orders"""
       try:
           # Cancel pending buy orders
           for order_id in list(self.pending_buy_orders.keys()):
               if self.client.cancel_order(order_id, self.symbol):
                   del self.pending_buy_orders[order_id]
           
           # Cancel pending sell orders
           for order_id in list(self.pending_sell_orders.keys()):
               if self.client.cancel_order(order_id, self.symbol):
                   del self.pending_sell_orders[order_id]
           
           logger.info("All pending orders cancelled")
           
       except Exception as e:
           logger.error(f"Error cancelling pending orders: {str(e)}")
   
    def get_status(self) -> Dict[str, Any]:
       """Get current bot status"""
       current_price = self.last_price or self.client.get_current_price(self.symbol)
       
       status = {
           'state': self.state.value,
           'pending_exit': self.pending_exit,
           'current_price': current_price,
           'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
           'symbol': self.symbol,
           'mode': 'simulation' if self.is_simulation else 'live',
           'order_type': self.order_type,
           'profit_margin': self.user_profit_margin * 100  # Convert to percentage
       }
       
       # Add balance information
       status['balances'] = {
           'USDT': self.client.get_usdt_balance(),
           'BTC': self.client.get_btc_balance()
       }
       
       # Add position information
       open_positions = position_manager.get_open_positions()
       status['positions'] = {
           'count': len(open_positions),
           'total_btc': position_manager.get_total_btc_amount(),
           'average_buy_price': position_manager.get_average_buy_price()
       }
       
       # Add pending orders information
       status['pending_orders'] = {
           'buy_orders': len(self.pending_buy_orders),
           'sell_orders': len(self.pending_sell_orders),
           'total_pending': len(self.pending_buy_orders) + len(self.pending_sell_orders)
       }
       
       # Add P&L information
       if current_price:
           unrealized_pnl = position_manager.get_unrealized_pnl(current_price)
           realized_pnl = position_manager.get_realized_pnl()
           
           status['pnl'] = {
               'unrealized': unrealized_pnl,
               'realized': realized_pnl
           }
       
       return status
   
    def get_pending_orders_details(self) -> Dict[str, List[Dict]]:
       """Get detailed information about pending orders"""
       return {
           'buy_orders': list(self.pending_buy_orders.values()),
           'sell_orders': list(self.pending_sell_orders.values())
       }
   
    def reset_bot(self):
       """Reset bot to initial state"""
       if self.state == BotState.RUNNING:
           self.force_stop()
       
       # Clear pending orders
       self.pending_buy_orders.clear()
       self.pending_sell_orders.clear()
       
       # Clear positions
       position_manager.clear_all_positions()
       
       # Reset simulator if in simulation mode
       if self.is_simulation:
           simulator.reset_simulation()
       
       logger.info("Bot reset to initial state")

# Global trading engine instance
trading_engine = TradingEngine()