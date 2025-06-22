import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils.config import config
from utils.logger import logger
from utils.helpers import save_json_file, load_json_file, get_timestamp, calculate_profit_percentage

class TradingSimulator:
    """Paper trading simulator with exact same logic as live trading"""
    
    def __init__(self, initial_balance: float = None):
        self.initial_balance = initial_balance or config.get_secret('initial_balance')
        self.balances = {
            'USDT': self.initial_balance,
            'BTC': 0.0
        }
        self.orders = []
        self.trades = []
        self.positions = []
        self.order_id_counter = 1
        self.pending_orders = []  # For limit orders
        
        # Load previous simulation data if exists
        self._load_simulation_state()
        
        logger.info(f"Trading simulator initialized - Initial balance: ${self.initial_balance}")
    
    def _load_simulation_state(self):
        """Load simulation state from file"""
        try:
            state = load_json_file("data/simulation_state.json")
            if state:
                self.balances = state.get('balances', self.balances)
                self.orders = state.get('orders', [])
                self.trades = state.get('trades', [])
                self.positions = state.get('positions', [])
                self.pending_orders = state.get('pending_orders', [])
                self.order_id_counter = state.get('order_id_counter', 1)
                logger.info("Loaded previous simulation state")
        except Exception as e:
            logger.error(f"Error loading simulation state: {str(e)}")
    
    def _save_simulation_state(self):
        """Save simulation state to file"""
        try:
            state = {
                'balances': self.balances,
                'orders': self.orders,
                'trades': self.trades,
                'positions': self.positions,
                'pending_orders': self.pending_orders,
                'order_id_counter': self.order_id_counter,
                'last_updated': get_timestamp()
            }
            save_json_file("data/simulation_state.json", state)
        except Exception as e:
            logger.error(f"Error saving simulation state: {str(e)}")
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        order_id = f"SIM_{self.order_id_counter:06d}"
        self.order_id_counter += 1
        return order_id
    
    def get_balance(self, currency: str = 'USDT') -> float:
       """Get simulated balance"""
       return self.balances.get(currency, 0.0)
   
    def get_btc_balance(self) -> float:
       """Get simulated BTC balance"""
       return self.get_balance('BTC')
   
    def get_usdt_balance(self) -> float:
       """Get simulated USDT balance"""
       return self.get_balance('USDT')
   
    def get_current_price(self, symbol: str = None) -> Optional[float]:
       """Get current market price (same as live)"""
       # In simulation, we still use real market prices
       from core.kucoin_client import kucoin_client
       return kucoin_client.get_current_price(symbol)
   
    def get_bid_ask_spread(self, symbol: str = None) -> Optional[Dict[str, float]]:
       """Get current bid/ask prices and spread"""
       from core.kucoin_client import kucoin_client
       return kucoin_client.get_bid_ask_spread(symbol)
   
    def simulate_market_buy(self, symbol: str, amount_usdt: float) -> Optional[Dict]:
       """Simulate market buy order"""
       try:
           current_price = self.get_current_price(symbol)
           if not current_price:
               logger.error("Cannot simulate buy: Unable to fetch current price")
               return None
           
           # Check if we have enough USDT
           if self.balances['USDT'] < amount_usdt:
               logger.error(f"Insufficient USDT balance: {self.balances['USDT']} < {amount_usdt}")
               return None
           
           # Calculate BTC amount (accounting for fees)
           fees = self._calculate_fees(amount_usdt, 'taker')
           net_usdt = amount_usdt - fees
           btc_amount = net_usdt / current_price
           
           # Execute simulated trade
           self.balances['USDT'] -= amount_usdt
           self.balances['BTC'] += btc_amount
           
           # Create order record
           order = {
               'id': self._generate_order_id(),
               'symbol': symbol,
               'type': 'market',
               'side': 'buy',
               'amount': btc_amount,
               'price': current_price,
               'cost': amount_usdt,
               'fees': fees,
               'status': 'closed',
               'timestamp': get_timestamp()
           }
           
           self.orders.append(order)
           self.trades.append(order.copy())
           
           logger.trade(
               action="BUY",
               symbol=symbol,
               price=current_price,
               amount=btc_amount,
               mode="SIMULATION"
           )
           
           self._save_simulation_state()
           return order
           
       except Exception as e:
           logger.error(f"Error in simulated market buy: {str(e)}")
           return None
   
    def simulate_limit_buy(self, symbol: str, amount: float, price: float) -> Optional[Dict]:
       """Simulate limit buy order"""
       try:
           # Calculate cost
           cost = amount * price
           
           # Check if we have enough USDT
           if self.balances['USDT'] < cost:
               logger.error(f"Insufficient USDT balance: {self.balances['USDT']} < {cost}")
               return None
           
           # Create pending order
           order = {
               'id': self._generate_order_id(),
               'symbol': symbol,
               'type': 'limit',
               'side': 'buy',
               'amount': amount,
               'price': price,
               'cost': cost,
               'fees': 0,  # Will be calculated when filled
               'status': 'open',
               'timestamp': get_timestamp()
           }
           
           self.orders.append(order)
           self.pending_orders.append(order['id'])
           
           logger.trade(
               action="BUY_LIMIT",
               symbol=symbol,
               price=price,
               amount=amount,
               mode="SIMULATION"
           )
           
           self._save_simulation_state()
           return order
           
       except Exception as e:
           logger.error(f"Error in simulated limit buy: {str(e)}")
           return None
   
    def simulate_conditional_buy(self, symbol: str, amount_usdt: float, trigger_price: float) -> Optional[Dict]:
       """Simulate conditional buy order"""
       btc_amount = amount_usdt / trigger_price
       btc_amount = round(btc_amount, 8)
       return self.simulate_limit_buy(symbol, btc_amount, trigger_price)
   
    def simulate_market_sell(self, symbol: str, amount: float) -> Optional[Dict]:
       """Simulate market sell order"""
       try:
           current_price = self.get_current_price(symbol)
           if not current_price:
               logger.error("Cannot simulate sell: Unable to fetch current price")
               return None
           
           # Check if we have enough BTC
           if self.balances['BTC'] < amount:
               logger.error(f"Insufficient BTC balance: {self.balances['BTC']} < {amount}")
               return None
           
           # Calculate USDT amount (accounting for fees)
           gross_usdt = amount * current_price
           fees = self._calculate_fees(gross_usdt, 'taker')
           net_usdt = gross_usdt - fees
           
           # Execute simulated trade
           self.balances['BTC'] -= amount
           self.balances['USDT'] += net_usdt
           
           # Create order record
           order = {
               'id': self._generate_order_id(),
               'symbol': symbol,
               'type': 'market',
               'side': 'sell',
               'amount': amount,
               'price': current_price,
               'cost': gross_usdt,
               'fees': fees,
               'status': 'closed',
               'timestamp': get_timestamp()
           }
           
           self.orders.append(order)
           self.trades.append(order.copy())
           
           logger.trade(
               action="SELL",
               symbol=symbol,
               price=current_price,
               amount=amount,
               mode="SIMULATION"
           )
           
           self._save_simulation_state()
           return order
           
       except Exception as e:
           logger.error(f"Error in simulated market sell: {str(e)}")
           return None
   
    def simulate_limit_sell(self, symbol: str, amount: float, price: float) -> Optional[Dict]:
       """Simulate limit sell order"""
       try:
           # Check if we have enough BTC
           if self.balances['BTC'] < amount:
               logger.error(f"Insufficient BTC balance: {self.balances['BTC']} < {amount}")
               return None
           
           # Create pending order
           order = {
               'id': self._generate_order_id(),
               'symbol': symbol,
               'type': 'limit',
               'side': 'sell',
               'amount': amount,
               'price': price,
               'cost': amount * price,
               'fees': 0,  # Will be calculated when filled
               'status': 'open',
               'timestamp': get_timestamp()
           }
           
           self.orders.append(order)
           self.pending_orders.append(order['id'])
           
           logger.trade(
               action="SELL_LIMIT",
               symbol=symbol,
               price=price,
               amount=amount,
               mode="SIMULATION"
           )
           
           self._save_simulation_state()
           return order
           
       except Exception as e:
           logger.error(f"Error in simulated limit sell: {str(e)}")
           return None
   
    def simulate_conditional_sell(self, symbol: str, amount: float, target_price: float) -> Optional[Dict]:
       """Simulate conditional sell order"""
       return self.simulate_limit_sell(symbol, amount, target_price)
   
    def get_order_status(self, order_id: str, symbol: str = None) -> Optional[Dict]:
       """Get simulated order status"""
       for order in self.orders:
           if order['id'] == order_id:
               return order
       return None
   
    def cancel_order(self, order_id: str, symbol: str = None) -> bool:
       """Cancel simulated order"""
       try:
           for order in self.orders:
               if order['id'] == order_id and order['status'] == 'open':
                   order['status'] = 'cancelled'
                   if order_id in self.pending_orders:
                       self.pending_orders.remove(order_id)
                   
                   logger.info(f"Simulated order cancelled: {order_id}")
                   self._save_simulation_state()
                   return True
           return False
       except Exception as e:
           logger.error(f"Error cancelling simulated order: {str(e)}")
           return False
   
    def get_open_orders(self, symbol: str = None) -> List[Dict]:
       """Get open simulated orders"""
       return [order for order in self.orders if order['status'] == 'open']
   
    def calculate_average_fill_price(self, order_id: str, symbol: str = None) -> Optional[float]:
       """Get average fill price for simulated order"""
       order = self.get_order_status(order_id, symbol)
       if order and order['status'] == 'closed':
           return order['price']
       return None
   
    def check_and_fill_orders(self):
       """Check if any open orders should be filled"""
       current_price = self.get_current_price()
       if not current_price:
           return
       
       filled_orders = []
       
       for order_id in list(self.pending_orders):
           order = self.get_order_status(order_id)
           if not order or order['status'] != 'open':
               continue
           
           should_fill = False
           
           # Check limit buy orders
           if order['type'] == 'limit' and order['side'] == 'buy':
               if current_price <= order['price']:
                   should_fill = True
           
           # Check limit sell orders
           elif order['type'] == 'limit' and order['side'] == 'sell':
               if current_price >= order['price']:
                   should_fill = True
           
           if should_fill:
               self._fill_order(order, current_price)
               filled_orders.append(order['id'])
       
       if filled_orders:
           logger.info(f"Filled {len(filled_orders)} orders in simulation")
           self._save_simulation_state()
   
    def _fill_order(self, order: Dict, fill_price: float):
       """Fill an open order"""
       try:
           if order['side'] == 'buy':
               # Calculate fees
               gross_cost = order['amount'] * fill_price
               fees = self._calculate_fees(gross_cost, 'maker')  # Limit orders get maker fees
               total_cost = gross_cost + fees
               
               # Check if we still have enough balance
               if self.balances['USDT'] >= total_cost:
                   # Execute the trade
                   self.balances['USDT'] -= total_cost
                   self.balances['BTC'] += order['amount']
                   
                   # Update order
                   order['status'] = 'closed'
                   order['price'] = fill_price  # Actual fill price
                   order['cost'] = gross_cost
                   order['fees'] = fees
                   order['filled_timestamp'] = get_timestamp()
                   
                   self.trades.append(order.copy())
                   
                   if order['id'] in self.pending_orders:
                       self.pending_orders.remove(order['id'])
           
           elif order['side'] == 'sell':
               # Calculate fees
               gross_proceeds = order['amount'] * fill_price
               fees = self._calculate_fees(gross_proceeds, 'maker')  # Limit orders get maker fees
               net_proceeds = gross_proceeds - fees
               
               # Check if we still have enough BTC
               if self.balances['BTC'] >= order['amount']:
                   # Execute the trade
                   self.balances['BTC'] -= order['amount']
                   self.balances['USDT'] += net_proceeds
                   
                   # Update order
                   order['status'] = 'closed'
                   order['price'] = fill_price  # Actual fill price
                   order['cost'] = gross_proceeds
                   order['fees'] = fees
                   order['filled_timestamp'] = get_timestamp()
                   
                   self.trades.append(order.copy())
                   
                   if order['id'] in self.pending_orders:
                       self.pending_orders.remove(order['id'])
                       
       except Exception as e:
           logger.error(f"Error filling simulated order: {str(e)}")
   
    def _calculate_fees(self, amount: float, fee_type: str = 'taker') -> float:
       """Calculate trading fees"""
       fee_rates = {
           'maker': 0.001,  # 0.1%
           'taker': 0.001   # 0.1%
       }
       return amount * fee_rates.get(fee_type, 0.001)
   
    def get_total_value(self) -> float:
       """Get total portfolio value in USDT"""
       current_price = self.get_current_price()
       if not current_price:
           return self.balances['USDT']
       
       btc_value = self.balances['BTC'] * current_price
       return self.balances['USDT'] + btc_value
   
    def get_profit_loss(self) -> Dict[str, float]:
       """Calculate profit/loss"""
       total_value = self.get_total_value()
       absolute_pnl = total_value - self.initial_balance
       percentage_pnl = (absolute_pnl / self.initial_balance) * 100
       
       return {
           'initial_balance': self.initial_balance,
           'current_value': total_value,
           'absolute_pnl': absolute_pnl,
           'percentage_pnl': percentage_pnl
       }
   
    def get_trade_history(self) -> List[Dict]:
       """Get simulated trade history"""
       return self.trades.copy()
   
    def get_pending_orders_summary(self) -> Dict[str, Any]:
       """Get summary of pending orders"""
       open_orders = self.get_open_orders()
       buy_orders = [o for o in open_orders if o['side'] == 'buy']
       sell_orders = [o for o in open_orders if o['side'] == 'sell']
       
       return {
           'total_open': len(open_orders),
           'buy_orders': len(buy_orders),
           'sell_orders': len(sell_orders),
           'total_buy_value': sum(o['cost'] for o in buy_orders),
           'total_sell_value': sum(o['cost'] for o in sell_orders)
       }
   
    def reset_simulation(self):
       """Reset simulation to initial state"""
       self.balances = {
           'USDT': self.initial_balance,
           'BTC': 0.0
       }
       self.orders = []
       self.trades = []
       self.positions = []
       self.pending_orders = []
       self.order_id_counter = 1
       
       self._save_simulation_state()
       logger.info("Simulation reset to initial state")

# Global simulator instance
simulator = TradingSimulator()