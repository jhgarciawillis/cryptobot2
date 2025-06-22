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

class Simulator:
    def __init__(self, initial_balance: float = 50):
        self.balances = {
            "USDT": initial_balance,
            "BTC": 0.0
        }
        self.trades: List[SimulatedTrade] = []
        self.order_counter = 1
        self.is_connected = True
    
    def _get_real_price(self, symbol: str = "BTC-USDT") -> Optional[float]:
        """Get real market price from KuCoin public API"""
        try:
            url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "200000":
                    return float(data["data"]["price"])
        except:
            pass
        return 50000.0  # Fallback price
    
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
    
    def get_balance(self, currency: str = "USDT") -> float:
        """Get simulated balance"""
        return self.balances.get(currency, 0.0)
    
    def get_usdt_balance(self) -> float:
        """Get USDT balance"""
        return self.get_balance("USDT")
    
    def get_btc_balance(self) -> float:
        """Get BTC balance"""
        return self.get_balance("BTC")
    
    def place_market_buy_order(self, symbol: str, amount_usdt: float) -> Optional[str]:
        """Simulate market buy order"""
        current_price = self.get_current_price(symbol)
        if not current_price or self.balances["USDT"] < amount_usdt:
            return None
        
        fee = self._calculate_fee(amount_usdt)
        net_amount = amount_usdt - fee
        btc_received = net_amount / current_price
        
        # Update balances
        self.balances["USDT"] -= amount_usdt
        self.balances["BTC"] += btc_received
        
        # Record trade
        trade = SimulatedTrade(
            id=self._generate_order_id(),
            symbol=symbol,
            side="buy",
            size=btc_received,
            price=current_price,
            funds=amount_usdt,
            fee=fee,
            timestamp=time.time()
        )
        self.trades.append(trade)
        
        return trade.id
    
    def place_limit_buy_order(self, symbol: str, size: float, price: float) -> Optional[str]:
        """Simulate limit buy order (fills immediately if price is favorable)"""
        current_price = self.get_current_price(symbol)
        if not current_price:
            return None
        
        cost = size * price
        if self.balances["USDT"] < cost:
            return None
        
        # For simulation, fill immediately if limit price >= current price
        if price >= current_price:
            return self.place_market_buy_order(symbol, cost)
        
        # Otherwise, order would be pending (not implemented for simplicity)
        return self._generate_order_id()
    
    def place_market_sell_order(self, symbol: str, size: float) -> Optional[str]:
        """Simulate market sell order"""
        current_price = self.get_current_price(symbol)
        if not current_price or self.balances["BTC"] < size:
            return None
        
        gross_proceeds = size * current_price
        fee = self._calculate_fee(gross_proceeds)
        net_proceeds = gross_proceeds - fee
        
        # Update balances
        self.balances["BTC"] -= size
        self.balances["USDT"] += net_proceeds
        
        # Record trade
        trade = SimulatedTrade(
            id=self._generate_order_id(),
            symbol=symbol,
            side="sell",
            size=size,
            price=current_price,
            funds=gross_proceeds,
            fee=fee,
            timestamp=time.time()
        )
        self.trades.append(trade)
        
        return trade.id
    
    def place_limit_sell_order(self, symbol: str, size: float, price: float) -> Optional[str]:
        """Simulate limit sell order (fills immediately if price is favorable)"""
        current_price = self.get_current_price(symbol)
        if not current_price or self.balances["BTC"] < size:
            return None
        
        # For simulation, fill immediately if limit price <= current price
        if price <= current_price:
            return self.place_market_sell_order(symbol, size)
        
        # Otherwise, order would be pending (not implemented for simplicity)
        return self._generate_order_id()
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get simulated order status"""
        for trade in self.trades:
            if trade.id == order_id:
                return {
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "size": str(trade.size),
                    "price": str(trade.price),
                    "funds": str(trade.funds),
                    "fee": str(trade.fee),
                    "status": "done"
                }
        return {"id": order_id, "status": "active"}
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel simulated order"""
        return True  # Always succeeds in simulation
    
    def get_open_orders(self, symbol: str = "BTC-USDT") -> list:
        """Get open orders (always empty in simplified simulation)"""
        return []
    
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
    
    def reset(self, initial_balance: float = 50):
        """Reset simulation"""
        self.balances = {"USDT": initial_balance, "BTC": 0.0}
        self.trades = []
        self.order_counter = 1