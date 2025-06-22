#!/usr/bin/env python3
"""
Alternative entry point for the Crypto Profit Bot
This can be used to run the bot without Streamlit for headless operation
"""

import sys
import time
import signal
import argparse
from datetime import datetime

from core.trading_engine import trading_engine, BotState
from utils.config import config
from utils.logger import logger

class HeadlessBot:
    """Headless bot runner for command-line operation"""
    
    def __init__(self):
        self.running = False
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        
        if trading_engine.state == BotState.RUNNING:
            trading_engine.stop_trading()
            
            # Wait for profitable exit
            timeout = 300  # 5 minutes timeout
            start_time = time.time()
            
            while trading_engine.state != BotState.STOPPED and (time.time() - start_time) < timeout:
                time.sleep(1)
            
            if trading_engine.state != BotState.STOPPED:
                logger.warning("Timeout waiting for profitable exit, force stopping...")
                trading_engine.force_stop()
    
    def run(self, auto_start=False):
        """Run the bot in headless mode"""
        logger.info("Starting Crypto Profit Bot in headless mode...")
        logger.info(f"Mode: {'SIMULATION' if config.is_simulation_mode() else 'LIVE'}")
        
        self.running = True
        
        if auto_start:
            logger.info("Auto-starting trading bot...")
            if trading_engine.start_trading():
                logger.info("Bot started successfully")
            else:
                logger.error("Failed to start bot")
                return 1
        
        try:
            while self.running:
                status = trading_engine.get_status()
                
                # Log status periodically
                if int(time.time()) % 60 == 0:  # Every minute
                    self.log_status(status)
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return 1
        finally:
            logger.info("Shutting down...")
            if trading_engine.state == BotState.RUNNING:
                trading_engine.force_stop()
        
        return 0
    
    def log_status(self, status):
        """Log current bot status"""
        state = status['state']
        current_price = status.get('current_price', 0)
        position_count = status.get('positions', {}).get('count', 0)
        
        logger.info(f"Status: {state} | Price: ${current_price:,.2f} | Positions: {position_count}")
        
        if status.get('pnl'):
            unrealized = status['pnl']['unrealized']
            pnl_value = unrealized.get('absolute', 0)
            pnl_pct = unrealized.get('percentage', 0)
            logger.info(f"Unrealized P&L: ${pnl_value:.2f} ({pnl_pct:+.2f}%)")

def main():
    """Main entry point for headless operation"""
    parser = argparse.ArgumentParser(description='Crypto Profit Bot - Headless Runner')
    parser.add_argument('--start', action='store_true', help='Auto-start trading')
    parser.add_argument('--config', type=str, help='Config file path')
    parser.add_argument('--mode', choices=['simulation', 'live'], help='Override trading mode')
    
    args = parser.parse_args()
    
    # Override config if specified
    if args.config:
        # Would need to implement config override
        pass
    
    if args.mode:
        # Would need to implement mode override
        pass
    
    # Create and run headless bot
    bot = HeadlessBot()
    exit_code = bot.run(auto_start=args.start)
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()