import time
import requests
from typing import Dict, Optional, List
from dataclasses import dataclass

@dataclass
class SimulatedTrade:
    id: str
    symbol: str
    side: str
    size: float
    price: float
    funds: float
    fee: float
    timestamp: float

@dataclass
class SimulatedOrder:
    id: str
    symbol: str
    side: str
    size: float
    price: float
    status: str  # 'active', 'filled', 'cancelled'
    timestamp: float
    filled_size: float = 0.0
    filled_funds: float = 0.0

class Simulator:
    def __init__(self, initial_balance: float = 50):
        self.initial_balance = initial_balance
        self.balances = {
            "USDT": initial_balance,
            "BTC": 0.0
        }
        self.trades: List[SimulatedTrade] = []
        self.orders: List[SimulatedOrder] = []
        self.order_counter = 1
        self.is_connected = True
        self.pending_orders = {}  # Track pending orders like real client
    
    def _get_real_price(self, symbol: str = "BTC-USDT") -> Optional[float]:
        """Get real market price from KuCoin public API"""
        try:
            url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "200000":
                    return float(data["data"]["price"])
        except:
            pass
        return 50000.0  # Fallback price
    
    def _get_real_orderbook(self, symbol: str = "BTC-USDT") -> Optional[Dict]:
        """Get real order book from KuCoin public API"""
        try:
            url = f"https://api.kucoin.com/api/v3/market/orderbook/level2?symbol={symbol}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "200000":
                    result = data["data"]
                    return {
                        'bids': [[float(bid[0]), float(bid[1])] for bid in result.get('bids', [])[:20]],
                        'asks': [[float(ask[0]), float(ask[1])] for ask in result.get('asks', [])[:20]],
                        'timestamp': result.get('time')
                    }
        except:
            pass
        
        # Fallback synthetic orderbook
        price = self._get_real_price(symbol)
        return {
            'bids': [[price * 0.999, 1.0], [price * 0.998, 0.5]],
            'asks': [[price * 1.001, 1.0], [price * 1.002, 0.5]],
            'timestamp': int(time.time() * 1000)
        }
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        order_id = f"SIM_{self.order_counter:06d}"
        self.order_counter += 1
        return order_id
    
    def _calculate_fee(self, amount: float, fee_rate: float = 0.001) -> float:
        """Calculate trading fee"""
        return amount * fee_rate
    
    def get_current_price(self, symbol: str = "BTC-USDT") -> Optional[float]:
        """Get current market price"""
        return self._get_real_price(symbol)
    
    def get_order_book(self, symbol: str = "BTC-USDT", depth: int = 20) -> Optional[Dict]:
        """Get order book"""
        return self._get_real_orderbook(symbol)
    
    def get_bid_ask_spread(self, symbol: str = "BTC-USDT") -> Optional[Dict]:
        """Get current bid/ask prices and spread"""
        orderbook = self.get_order_book(symbol, 1)
        if orderbook and orderbook['bids'] and orderbook['asks']:
            bid = orderbook['bids'][0][0]
            ask = orderbook['asks'][0][0]
            spread = ask - bid
            spread_percent = (spread / bid) * 100
            
            return {
                'bid': bid,
                'ask': ask,
                'spread': spread,
                'spread_percent': spread_percent
            }
        return None
    
    def calculate_smart_buy_price(self, symbol: str = "BTC-USDT") -> Optional[float]:
        """Calculate smart buy price based on order book"""
        spread_info = self.get_bid_ask_spread(symbol)
        if not spread_info:
            current_price = self.get_current_price(symbol)
            return current_price * 0.999 if current_price else None
        
        bid = spread_info['bid']
        ask = spread_info['ask']
        spread_percent = spread_info['spread_percent']
        
        if spread_percent < 0.1:
            return bid + 0.01
        else:
            return bid + (ask - bid) * 0.3
    
    def calculate_smart_sell_price(self, symbol: str = "BTC-USDT") -> Optional[float]:
        """Calculate smart sell price based on order book"""
        spread_info = self.get_bid_ask_spread(symbol)
        if not spread_info:
            current_price = self.get_current_price(symbol)
            return current_price * 1.001 if current_price else None
        
        bid = spread_info['bid']
        ask = spread_info['ask']
        spread_percent = spread_info['spread_percent']
        
        if spread_percent < 0.1:
            return ask - 0.01
        else:
            return ask - (ask - bid) * 0.3
    
    def get_balance(self, currency: str = "USDT") -> float:
        """Get simulated balance"""
        return self.balances.get(currency, 0.0)
    
    def get_usdt_balance(self) -> float:
        """Get USDT balance"""
        return self.get_balance("USDT")
    
    def get_btc_balance(self) -> float:
        """Get BTC balance"""
        return self.get_balance("BTC")
    
    def place_smart_limit_buy_order(self, symbol: str, amount_usdt: float) -> Optional[str]:
        """Simulate smart limit buy order"""
        smart_price = self.calculate_smart_buy_price(symbol)
        if not smart_price or self.balances["USDT"] < amount_usdt:
            return None
        
        size = round(amount_usdt / smart_price, 8)
        order_id = self._generate_order_id()
        
        # Create order
        order = SimulatedOrder(
            id=order_id,
            symbol=symbol,
            side="buy",
            size=size,
            price=smart_price,
            status="active",
            timestamp=time.time()
        )
        
        self.orders.append(order)
        self.pending_orders[order_id] = {
            'type': 'buy',
            'symbol': symbol,
            'size': size,
            'price': smart_price,
            'amount_usdt': amount_usdt,
            'timestamp': time.time()
        }
        
        print(f"Simulated smart buy order: {size:.6f} {symbol} @ ${smart_price:.2f}")
        
        # In simulation, check if order should fill immediately
        current_price = self.get_current_price(symbol)
        if current_price and current_price <= smart_price:
            self._fill_buy_order(order, current_price)
        
        return order_id
    
    def place_smart_limit_sell_order(self, symbol: str, size: float, target_price: float) -> Optional[str]:
        """Simulate smart limit sell order"""
        if self.balances["BTC"] < size:
            return None
        
        smart_price = self.calculate_smart_sell_price(symbol)
        sell_price = max(target_price, smart_price) if smart_price else target_price
        
        order_id = self._generate_order_id()
        
        # Create order
        order = SimulatedOrder(
            id=order_id,
            symbol=symbol,
            side="sell",
            size=size,
            price=sell_price,
            status="active",
            timestamp=time.time()
        )
        
        self.orders.append(order)
        self.pending_orders[order_id] = {
            'type': 'sell',
            'symbol': symbol,
            'size': size,
            'price': sell_price,
            'target_price': target_price,
            'timestamp': time.time()
        }
        
        print(f"Simulated smart sell order: {size:.6f} {symbol} @ ${sell_price:.2f}")
        
        # In simulation, check if order should fill immediately
        current_price = self.get_current_price(symbol)
        if current_price and current_price >= sell_price:
            self._fill_sell_order(order, current_price)
        
        return order_id
    
    def _fill_buy_order(self, order: SimulatedOrder, fill_price: float):
        """Fill a buy order"""
        if order.status != "active":
            return
        
        cost = order.size * fill_price
        fee = self._calculate_fee(cost)
        net_cost = cost + fee
        
        if self.balances["USDT"] >= net_cost:
            # Execute trade
            self.balances["USDT"] -= net_cost
            self.balances["BTC"] += order.size
            
            # Update order
            order.status = "filled"
            order.filled_size = order.size
            order.filled_funds = cost
            
            # Record trade
            trade = SimulatedTrade(
                id=order.id,
                symbol=order.symbol,
                side=order.side,
                size=order.size,
                price=fill_price,
                funds=cost,
                fee=fee,
                timestamp=time.time()
            )
            self.trades.append(trade)
            
            print(f"Buy order filled: {order.size:.6f} @ ${fill_price:.2f}")
    
    def _fill_sell_order(self, order: SimulatedOrder, fill_price: float):
        """Fill a sell order"""
        if order.status != "active" or self.balances["BTC"] < order.size:
            return
        
        gross_proceeds = order.size * fill_price
        fee = self._calculate_fee(gross_proceeds)
        net_proceeds = gross_proceeds - fee
        
        # Execute trade
        self.balances["BTC"] -= order.size
        self.balances["USDT"] += net_proceeds
        
        # Update order
        order.status = "filled"
        order.filled_size = order.size
        order.filled_funds = gross_proceeds
        
        # Record trade
        trade = SimulatedTrade(
            id=order.id,
            symbol=order.symbol,
            side=order.side,
            size=order.size,
            price=fill_price,
            funds=gross_proceeds,
            fee=fee,
            timestamp=time.time()
        )
        self.trades.append(trade)
        
        print(f"Sell order filled: {order.size:.6f} @ ${fill_price:.2f}")
    
    def check_and_fill_orders(self):
        """Check if any pending orders should be filled"""
        current_price = self.get_current_price()
        if not current_price:
            return
        
        for order in self.orders:
            if order.status == "active":
                if order.side == "buy" and current_price <= order.price:
                    self._fill_buy_order(order, order.price)
                elif order.side == "sell" and current_price >= order.price:
                    self._fill_sell_order(order, order.price)
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get simulated order status"""
        for order in self.orders:
            if order.id == order_id:
                return {
                    "orderId": order.id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "size": str(order.size),
                    "price": str(order.price),
                    "status": order.status,
                    "isActive": order.status == "active",
                    "dealSize": str(order.filled_size),
                    "dealFunds": str(order.filled_funds),
                    "fee": str(self._calculate_fee(order.filled_funds) if order.filled_funds > 0 else 0)
                }
        return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel simulated order"""
        for order in self.orders:
            if order.id == order_id and order.status == "active":
                order.status = "cancelled"
                if order_id in self.pending_orders:
                    del self.pending_orders[order_id]
                print(f"Order cancelled: {order_id}")
                return True
        return False
    
    def get_open_orders(self, symbol: str = "BTC-USDT") -> List[Dict]:
        """Get open orders"""
        open_orders = []
        for order in self.orders:
            if order.status == "active" and order.symbol == symbol:
                open_orders.append({
                    "id": order.id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "size": str(order.size),
                    "price": str(order.price),
                    "status": "active"
                })
        return open_orders
    
    def check_filled_orders(self) -> List[Dict]:
        """Check which of our tracked orders have been filled"""
        filled_orders = []
        
        for order_id in list(self.pending_orders.keys()):
            order_status = self.get_order_status(order_id)
            
            if order_status and not order_status.get("isActive", True):
                order_info = self.pending_orders[order_id].copy()
                order_info['order_id'] = order_id
                order_info['status'] = order_status.get('status', 'unknown')
                order_info['filled_size'] = float(order_status.get('dealSize', 0))
                order_info['filled_funds'] = float(order_status.get('dealFunds', 0))
                order_info['actual_price'] = order_info['filled_funds'] / order_info['filled_size'] if order_info['filled_size'] > 0 else order_info['price']
                order_info['fee'] = float(order_status.get('fee', 0))
                
                filled_orders.append(order_info)
                del self.pending_orders[order_id]
        
        return filled_orders
    
    def get_trading_fees(self) -> Dict[str, float]:
        """Get trading fees"""
        return {'maker': 0.001, 'taker': 0.001}
    
    def cancel_all_orders(self, symbol: str = "BTC-USDT") -> bool:
        """Cancel all orders"""
        cancelled = 0
        for order in self.orders:
            if order.status == "active" and order.symbol == symbol:
                order.status = "cancelled"
                cancelled += 1
        
        self.pending_orders.clear()
        print(f"Cancelled {cancelled} orders")
        return True
    
    def get_trade_history(self) -> List[Dict]:
        """Get trade history"""
        return [
            {
                "id": trade.id,
                "symbol": trade.symbol,
                "side": trade.side,
                "size": trade.size,
                "price": trade.price,
                "funds": trade.funds,
                "fee": trade.fee,
                "timestamp": trade.timestamp
            }
            for trade in self.trades
        ]
    
    def get_total_value(self) -> float:
        """Get total portfolio value in USDT"""
        current_price = self.get_current_price()
        if not current_price:
            return self.balances["USDT"]
        
        btc_value = self.balances["BTC"] * current_price
        return self.balances["USDT"] + btc_value
    
    def reset(self, initial_balance: float = None):
        """Reset simulation"""
        if initial_balance is None:
            initial_balance = self.initial_balance
        
        self.initial_balance = initial_balance
        self.balances = {"USDT": initial_balance, "BTC": 0.0}
        self.trades = []
        self.orders = []
        self.pending_orders = {}
        self.order_counter = 1
        print(f"Simulation reset with ${initial_balance} initial balance")