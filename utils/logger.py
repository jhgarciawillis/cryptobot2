import logging
import os
from datetime import datetime
from typing import Optional

class Logger:
    def __init__(self, name: str = "crypto_bot", log_dir: str = "data/logs"):
        self.name = name
        self.log_dir = log_dir
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with file and console handlers"""
        # Create logs directory if it doesn't exist
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.INFO)
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            return
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )
        
        # File handler
        log_file = os.path.join(
            self.log_dir, 
            f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str, extra_data: Optional[dict] = None):
        """Log info message"""
        if extra_data:
            message = f"{message} | Data: {extra_data}"
        self.logger.info(message)
    
    def error(self, message: str, exception: Optional[Exception] = None):
        """Log error message"""
        if exception:
            message = f"{message} | Exception: {str(exception)}"
        self.logger.error(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
    
    def trade(self, action: str, symbol: str, price: float, amount: float, mode: str = "LIVE"):
        """Log trading action"""
        message = f"[{mode}] {action} - {symbol} | Price: ${price:.2f} | Amount: {amount:.6f}"
        self.info(message)

# Global logger instance
logger = Logger()