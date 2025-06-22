import json
import os
import streamlit as st
from typing import Dict, Any
from dotenv import load_dotenv
from .helpers import calculate_required_sell_price, validate_profit_margin

load_dotenv()

class Config:
    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self._config = self._load_config()
        self._secrets = self._load_secrets()
        self._live_access_validated = False
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Create default config if not found
            default_config = {
                "mode": "simulation",
                "trading": {
                    "symbol": "BTC-USDT",
                    "user_profit_margin": 0.005,
                    "buy_trigger_percent": 0.5,
                    "order_type": "limit",
                    "min_trade_amount": 10,
                    "max_position_size": 1.0
                },
                "kucoin": {
                    "sandbox": True,
                    "api_url": "https://api.kucoin.com",
                    "sandbox_url": "https://openapi-sandbox.kucoin.com"
                },
                "ui": {
                    "refresh_interval": 5,
                    "chart_timeframe": "1h",
                    "show_debug": True
                },
                "risk": {
                    "max_drawdown_percent": 20,
                    "emergency_stop": False,
                    "max_open_positions": 5
                }
            }
            self._save_config(default_config)
            return default_config
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in config file: {self.config_path}")
    
    def _load_secrets(self) -> Dict[str, str]:
        """Load secrets from Streamlit secrets or environment variables"""
        secrets = {}
        
        # Try Streamlit secrets first
        if hasattr(st, 'secrets') and 'api_credentials' in st.secrets:
            creds = st.secrets['api_credentials']
            secrets = {
                'api_key': creds.get('api_key'),
                'api_secret': creds.get('api_secret'),
                'api_passphrase': creds.get('api_passphrase'),
                'live_trading_access_key': creds.get('live_trading_access_key'),
                'initial_balance': float(creds.get('initial_balance', 50)),
                'telegram_token': creds.get('telegram_bot_token'),
                'telegram_chat_id': creds.get('telegram_chat_id')
            }
        else:
            # Fallback to environment variables
            secrets = {
                'api_key': os.getenv('KUCOIN_API_KEY'),
                'api_secret': os.getenv('KUCOIN_API_SECRET'),
                'api_passphrase': os.getenv('KUCOIN_API_PASSPHRASE'),
                'live_trading_access_key': os.getenv('LIVE_TRADING_ACCESS_KEY'),
                'initial_balance': float(os.getenv('INITIAL_BALANCE', 50)),
                'telegram_token': os.getenv('TELEGRAM_BOT_TOKEN'),
                'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID')
            }
        
        return secrets
    
    def _save_config(self, config_data: Dict[str, Any] = None):
        """Save configuration to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            data_to_save = config_data or self._config
            with open(self.config_path, 'w') as f:
                json.dump(data_to_save, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {str(e)}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation"""
        keys = key.split('.')
        config_section = self._config
        
        # Navigate to the parent section
        for k in keys[:-1]:
            if k not in config_section:
                config_section[k] = {}
            config_section = config_section[k]
        
        # Set the value
        config_section[keys[-1]] = value
        self._save_config()
    
    def get_secret(self, key: str) -> str:
        """Get secret value"""
        return self._secrets.get(key)
    
    def validate_live_access(self, provided_key: str) -> bool:
        """Validate live trading access key"""
        stored_key = self.get_secret('live_trading_access_key')
        if not stored_key:
            return False
        
        is_valid = provided_key == stored_key
        if is_valid:
            self._live_access_validated = True
        return is_valid
    
    def is_live_access_validated(self) -> bool:
        """Check if live trading access has been validated"""
        return self._live_access_validated
    
    def requires_live_access_key(self) -> bool:
        """Check if live trading access key is required"""
        return not self.is_simulation_mode() and bool(self.get_secret('live_trading_access_key'))
    
    def is_simulation_mode(self) -> bool:
        """Check if running in simulation mode"""
        return self.get('mode') == 'simulation'
    
    def set_mode(self, mode: str):
        """Set trading mode and reset live access validation"""
        if mode in ['simulation', 'live']:
            self.set('mode', mode)
            if mode == 'simulation':
                self._live_access_validated = True  # No key needed for simulation
            else:
                self._live_access_validated = False  # Reset for live mode
    
    def is_sandbox_mode(self) -> bool:
        """Check if using KuCoin sandbox"""
        return self.get('kucoin.sandbox', True)
    
    def get_trading_symbol(self) -> str:
        """Get trading symbol"""
        return self.get('trading.symbol', 'BTC-USDT')
    
    def get_profit_threshold(self) -> float:
        """Get profit threshold (1.01 = 1% profit) - DEPRECATED"""
        # This is now calculated dynamically based on user margin
        return 1.0 + self.get_user_profit_margin()
    
    def get_buy_trigger_percent(self) -> float:
        """Get buy trigger percentage"""
        return self.get('trading.buy_trigger_percent', 0.5)
    
    def get_user_profit_margin(self) -> float:
        """Get user's desired profit margin"""
        return self.get('trading.user_profit_margin', 0.005)  # Default 0.5%
    
    def set_user_profit_margin(self, margin: float):
        """Set user's profit margin and save to config"""
        self.set('trading.user_profit_margin', margin)
    
    def get_calculated_sell_target(self, buy_price: float) -> float:
        """Calculate sell target price based on user's desired margin"""
        user_margin = self.get_user_profit_margin()
        buy_fee_rate = self.get('trading.buy_fee_rate', 0.001)
        sell_fee_rate = self.get('trading.sell_fee_rate', 0.001)
        return calculate_required_sell_price(buy_price, user_margin, buy_fee_rate, sell_fee_rate)
    
    def get_fee_rates(self) -> Dict[str, float]:
        """Get trading fee rates"""
        return {
            'maker_buy': self.get('trading.maker_fee_rate', 0.001),
            'maker_sell': self.get('trading.maker_fee_rate', 0.001),
            'taker_buy': self.get('trading.taker_fee_rate', 0.001),
            'taker_sell': self.get('trading.taker_fee_rate', 0.001)
        }
    
    def validate_profit_margin_setting(self) -> tuple[bool, str]:
        """Validate current profit margin setting"""
        margin = self.get_user_profit_margin()
        is_valid, message, _ = validate_profit_margin(margin)
        return is_valid, message
    
    def get_order_type_preference(self) -> str:
        """Get preferred order type (limit/market)"""
        return self.get('trading.order_type', 'limit')
    
    def set_order_type_preference(self, order_type: str):
        """Set preferred order type"""
        if order_type in ['limit', 'market']:
            self.set('trading.order_type', order_type)
    
    def validate_secrets(self) -> bool:
        """Validate that required secrets are present"""
        required_secrets = ['api_key', 'api_secret', 'api_passphrase']
        
        for secret in required_secrets:
            if not self.get_secret(secret):
                return False
        return True
    
    def get_secrets_source(self) -> str:
        """Get source of secrets (streamlit or environment)"""
        if hasattr(st, 'secrets') and 'api_credentials' in st.secrets:
            return "streamlit_secrets"
        return "environment_variables"

# Global config instance
config = Config()