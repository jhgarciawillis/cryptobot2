import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from kucoin import KuCoinClient
from simulator import Simulator

@dataclass
class Position:
    buy_price: float
    size: float
    timestamp: float
    
    def get_profit_at_price(self, current_price: float) -> float:
        """Calculate profit percentage at given price"""
        return ((current_price - self.buy_price) / self.buy_price) * 100
    
    def is_profitable(self, current_price: float, target_margin: float) -> bool:
        """Check if position is profitable"""
        required_price = self.buy_price * (1 + target_margin + 0.002)  # +0.2% for fees
        return current_price >= required_price

class TradingBot:
    def __init__(self, api_key: str = None, api_secret: str = None, api_passphrase: str = None, 
                 sandbox: bool = True, simulation: bool = True, initial_balance: float = 50):
        
        # Configuration
        self.simulation = simulation
        self.symbol = "BTC-USDT"
        self.profit_margin = 0.005  # 0.5% target profit
        self.buy_trigger_percent = 0.5  # 0.5% price drop triggers buy
        self.min_trade_amount = 10  # Minimum $10 per trade
        
        # Client setup
        if simulation:
            self.client = Simulator(initial_balance)
        else:
            if not all([api_key, api_secret, api_passphrase]):
                raise ValueError("API credentials required for live trading")
            self.client = KuCoinClient(api_key, api_secret, api_passphrase, sandbox)
        
        # Bot state
        self.status = "stopped"
        self.running = False
        self.positions: List[Position] = []
        self.thread = None
        self.last_price = None
        self.last_check_time = None
        self.pending_exit = False
        
        print(f"Bot initialized - Mode: {'Simulation' if simulation else 'Live'}")
    
    def _calculate_required_sell_price(self, buy_price: float) -> float:
        """Calculate required sell price for target profit after fees"""
        # Account for buy fee (0.1%) and sell fee (0.1%) plus desired profit
        total_margin = self.profit_margin + 0.002  # Add 0.2% for round-trip fees
        return buy_price * (1 + total_margin)
    
    def _should_buy_more(self, current_price: float) -> bool:
        """Check if we should buy more based on price drop"""
        if not self.positions:
            return True  # First buy
        
        last_buy_price = max(pos.buy_price for pos in self.positions)
        trigger_price = last_buy_price * (1 - self.buy_trigger_percent / 100)
        return current_price <= trigger_price
    
    def _get_available_funds(self) -> float:
        """Get available USDT for trading"""
        return max(0, self.client.get_usdt_balance() - 5)  # Keep $5 buffer
    
    def _execute_buy(self, current_price: float):
        """Execute buy order"""
        available_funds = self._get_available_funds()
        if available_funds < self.min_trade_amount:
            return
        
        # Use 90% of available funds for this buy
        trade_amount = min(available_funds * 0.9, available_funds - 1)
        
        print(f"Executing buy: ${trade_amount:.2f} at ${current_price:.2f}")
        
        order_id = self.client.place_market_buy_order(self.symbol, trade_amount)
        if order_id:
            # Add position (approximate size for immediate tracking)
            btc_size = trade_amount / current_price * 0.999  # Account for fees
            position = Position(current_price, btc_size, time.time())
            self.positions.append(position)
            print(f"Buy executed: {btc_size:.6f} BTC")
    
    def _execute_sell(self, position: Position, current_price: float):
        """Execute sell order for a position"""
        print(f"Executing sell: {position.size:.6f} BTC at ${current_price:.2f}")
        
        order_id = self.client.place_market_sell_order(self.symbol, position.size)
        if order_id:
            profit_pct = position.get_profit_at_price(current_price)
            print(f"Sell executed: {position.size:.6f} BTC - Profit: {profit_pct:+.2f}%")
            self.positions.remove(position)
    
    def _check_sell_opportunities(self, current_price: float):
        """Check for profitable sell opportunities"""
        for position in self.positions[:]:  # Copy list to avoid modification during iteration
            if position.is_profitable(current_price, self.profit_margin):
                self._execute_sell(position, current_price)
    
    def _trading_loop(self):
        """Main trading loop"""
        print("Trading loop started")
        
        while self.running:
            try:
                # Get current price
                current_price = self.client.get_current_price(self.symbol)
                if not current_price:
                    time.sleep(5)
                    continue
                
                self.last_price = current_price
                self.last_check_time = datetime.now()
                
                if self.pending_exit:
                    # Check if all positions can be sold profitably
                    profitable_positions = [
                        pos for pos in self.positions 
                        if pos.is_profitable(current_price, self.profit_margin)
                    ]
                    
                    if len(profitable_positions) == len(self.positions):
                        # All positions profitable - sell everything
                        for position in self.positions[:]:
                            self._execute_sell(position, current_price)
                        break
                    else:
                        # Sell profitable positions
                        for position in profitable_positions:
                            self._execute_sell(position, current_price)
                else:
                    # Normal trading
                    # Check for sell opportunities
                    self._check_sell_opportunities(current_price)
                    
                    # Check for buy opportunities
                    if self._should_buy_more(current_price):
                        self._execute_buy(current_price)
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                print(f"Error in trading loop: {e}")
                time.sleep(10)
        
        self.status = "stopped"
        print("Trading loop ended")
    
    def start(self) -> bool:
        """Start the trading bot"""
        if self.running:
            return False
        
        if not self.client.is_connected:
            print("Client not connected")
            return False
        
        # Check minimum balance
        balance = self.client.get_usdt_balance()
        if balance < self.min_trade_amount:
            print(f"Insufficient balance: ${balance:.2f}")
            return False
        
        self.running = True
        self.status = "running"
        self.pending_exit = False
        
        self.thread = threading.Thread(target=self._trading_loop, daemon=True)
        self.thread.start()
        
        print("Trading bot started")
        return True
    
    def stop(self):
        """Stop trading and look for profitable exit"""
        if not self.running:
            return
        
        print("Stop signal received - looking for profitable exit...")
        self.pending_exit = True
    
    def force_stop(self):
        """Force stop immediately"""
        print("Force stopping...")
        self.running = False
        self.status = "stopped"
        if self.thread:
            self.thread.join(timeout=5)
    
    def set_profit_margin(self, margin_percent: float) -> bool:
        """Set profit margin (percentage)"""
        if 0.001 <= margin_percent <= 5.0:
            self.profit_margin = margin_percent / 100
            print(f"Profit margin set to {margin_percent:.3f}%")
            return True
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get bot status"""
        current_price = self.last_price or self.client.get_current_price(self.symbol)
        
        # Calculate P&L
        unrealized_pnl = 0.0
        total_cost = 0.0
        if self.positions and current_price:
            for pos in self.positions:
                cost = pos.buy_price * pos.size
                value = current_price * pos.size
                total_cost += cost
                unrealized_pnl += (value - cost)
        
        return {
            "status": self.status,
            "pending_exit": self.pending_exit,
            "mode": "simulation" if self.simulation else "live",
            "current_price": current_price,
            "last_check": self.last_check_time.isoformat() if self.last_check_time else None,
            "balances": {
                "USDT": self.client.get_usdt_balance(),
                "BTC": self.client.get_btc_balance()
            },
            "positions": {
                "count": len(self.positions),
                "total_btc": sum(pos.size for pos in self.positions),
                "avg_buy_price": total_cost / sum(pos.size for pos in self.positions) if self.positions else 0
            },
            "pnl": {
                "unrealized_usd": unrealized_pnl,
                "unrealized_percent": (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0
            },
            "profit_margin": self.profit_margin * 100,
            "symbol": self.symbol
        }
    
    def get_trade_history(self) -> List[Dict]:
        """Get trade history"""
        if hasattr(self.client, 'get_trade_history'):
            return self.client.get_trade_history()
        return []
    
    def reset(self):
        """Reset bot state"""
        self.force_stop()
        self.positions = []
        if hasattr(self.client, 'reset'):
            self.client.reset()
        print("Bot reset")