import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import pandas as pd

def ensure_directory(path: str):
    """Ensure directory exists, create if not"""
    os.makedirs(path, exist_ok=True)

def load_json_file(file_path: str, default: Any = None) -> Any:
    """Load JSON file, return default if file doesn't exist"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default or {}

def save_json_file(file_path: str, data: Any):
    """Save data to JSON file"""
    ensure_directory(os.path.dirname(file_path))
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def get_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now(timezone.utc).isoformat()

def calculate_profit_percentage(buy_price: float, sell_price: float) -> float:
    """Calculate profit percentage"""
    if buy_price <= 0:
        return 0.0
    return ((sell_price - buy_price) / buy_price) * 100

def format_currency(amount: float, symbol: str = "$") -> str:
    """Format currency amount"""
    return f"{symbol}{amount:,.2f}"

def format_percentage(percentage: float) -> str:
    """Format percentage"""
    return f"{percentage:+.2f}%"

def validate_price(price: float) -> bool:
    """Validate if price is valid"""
    return price > 0 and not pd.isna(price)

def calculate_position_size(balance: float, price: float, percentage: float = 1.0) -> float:
    """Calculate position size based on balance and percentage"""
    if not validate_price(price) or balance <= 0:
        return 0.0
    
    max_amount = (balance * percentage) / price
    return round(max_amount, 8)  # Round to 8 decimal places for crypto

def is_profitable_exit(buy_price: float, current_price: float, profit_threshold: float = 1.01) -> bool:
    """Check if current price provides profitable exit"""
    if not validate_price(buy_price) or not validate_price(current_price):
        return False
    
    return current_price >= (buy_price * profit_threshold)

def calculate_drawdown_trigger(last_buy_price: float, trigger_percent: float = 0.5) -> float:
    """Calculate price level that triggers next buy"""
    if not validate_price(last_buy_price):
        return 0.0
    
    trigger_multiplier = 1 - (trigger_percent / 100)
    return last_buy_price * trigger_multiplier

def calculate_required_sell_price(buy_price: float, desired_profit_percent: float, 
                                 buy_fee_rate: float = 0.001, sell_fee_rate: float = 0.001) -> float:
    """
    Calculate the required sell price to achieve desired profit after all fees
    
    Args:
        buy_price: Price at which BTC was bought
        desired_profit_percent: Desired profit (e.g., 0.005 for 0.5%)
        buy_fee_rate: Fee rate for buy order (default 0.1%)
        sell_fee_rate: Fee rate for sell order (default 0.1%)
    
    Returns:
        Required sell price to achieve desired profit
    """
    # Account for buy fee in effective buy price
    effective_buy_price = buy_price / (1 - buy_fee_rate)
    
    # Calculate sell price needed after sell fees
    required_sell_price = effective_buy_price * (1 + desired_profit_percent) / (1 - sell_fee_rate)
    
    return required_sell_price

def calculate_actual_profit_margin(buy_price: float, sell_price: float,
                                 buy_fee_rate: float = 0.001, sell_fee_rate: float = 0.001) -> float:
    """
    Calculate actual profit margin achieved after all fees
    """
    # Net buy cost (including fees)
    net_buy_cost = buy_price * (1 + buy_fee_rate)
    
    # Net sell proceeds (after fees)
    net_sell_proceeds = sell_price * (1 - sell_fee_rate)
    
    # Actual profit margin
    profit_margin = (net_sell_proceeds - net_buy_cost) / net_buy_cost
    
    return profit_margin

def get_minimum_viable_profit_margin(buy_fee_rate: float = 0.001, sell_fee_rate: float = 0.001) -> float:
    """
    Calculate minimum profit margin needed to break even after fees
    """
    # Minimum margin needed to overcome fees
    minimum_margin = (buy_fee_rate + sell_fee_rate) / (1 - sell_fee_rate)
    return minimum_margin

def validate_profit_margin(desired_margin: float) -> tuple[bool, str, float]:
    """
    Validate user's desired profit margin and suggest minimum
    
    Returns:
        (is_valid, message, suggested_minimum)
    """
    minimum_viable = get_minimum_viable_profit_margin()
    suggested_minimum = minimum_viable * 1.5  # 50% buffer above break-even
    
    if desired_margin < minimum_viable:
        return False, f"Margin too low. Minimum needed: {minimum_viable*100:.3f}%", suggested_minimum
    elif desired_margin < suggested_minimum:
        return True, f"Risky margin. Suggested minimum: {suggested_minimum*100:.3f}%", suggested_minimum
    else:
        return True, "Margin looks good!", suggested_minimum

def calculate_limit_order_profit(buy_price: float, sell_price: float, amount: float,
                               buy_fee_rate: float = 0.001, sell_fee_rate: float = 0.001) -> Dict[str, float]:
    """
    Calculate detailed profit breakdown for limit orders
    """
    # Buy side calculations
    gross_buy_cost = buy_price * amount
    buy_fee = gross_buy_cost * buy_fee_rate
    net_buy_cost = gross_buy_cost + buy_fee
    
    # Sell side calculations
    gross_sell_proceeds = sell_price * amount
    sell_fee = gross_sell_proceeds * sell_fee_rate
    net_sell_proceeds = gross_sell_proceeds - sell_fee
    
    # Profit calculations
    gross_profit = gross_sell_proceeds - gross_buy_cost
    net_profit = net_sell_proceeds - net_buy_cost
    profit_margin = net_profit / net_buy_cost if net_buy_cost > 0 else 0
    
    return {
        'gross_buy_cost': gross_buy_cost,
        'buy_fee': buy_fee,
        'net_buy_cost': net_buy_cost,
        'gross_sell_proceeds': gross_sell_proceeds,
        'sell_fee': sell_fee,
        'net_sell_proceeds': net_sell_proceeds,
        'gross_profit': gross_profit,
        'net_profit': net_profit,
        'profit_margin': profit_margin,
        'total_fees': buy_fee + sell_fee
    }

class PriceTracker:
    """Track price movements and calculate triggers"""
    
    def __init__(self):
        self.price_history = []
        self.max_history_length = 1000
    
    def add_price(self, price: float, timestamp: Optional[str] = None):
        """Add price to history"""
        if not validate_price(price):
            return
        
        entry = {
            'price': price,
            'timestamp': timestamp or get_timestamp()
        }
        
        self.price_history.append(entry)
        
        # Keep only recent history
        if len(self.price_history) > self.max_history_length:
            self.price_history = self.price_history[-self.max_history_length:]
    
    def get_latest_price(self) -> Optional[float]:
        """Get latest price"""
        if not self.price_history:
            return None
        return self.price_history[-1]['price']
    
    def get_price_change_percent(self, periods: int = 1) -> Optional[float]:
        """Get price change percentage over periods"""
        if len(self.price_history) < periods + 1:
            return None
        
        current_price = self.price_history[-1]['price']
        past_price = self.price_history[-(periods + 1)]['price']
        
        return calculate_profit_percentage(past_price, current_price)