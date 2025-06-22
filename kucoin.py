import time
import hmac
import hashlib
import base64
import requests
from typing import Dict, Optional, Any, List

class KuCoinClient:
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str, sandbox: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.base_url = "https://openapi-sandbox.kucoin.com" if sandbox else "https://api.kucoin.com"
        self.is_connected = False
        self.pending_orders = {}  # Track our pending orders
        self._test_connection()
    
    def _encrypt_passphrase(self) -> str:
        """Encrypt passphrase with API secret"""
        return base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                self.api_passphrase.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode()
    
    def _sign_request(self, method: str, endpoint: str, body: str = "") -> Dict[str, str]:
        """Create KuCoin API signature headers"""
        timestamp = str(int(time.time() * 1000))
        str_to_sign = timestamp + method.upper() + endpoint + body
        
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                str_to_sign.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode()
        
        return {
            "KC-API-KEY": self.api_key,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-PASSPHRASE": self._encrypt_passphrase(),
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Make authenticated request to KuCoin API"""
        try:
            url = f"{self.base_url}{endpoint}"
            body = ""
            if data:
                import json
                body = json.dumps(data)
            
            headers = self._sign_request(method, endpoint, body)
            
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, data=body, timeout=10)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                return None
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == "200000":
                    return result.get("data")
            
            print(f"API Error: {response.status_code} - {response.text}")
            return None
            
        except Exception as e:
            print(f"API request error: {e}")
            return None
    
    def _test_connection(self):
        """Test API connection"""
        try:
            result = self._make_request("GET", "/api/v1/accounts")
            self.is_connected = result is not None
            if self.is_connected:
                print("✅ KuCoin API connected")
            else:
                print("❌ KuCoin API connection failed")
        except:
            self.is_connected = False
            print("❌ KuCoin API connection failed")
    
    def get_current_price(self, symbol: str = "BTC-USDT") -> Optional[float]:
        """Get current market price"""
        result = self._make_request("GET", f"/api/v1/market/orderbook/level1?symbol={symbol}")
        if result and "price" in result:
            return float(result["price"])
        return None
    
    def get_order_book(self, symbol: str = "BTC-USDT", depth: int = 20) -> Optional[Dict]:
        """Get order book for sophisticated order placement"""
        result = self._make_request("GET", f"/api/v3/market/orderbook/level2?symbol={symbol}")
        if result:
            return {
                'bids': [[float(bid[0]), float(bid[1])] for bid in result.get('bids', [])[:depth]],
                'asks': [[float(ask[0]), float(ask[1])] for ask in result.get('asks', [])[:depth]],
                'timestamp': result.get('time')
            }
        return None
    
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
    
    def get_balance(self, currency: str = "USDT") -> float:
        """Get account balance"""
        result = self._make_request("GET", "/api/v1/accounts")
        if result:
            for account in result:
                if account.get("currency") == currency and account.get("type") == "trade":
                    return float(account.get("available", 0))
        return 0.0
    
    def get_usdt_balance(self) -> float:
        """Get USDT balance"""
        return self.get_balance("USDT")
    
    def get_btc_balance(self) -> float:
        """Get BTC balance"""
        return self.get_balance("BTC")
    
    def calculate_smart_buy_price(self, symbol: str = "BTC-USDT") -> Optional[float]:
        """Calculate smart buy price based on order book"""
        spread_info = self.get_bid_ask_spread(symbol)
        if not spread_info:
            # Fallback to simple market price
            current_price = self.get_current_price(symbol)
            return current_price * 0.999 if current_price else None
        
        bid = spread_info['bid']
        ask = spread_info['ask']
        spread_percent = spread_info['spread_percent']
        
        # If spread is small (< 0.1%), place order just above current bid
        if spread_percent < 0.1:
            return bid + 0.01  # $0.01 above highest bid
        else:
            # If spread is large, place order in middle-lower area
            return bid + (ask - bid) * 0.3  # 30% into the spread
    
    def calculate_smart_sell_price(self, symbol: str = "BTC-USDT") -> Optional[float]:
        """Calculate smart sell price based on order book"""
        spread_info = self.get_bid_ask_spread(symbol)
        if not spread_info:
            # Fallback to simple market price  
            current_price = self.get_current_price(symbol)
            return current_price * 1.001 if current_price else None
        
        bid = spread_info['bid']
        ask = spread_info['ask']
        spread_percent = spread_info['spread_percent']
        
        # If spread is small (< 0.1%), place order just below current ask
        if spread_percent < 0.1:
            return ask - 0.01  # $0.01 below lowest ask
        else:
            # If spread is large, place order in middle-upper area
            return ask - (ask - bid) * 0.3  # 30% into the spread from ask side
    
    def place_smart_limit_buy_order(self, symbol: str, amount_usdt: float) -> Optional[str]:
        """Place intelligent limit buy order for best execution"""
        smart_price = self.calculate_smart_buy_price(symbol)
        if not smart_price:
            print("Cannot calculate smart buy price")
            return None
        
        size = round(amount_usdt / smart_price, 8)
        
        # Validate minimum order size
        if size < 0.00001:  # KuCoin minimum
            print(f"Order size too small: {size}")
            return None
        
        data = {
            "clientOid": f"smart_buy_{int(time.time() * 1000)}",
            "side": "buy",
            "symbol": symbol,
            "type": "limit",
            "size": str(size),
            "price": str(smart_price)
        }
        
        result = self._make_request("POST", "/api/v1/orders", data)
        if result and "orderId" in result:
            order_id = result["orderId"]
            # Track this order
            self.pending_orders[order_id] = {
                'type': 'buy',
                'symbol': symbol,
                'size': size,
                'price': smart_price,
                'amount_usdt': amount_usdt,
                'timestamp': time.time()
            }
            print(f"Smart buy order placed: {size:.6f} {symbol} @ ${smart_price:.2f}")
            return order_id
        
        return None
    
    def place_smart_limit_sell_order(self, symbol: str, size: float, target_price: float) -> Optional[str]:
        """Place intelligent limit sell order"""
        # Use target price if it's better than smart price, otherwise use smart price
        smart_price = self.calculate_smart_sell_price(symbol)
        if smart_price and smart_price > target_price:
            sell_price = smart_price
        else:
            sell_price = target_price
        
        data = {
            "clientOid": f"smart_sell_{int(time.time() * 1000)}",
            "side": "sell", 
            "symbol": symbol,
            "type": "limit",
            "size": str(size),
            "price": str(sell_price)
        }
        
        result = self._make_request("POST", "/api/v1/orders", data)
        if result and "orderId" in result:
            order_id = result["orderId"]
            # Track this order
            self.pending_orders[order_id] = {
                'type': 'sell',
                'symbol': symbol,
                'size': size,
                'price': sell_price,
                'target_price': target_price,
                'timestamp': time.time()
            }
            print(f"Smart sell order placed: {size:.6f} {symbol} @ ${sell_price:.2f}")
            return order_id
        
        return None
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get order status"""
        result = self._make_request("GET", f"/api/v1/orders/{order_id}")
        return result
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        result = self._make_request("DELETE", f"/api/v1/orders/{order_id}")
        if result:
            # Remove from our tracking
            if order_id in self.pending_orders:
                del self.pending_orders[order_id]
            print(f"Order cancelled: {order_id}")
            return True
        return False
    
    def get_open_orders(self, symbol: str = "BTC-USDT") -> List[Dict]:
        """Get open orders"""
        result = self._make_request("GET", f"/api/v1/orders?status=active&symbol={symbol}")
        return result.get("items", []) if result else []
    
    def check_filled_orders(self) -> List[Dict]:
        """Check which of our tracked orders have been filled"""
        filled_orders = []
        
        for order_id in list(self.pending_orders.keys()):
            status = self.get_order_status(order_id)
            
            if status and status.get("isActive") == False:
                # Order is no longer active (filled or cancelled)
                order_info = self.pending_orders[order_id].copy()
                order_info['order_id'] = order_id
                order_info['status'] = status.get('opType', 'unknown')
                order_info['filled_size'] = float(status.get('dealSize', 0))
                order_info['filled_funds'] = float(status.get('dealFunds', 0))
                order_info['actual_price'] = float(status.get('dealFunds', 0)) / float(status.get('dealSize', 1)) if float(status.get('dealSize', 0)) > 0 else order_info['price']
                order_info['fee'] = float(status.get('fee', 0))
                
                filled_orders.append(order_info)
                
                # Remove from pending
                del self.pending_orders[order_id]
                
                print(f"Order filled: {order_id} - {order_info['type']} {order_info['filled_size']:.6f} @ ${order_info['actual_price']:.2f}")
        
        return filled_orders
    
    def get_trading_fees(self) -> Dict[str, float]:
        """Get current trading fees"""
        # For most users, KuCoin charges 0.1% maker/taker
        return {
            'maker': 0.001,  # 0.1%
            'taker': 0.001   # 0.1%
        }
    
    def cancel_all_orders(self, symbol: str = "BTC-USDT") -> bool:
        """Cancel all open orders"""
        try:
            result = self._make_request("DELETE", f"/api/v1/orders?symbol={symbol}")
            if result:
                # Clear our tracking
                self.pending_orders.clear()
                print("All orders cancelled")
                return True
        except Exception as e:
            print(f"Error cancelling all orders: {e}")
        return False