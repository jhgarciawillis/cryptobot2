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
    order_id: str = None
    sell_order_id: str = None
    
    def get_profit_at_price(self, current_price: float) -> float:
        """Calculate profit percentage at given price"""
        return ((current_price - self.buy_price) / self.buy_price) * 100
    
    def calculate_required_sell_price(self, profit_margin: float) -> float:
        """Calculate required sell price for target profit after fees"""
        # Buy fee: 0.1% on USDT spent (maker fee for limit orders)
        # Effective buy price after fees
        effective_buy_price = self.buy_price / (1 - 0.001)
        
        # Sell fee: 0.1% on USDT received (maker fee for limit orders)
        # Required sell price accounting for sell fee and desired profit
        required_sell_price = (effective_buy_price * (1 + profit_margin)) / (1 - 0.001)
        
        return required_sell_price
    
    def is_profitable(self, current_price: float, profit_margin: float) -> bool:
        """Check if position is profitable at current price"""
        required_price = self.calculate_required_sell_price(profit_margin)
        return current_price >= required_price

class TradingBot:
    def __init__(self, api_key: str = None, api_secret: str = None, api_passphrase: str = None, 
                 sandbox: bool = True, simulation: bool = True, initial_balance: float = 50):
        
        # Configuration with enforced minimums
        self.simulation = simulation
        self.symbol = "BTC-USDT"
        self.MINIMUM_PROFIT_MARGIN = 0.005  # 0.5% absolute minimum
        self.profit_margin = 0.005  # 0.5% default target profit
        self.buy_trigger_percent = 0.5  # 0.5% price drop triggers buy
        self.min_trade_amount = 10  # Minimum $10 per trade
        self.max_position_count = 10  # Maximum number of positions
        
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
        self.order_check_interval = 5  # Check orders every 5 seconds
        
        print(f"Bot initialized - Mode: {'Simulation' if simulation else 'Live'}")
        print(f"Target profit margin: {self.profit_margin*100:.1f}% (minimum: {self.MINIMUM_PROFIT_MARGIN*100:.1f}%)")
    
    def _get_last_buy_price(self) -> Optional[float]:
        """Get the price of the most recent purchase"""
        if not self.positions:
            return None
        return max(pos.buy_price for pos in self.positions)
    
    def _should_buy_more(self, current_price: float) -> bool:
        """Check if we should buy more based on price drop"""
        if len(self.positions) >= self.max_position_count:
            print(f"Maximum positions ({self.max_position_count}) reached")
            return False
        
        if not self.positions:
            return True  # First buy
        
        last_buy_price = self._get_last_buy_price()
        if not last_buy_price:
            return True
        
        trigger_price = last_buy_price * (1 - self.buy_trigger_percent / 100)
        should_buy = current_price <= trigger_price
        
        if should_buy:
            print(f"Buy trigger hit: ${current_price:.2f} <= ${trigger_price:.2f}")
        
        return should_buy
    
    def _get_available_funds(self) -> float:
        """Get available USDT for trading"""
        balance = self.client.get_usdt_balance()
        return max(0, balance - 5)  # Keep $5 buffer
    
    def _calculate_trade_amount(self) -> float:
        """Calculate amount for next trade"""
        available_funds = self._get_available_funds()
        
        if available_funds < self.min_trade_amount:
            return 0
        
        # Use progressive position sizing - larger positions as price drops more
        position_count = len(self.positions)
        if position_count == 0:
            # First position: use 30% of available funds
            return min(available_funds * 0.3, available_funds - 1)
        else:
            # Subsequent positions: use 20% of available funds
            return min(available_funds * 0.2, available_funds - 1)
    
    def _execute_smart_buy(self, current_price: float):
        """Execute smart buy using limit orders"""
        trade_amount = self._calculate_trade_amount()
        if trade_amount < self.min_trade_amount:
            print(f"Insufficient funds for trade: ${trade_amount:.2f}")
            return
        
        print(f"Executing smart buy: ${trade_amount:.2f} worth at market ~${current_price:.2f}")
        
        # Place smart limit buy order
        order_id = self.client.place_smart_limit_buy_order(self.symbol, trade_amount)
        if order_id:
            print(f"Smart buy order placed: {order_id}")
        else:
            print("Failed to place smart buy order")
    
    def _execute_smart_sell(self, position: Position, current_price: float):
        """Execute smart sell using limit orders"""
        target_price = position.calculate_required_sell_price(self.profit_margin)
        
        print(f"Executing smart sell: {position.size:.6f} BTC, target: ${target_price:.2f}")
        
        # Place smart limit sell order
        order_id = self.client.place_smart_limit_sell_order(self.symbol, position.size, target_price)
        if order_id:
            position.sell_order_id = order_id
            print(f"Smart sell order placed: {order_id}")
        else:
            print("Failed to place smart sell order")
    
    def _process_filled_orders(self):
        """Process orders that have been filled"""
        filled_orders = self.client.check_filled_orders()
        
        for order_info in filled_orders:
            if order_info['type'] == 'buy' and order_info['status'] != 'cancelled':
                # Buy order filled - create new position
                position = Position(
                    buy_price=order_info['actual_price'],
                    size=order_info['filled_size'],
                    timestamp=time.time(),
                    order_id=order_info['order_id']
                )
                self.positions.append(position)
                
                print(f"✅ Buy filled: {position.size:.6f} BTC @ ${position.buy_price:.2f}")
                print(f"✅ Position created: {len(self.positions)} total positions")
                
                # Immediately place sell order for this position
                self._execute_smart_sell(position, order_info['actual_price'])
                
            elif order_info['type'] == 'sell' and order_info['status'] != 'cancelled':
                # Sell order filled - remove position
                sell_order_id = order_info['order_id']
                position_to_remove = None
                
                for position in self.positions:
                    if position.sell_order_id == sell_order_id:
                        position_to_remove = position
                        break
                
                if position_to_remove:
                    profit_pct = position_to_remove.get_profit_at_price(order_info['actual_price'])
                    profit_usd = (order_info['actual_price'] - position_to_remove.buy_price) * position_to_remove.size
                    
                    print(f"✅ Sell filled: {position_to_remove.size:.6f} BTC @ ${order_info['actual_price']:.2f}")
                    print(f"   Profit: ${profit_usd:.2f} ({profit_pct:+.2f}%)")
                    
                    self.positions.remove(position_to_remove)
                    print(f"✅ Position removed: {len(self.positions)} remaining positions")
    
    def _check_exit_opportunities(self, current_price: float):
        """Check for exit opportunities when stopping"""
        if not self.pending_exit:
            return False
        
        profitable_positions = [
            pos for pos in self.positions 
            if pos.is_profitable(current_price, self.profit_margin)
        ]
        
        total_positions = len(self.positions)
        profitable_count = len(profitable_positions)
        
        print(f"Exit check: {profitable_count}/{total_positions} positions profitable")
        
        if profitable_count == total_positions and total_positions > 0:
            # All positions are profitable - exit complete
            print("🎉 All positions profitable! Bot can exit safely.")
            return True
        elif profitable_count > 0:
            # Some positions profitable - sell them
            for position in profitable_positions:
                if not position.sell_order_id:  # Only if not already selling
                    self._execute_smart_sell(position, current_price)
        
        return False
    
    def _trading_loop(self):
        """Main trading loop with smart order management"""
        print("🚀 Smart trading loop started")
        
        while self.running:
            try:
                # Process filled orders first
                self._process_filled_orders()
                
                # Get current price
                current_price = self.client.get_current_price(self.symbol)
                if not current_price:
                    print("⚠️ Unable to fetch current price, retrying...")
                    time.sleep(10)
                    continue
                
                self.last_price = current_price
                self.last_check_time = datetime.now()
                
                # Handle exit logic
                if self.pending_exit:
                    if self._check_exit_opportunities(current_price):
                        print("✅ Safe exit completed")
                        break
                else:
                    # Normal trading logic
                    # Check for buy opportunities
                    if self._should_buy_more(current_price):
                        self._execute_smart_buy(current_price)
                    
                    # Check and fill simulation orders if needed
                    if self.simulation:
                        self.client.check_and_fill_orders()
                
                # Sleep before next iteration
                time.sleep(self.order_check_interval)
                
            except Exception as e:
                print(f"❌ Error in trading loop: {e}")
                time.sleep(10)
        
        self.status = "stopped"
        print("⏹️ Trading loop ended")
    
    def start(self) -> bool:
        """Start the trading bot"""
        if self.running:
            print("⚠️ Bot is already running")
            return False
        
        if not self.client.is_connected:
            print("❌ Client not connected")
            return False
        
        # Check minimum balance
        balance = self.client.get_usdt_balance()
        if balance < self.min_trade_amount:
            print(f"❌ Insufficient balance: ${balance:.2f}")
            return False
        
        self.running = True
        self.status = "running"
        self.pending_exit = False
        
        # Start trading thread
        self.thread = threading.Thread(target=self._trading_loop, daemon=True)
        self.thread.start()
        
        print(f"✅ Trading bot started with ${balance:.2f}")
        return True
    
    def stop(self):
        """Stop trading and look for profitable exit"""
        if not self.running:
            print("⚠️ Bot is not running")
            return
        
        print("🛑 Stop signal received - looking for profitable exit...")
        self.pending_exit = True
    
    def force_stop(self):
        """Force stop immediately"""
        print("🚨 Force stopping...")
        self.running = False
        self.status = "stopped"
        
        # Cancel all pending orders
        try:
            self.client.cancel_all_orders(self.symbol)
        except Exception as e:
            print(f"Error cancelling orders: {e}")
        
        if self.thread:
            self.thread.join(timeout=10)
        
        print("⏹️ Bot force stopped")
    
    def set_profit_margin(self, margin_percent: float) -> bool:
        """Set profit margin with enforced minimum"""
        if margin_percent < self.MINIMUM_PROFIT_MARGIN * 100:
            print(f"❌ REJECTED: Minimum profit margin is {self.MINIMUM_PROFIT_MARGIN * 100:.1f}% for guaranteed profits")
            return False
        
        if margin_percent > 5.0:
            print(f"❌ REJECTED: Maximum profit margin is 5.0%")
            return False
        
        old_margin = self.profit_margin * 100
        self.profit_margin = margin_percent / 100
        print(f"📊 Profit margin updated: {old_margin:.1f}% → {margin_percent:.1f}%")
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive bot status"""
        current_price = self.last_price or self.client.get_current_price(self.symbol)
        
        # Calculate position metrics
        total_btc = sum(pos.size for pos in self.positions)
        total_cost = sum(pos.buy_price * pos.size for pos in self.positions)
        avg_buy_price = total_cost / total_btc if total_btc > 0 else 0
        
        # Calculate P&L
        unrealized_pnl_usd = 0.0
        current_value = 0.0
        profitable_positions = 0
        
        if self.positions and current_price:
            for pos in self.positions:
                pos_value = pos.size * current_price
                pos_cost = pos.size * pos.buy_price
                current_value += pos_value
                unrealized_pnl_usd += (pos_value - pos_cost)
                
                if pos.is_profitable(current_price, self.profit_margin):
                    profitable_positions += 1
        
        unrealized_pnl_percent = (unrealized_pnl_usd / total_cost * 100) if total_cost > 0 else 0
        
        # Calculate total portfolio value for simulation
        total_portfolio_value = 0
        initial_value = 0
        if self.simulation:
            total_portfolio_value = self.client.get_total_value()
            initial_value = getattr(self.client, 'initial_balance', 50)
        
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
                "total_btc": total_btc,
                "avg_buy_price": avg_buy_price,
                "profitable_count": profitable_positions,
                "max_positions": self.max_position_count
            },
            "pnl": {
                "unrealized_usd": unrealized_pnl_usd,
                "unrealized_percent": unrealized_pnl_percent,
                "current_value": current_value,
                "total_cost": total_cost
            },
            "portfolio": {
                "total_value": total_portfolio_value,
                "initial_value": initial_value,
                "total_return": total_portfolio_value - initial_value if self.simulation else 0
            },
            "settings": {
                "profit_margin": self.profit_margin * 100,
                "minimum_margin": self.MINIMUM_PROFIT_MARGIN * 100,
                "buy_trigger_percent": self.buy_trigger_percent,
                "min_trade_amount": self.min_trade_amount
            },
            "symbol": self.symbol
        }
    
    def get_positions_detail(self) -> List[Dict]:
        """Get detailed position information"""
        print(f"DEBUG: Bot has {len(self.positions)} positions")  # Debug print
        current_price = self.last_price or self.client.get_current_price(self.symbol)
        position_details = []
        
        for i, pos in enumerate(self.positions, 1):
            target_price = pos.calculate_required_sell_price(self.profit_margin)
            profit_pct = pos.get_profit_at_price(current_price) if current_price else 0
            profit_usd = (current_price - pos.buy_price) * pos.size if current_price else 0
            is_profitable = pos.is_profitable(current_price, self.profit_margin) if current_price else False
            
            position_details.append({
                "position_id": i,
                "size": pos.size,
                "buy_price": pos.buy_price,
                "target_price": target_price,
                "current_profit_usd": profit_usd,
                "current_profit_percent": profit_pct,
                "is_profitable": is_profitable,
                "buy_timestamp": pos.timestamp,
                "order_id": pos.order_id,
                "sell_order_id": pos.sell_order_id
            })
        
        print(f"DEBUG: Returning {len(position_details)} position details")  # Debug print
        return position_details
    
    def get_trade_history(self) -> List[Dict]:
        """Get trade history"""
        if hasattr(self.client, 'get_trade_history'):
            trades = self.client.get_trade_history()
            print(f"DEBUG: Retrieved {len(trades)} trades from client")  # Debug print
            return trades
        return []
    
    def get_open_orders(self) -> List[Dict]:
        """Get open orders"""
        return self.client.get_open_orders(self.symbol)
    
    def cancel_all_orders(self) -> bool:
        """Cancel all open orders"""
        try:
            success = self.client.cancel_all_orders(self.symbol)
            if success:
                # Clear sell order IDs from positions
                for position in self.positions:
                    position.sell_order_id = None
                print("🗑️ All orders cancelled")
            return success
        except Exception as e:
            print(f"❌ Error cancelling orders: {e}")
            return False
    
    def reset(self):
        """Reset bot state"""
        self.force_stop()
        self.positions = []
        
        if hasattr(self.client, 'reset'):
            self.client.reset()
        
        print("🔄 Bot reset complete")