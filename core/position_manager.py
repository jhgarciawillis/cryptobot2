from typing import Dict, List, Optional
from datetime import datetime
from utils.helpers import save_json_file, load_json_file, get_timestamp, calculate_profit_percentage, is_profitable_exit
from utils.logger import logger

class Position:
    def __init__(self, symbol: str, buy_price: float, amount: float, timestamp: str = None):
        self.symbol = symbol
        self.buy_price = buy_price
        self.amount = amount
        self.timestamp = timestamp or get_timestamp()
        self.status = 'open'  # open, closed, partial
        self.exit_price = None
        self.exit_timestamp = None
        self.profit_loss = 0.0
    
    def to_dict(self) -> Dict:
        """Convert position to dictionary"""
        return {
            'symbol': self.symbol,
            'buy_price': self.buy_price,
            'amount': self.amount,
            'timestamp': self.timestamp,
            'status': self.status,
            'exit_price': self.exit_price,
            'exit_timestamp': self.exit_timestamp,
            'profit_loss': self.profit_loss
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Position':
        """Create position from dictionary"""
        position = cls(
            symbol=data['symbol'],
            buy_price=data['buy_price'],
            amount=data['amount'],
            timestamp=data['timestamp']
        )
        position.status = data.get('status', 'open')
        position.exit_price = data.get('exit_price')
        position.exit_timestamp = data.get('exit_timestamp')
        position.profit_loss = data.get('profit_loss', 0.0)
        return position
    
    def close_position(self, exit_price: float, amount_sold: float = None):
        """Close position or partial close"""
        if amount_sold is None:
            amount_sold = self.amount
        
        self.exit_price = exit_price
        self.exit_timestamp = get_timestamp()
        self.profit_loss = calculate_profit_percentage(self.buy_price, exit_price)
        
        if amount_sold >= self.amount:
            self.status = 'closed'
        else:
            self.status = 'partial'
            self.amount -= amount_sold
    
    def is_profitable(self, current_price: float, profit_threshold: float = 1.01) -> bool:
        """Check if position is profitable at current price"""
        return is_profitable_exit(self.buy_price, current_price, profit_threshold)

class PositionManager:
    """Manage trading positions and track P&L"""
    
    def __init__(self):
        self.positions: List[Position] = []
        self.closed_positions: List[Position] = []
        self._load_positions()
    
    def _load_positions(self):
        """Load positions from file"""
        try:
            data = load_json_file("data/positions.json", {})
            
            # Load open positions
            if 'open_positions' in data:
                self.positions = [
                    Position.from_dict(pos_data) 
                    for pos_data in data['open_positions']
                ]
            
            # Load closed positions
            if 'closed_positions' in data:
                self.closed_positions = [
                    Position.from_dict(pos_data) 
                    for pos_data in data['closed_positions']
                ]
            
            logger.info(f"Loaded {len(self.positions)} open positions and {len(self.closed_positions)} closed positions")
            
        except Exception as e:
            logger.error(f"Error loading positions: {str(e)}")
    
    def _save_positions(self):
        """Save positions to file"""
        try:
            data = {
                'open_positions': [pos.to_dict() for pos in self.positions],
                'closed_positions': [pos.to_dict() for pos in self.closed_positions],
                'last_updated': get_timestamp()
            }
            save_json_file("data/positions.json", data)
        except Exception as e:
            logger.error(f"Error saving positions: {str(e)}")
    
    def add_position(self, symbol: str, buy_price: float, amount: float) -> Position:
        """Add new position"""
        position = Position(symbol, buy_price, amount)
        self.positions.append(position)
        self._save_positions()
        
        logger.info(f"New position added: {amount:.6f} {symbol} at ${buy_price:.2f}")
        return position
    
    def close_position(self, position: Position, exit_price: float, amount_sold: float = None) -> float:
        """Close position and return profit/loss"""
        original_amount = position.amount
        position.close_position(exit_price, amount_sold)
        
        if position.status == 'closed':
            self.positions.remove(position)
            self.closed_positions.append(position)
        
        profit_pct = calculate_profit_percentage(position.buy_price, exit_price)
        sold_amount = amount_sold or original_amount
        
        logger.info(f"Position closed: {sold_amount:.6f} {position.symbol} at ${exit_price:.2f} - Profit: {profit_pct:+.2f}%")
        
        self._save_positions()
        return profit_pct
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        return self.positions.copy()
    
    def get_closed_positions(self) -> List[Position]:
        """Get all closed positions"""
        return self.closed_positions.copy()
    
    def get_total_btc_amount(self) -> float:
        """Get total BTC amount in open positions"""
        return sum(pos.amount for pos in self.positions)
    
    def get_average_buy_price(self) -> Optional[float]:
        """Get weighted average buy price of open positions"""
        if not self.positions:
            return None
        
        total_cost = sum(pos.buy_price * pos.amount for pos in self.positions)
        total_amount = sum(pos.amount for pos in self.positions)
        
        return total_cost / total_amount if total_amount > 0 else None
    
    def get_last_buy_price(self) -> Optional[float]:
        """Get the price of the most recent purchase"""
        if not self.positions:
            return None
        
        # Sort by timestamp and get the latest
        sorted_positions = sorted(self.positions, key=lambda x: x.timestamp, reverse=True)
        return sorted_positions[0].buy_price
    
    def get_profitable_positions(self, current_price: float, profit_threshold: float = 1.01) -> List[Position]:
        """Get positions that are profitable at current price"""
        return [
            pos for pos in self.positions 
            if pos.is_profitable(current_price, profit_threshold)
        ]
    
    def get_unrealized_pnl(self, current_price: float) -> Dict[str, float]:
        """Calculate unrealized P&L for open positions"""
        if not current_price or not self.positions:
            return {'absolute': 0.0, 'percentage': 0.0}
        
        total_cost = sum(pos.buy_price * pos.amount for pos in self.positions)
        total_amount = sum(pos.amount for pos in self.positions)
        current_value = total_amount * current_price
        
        absolute_pnl = current_value - total_cost
        percentage_pnl = (absolute_pnl / total_cost * 100) if total_cost > 0 else 0.0
        
        return {
            'absolute': absolute_pnl,
            'percentage': percentage_pnl,
            'total_cost': total_cost,
            'current_value': current_value
        }
    
    def get_realized_pnl(self) -> Dict[str, float]:
        """Calculate realized P&L from closed positions"""
        if not self.closed_positions:
            return {'absolute': 0.0, 'percentage': 0.0, 'total_trades': 0}
        
        total_profit_loss = 0.0
        total_trades = len(self.closed_positions)
        winning_trades = 0
        
        for pos in self.closed_positions:
            if pos.exit_price and pos.buy_price:
                trade_pnl = (pos.exit_price - pos.buy_price) * pos.amount
                total_profit_loss += trade_pnl
                
                if trade_pnl > 0:
                    winning_trades += 1
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        return {
            'absolute': total_profit_loss,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate
        }
    
    def should_buy_more(self, current_price: float, trigger_percent: float = 0.5) -> bool:
        """Check if we should buy more based on price drop"""
        last_buy_price = self.get_last_buy_price()
        if not last_buy_price:
            return True  # First purchase
        
        price_drop_threshold = last_buy_price * (1 - trigger_percent / 100)
        return current_price <= price_drop_threshold
    
    def clear_all_positions(self):
        """Clear all positions (for reset)"""
        self.closed_positions.extend(self.positions)
        self.positions = []
        self._save_positions()
        logger.info("All positions cleared")

# Global position manager instance
position_manager = PositionManager()