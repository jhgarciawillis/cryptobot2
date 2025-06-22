import time
import hmac
import hashlib
import base64
import requests
from typing import Dict, Optional, Any

class KuCoinClient:
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str, sandbox: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.base_url = "https://openapi-sandbox.kucoin.com" if sandbox else "https://api.kucoin.com"
        self.is_connected = False
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
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, data=body)
            else:
                return None
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == "200000":
                    return result.get("data")
            return None
            
        except Exception as e:
            print(f"API request error: {e}")
            return None
    
    def _test_connection(self):
        """Test API connection"""
        try:
            result = self._make_request("GET", "/api/v1/accounts")
            self.is_connected = result is not None
        except:
            self.is_connected = False
    
    def get_current_price(self, symbol: str = "BTC-USDT") -> Optional[float]:
        """Get current market price"""
        result = self._make_request("GET", f"/api/v1/market/orderbook/level1?symbol={symbol}")
        if result and "price" in result:
            return float(result["price"])
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
    
    def place_market_buy_order(self, symbol: str, amount_usdt: float) -> Optional[str]:
        """Place market buy order and return order ID"""
        current_price = self.get_current_price(symbol)
        if not current_price:
            return None
        
        size = round(amount_usdt / current_price, 8)
        
        data = {
            "clientOid": f"buy_{int(time.time() * 1000)}",
            "side": "buy",
            "symbol": symbol,
            "type": "market",
            "funds": str(amount_usdt)
        }
        
        result = self._make_request("POST", "/api/v1/orders", data)
        return result.get("orderId") if result else None
    
    def place_limit_buy_order(self, symbol: str, size: float, price: float) -> Optional[str]:
        """Place limit buy order and return order ID"""
        data = {
            "clientOid": f"buy_limit_{int(time.time() * 1000)}",
            "side": "buy",
            "symbol": symbol,
            "type": "limit",
            "size": str(size),
            "price": str(price)
        }
        
        result = self._make_request("POST", "/api/v1/orders", data)
        return result.get("orderId") if result else None
    
    def place_market_sell_order(self, symbol: str, size: float) -> Optional[str]:
        """Place market sell order and return order ID"""
        data = {
            "clientOid": f"sell_{int(time.time() * 1000)}",
            "side": "sell",
            "symbol": symbol,
            "type": "market",
            "size": str(size)
        }
        
        result = self._make_request("POST", "/api/v1/orders", data)
        return result.get("orderId") if result else None
    
    def place_limit_sell_order(self, symbol: str, size: float, price: float) -> Optional[str]:
        """Place limit sell order and return order ID"""
        data = {
            "clientOid": f"sell_limit_{int(time.time() * 1000)}",
            "side": "sell",
            "symbol": symbol,
            "type": "limit",
            "size": str(size),
            "price": str(price)
        }
        
        result = self._make_request("POST", "/api/v1/orders", data)
        return result.get("orderId") if result else None
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get order status"""
        result = self._make_request("GET", f"/api/v1/orders/{order_id}")
        return result
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        result = self._make_request("DELETE", f"/api/v1/orders/{order_id}")
        return result is not None
    
    def get_open_orders(self, symbol: str = "BTC-USDT") -> list:
        """Get open orders"""
        result = self._make_request("GET", f"/api/v1/orders?status=active&symbol={symbol}")
        return result.get("items", []) if result else []