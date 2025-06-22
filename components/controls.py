import streamlit as st
import time
from datetime import datetime
from typing import Dict, Any

from core.trading_engine import trading_engine, BotState
from core.position_manager import position_manager
from core.simulator import simulator
from utils.config import config
from utils.logger import logger
from utils.helpers import calculate_required_sell_price, validate_profit_margin, get_minimum_viable_profit_margin, calculate_limit_order_profit

def render_controls():
    """Render bot control buttons and actions"""
    
    # Check if live access key is required and not validated
    if config.requires_live_access_key() and not config.is_live_access_validated():
        render_live_access_gate()
        return
    
    status = trading_engine.get_status()
    current_state = status['state']
    pending_exit = status.get('pending_exit', False)
    
    st.subheader("🎮 Bot Controls")
    
    # Mode selector
    render_mode_selector()
    
    st.divider()
    
    # Main control buttons
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if current_state == 'stopped':
            if st.button("🚀 Start Trading", type="primary", use_container_width=True):
                start_trading_action()
        elif current_state == 'running' and not pending_exit:
            if st.button("⏹️ Stop Trading", type="secondary", use_container_width=True):
                stop_trading_action()
        elif pending_exit:
            if st.button("🔴 Force Stop", type="secondary", use_container_width=True):
                force_stop_action()
        else:
            st.button("⏳ Processing...", disabled=True, use_container_width=True)
    
    with col2:
        if st.button("🔄 Refresh Status", use_container_width=True):
            st.rerun()
    
    with col3:
        if st.button("📊 Reset Bot", use_container_width=True):
            reset_bot_action()
    
    with col4:
        if config.is_simulation_mode():
            if st.button("💰 Add Funds", use_container_width=True):
                show_add_funds_dialog()
    
    # Status messages
    render_control_status(status)
    
    # Profit margin control
    st.divider()
    render_profit_margin_control()
    
    # Order type control
    st.divider()
    render_order_type_control()
    
    # Advanced controls
    render_advanced_controls(status)
    
    # Emergency controls
    render_emergency_controls()

def render_live_access_gate():
    """Render live trading access key input"""
    st.error("🔐 **Live Trading Access Required**")
    st.warning("⚠️ This bot is configured for live trading. Please enter the live trading access key to continue.")
    
    with st.form("live_access_form"):
        access_key = st.text_input(
            "Live Trading Access Key",
            type="password",
            help="Enter the secure access key to enable live trading functionality"
        )
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            submitted = st.form_submit_button("🔓 Unlock Live Trading", type="primary")
        
        with col2:
            if st.form_submit_button("🔄 Switch to Simulation"):
                config.set_mode('simulation')
                st.success("✅ Switched to simulation mode")
                st.rerun()
        
        with col3:
            if st.form_submit_button("ℹ️ About Access Key"):
                show_access_key_info()
    
    if submitted:
        if access_key:
            if config.validate_live_access(access_key):
                st.success("✅ Live trading access granted!")
                logger.info("Live trading access validated via UI")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Invalid access key. Please check and try again.")
                logger.warning("Failed live trading access attempt via UI")
        else:
            st.error("❌ Please enter an access key.")

def show_access_key_info():
    """Show information about the access key"""
    st.info("""
    **About Live Trading Access Key:**
    
    🔐 This is a security feature to prevent unauthorized access to live trading functionality.
    
    🛡️ **Why it's needed:**
    - Prevents accidental live trading by unauthorized users
    - Protects your API credentials from misuse
    - Adds an extra layer of security for real money trading
    
    📝 **How to get it:**
    - The access key is set by the bot owner in Streamlit secrets
    - Contact the bot administrator if you need access
    - For personal use, you set this key yourself in the secrets
    
    🔄 **Alternative:**
    - You can always use simulation mode without any access key
    - Simulation mode uses real market data but virtual money
    """)

def render_mode_selector():
    """Render trading mode selector"""
    st.subheader("🎯 Trading Mode")
    
    current_mode = "Simulation" if config.is_simulation_mode() else "Live Trading"
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Show current mode
        if config.is_simulation_mode():
            st.success(f"🟢 **Current Mode:** {current_mode}")
        else:
            st.error(f"🔴 **Current Mode:** {current_mode}")
    
    with col2:
        if not config.is_simulation_mode():
            if st.button("🔄 Switch to Simulation", type="secondary"):
                switch_to_simulation()
    
    with col3:
        if config.is_simulation_mode():
            if st.button("⚠️ Switch to Live", type="secondary"):
                switch_to_live()
    
    # Show secrets source
    secrets_source = config.get_secrets_source()
    if secrets_source == "streamlit_secrets":
        st.info("🔑 Using Streamlit secrets for API credentials")
    else:
        st.warning("🔑 Using environment variables for API credentials")

def switch_to_simulation():
    """Switch to simulation mode"""
    try:
        if trading_engine.state == BotState.RUNNING:
            st.warning("⚠️ Please stop the bot before switching modes")
            return
        
        config.set_mode('simulation')
        # Reinitialize trading engine with new mode
        trading_engine.__init__()
        
        st.success("✅ Switched to simulation mode")
        logger.info("Switched to simulation mode via UI")
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error switching to simulation: {str(e)}")
        logger.error(f"Error switching to simulation: {str(e)}")

def switch_to_live():
    """Switch to live trading mode"""
    try:
        if trading_engine.state == BotState.RUNNING:
            st.warning("⚠️ Please stop the bot before switching modes")
            return
        
        # Check if API credentials are available
        if not config.validate_secrets():
            st.error("❌ API credentials not found. Please configure Streamlit secrets.")
            return
        
        config.set_mode('live')
        
        # If live access key is required, don't reinitialize yet
        if config.requires_live_access_key():
            st.info("🔐 Live mode selected. Please enter access key to continue.")
        else:
            # Reinitialize trading engine with new mode
            trading_engine.__init__()
            st.success("✅ Switched to live trading mode")
            logger.info("Switched to live trading mode via UI")
        
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error switching to live mode: {str(e)}")
        logger.error(f"Error switching to live mode: {str(e)}")

def start_trading_action():
    """Handle start trading action"""
    try:
        # Final security check for live mode
        if not config.is_simulation_mode() and config.requires_live_access_key():
            if not config.is_live_access_validated():
                st.error("❌ Live trading access not validated")
                return
        
        with st.spinner("Starting trading bot..."):
            success = trading_engine.start_trading()
            
        if success:
            mode_text = "simulation" if config.is_simulation_mode() else "live trading"
            st.success(f"✅ Trading bot started successfully in {mode_text} mode!")
            logger.info(f"Bot started via UI in {mode_text} mode")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Failed to start trading bot. Check logs for details.")
            
    except Exception as e:
        st.error(f"❌ Error starting bot: {str(e)}")
        logger.error(f"UI start error: {str(e)}")

def stop_trading_action():
    """Handle stop trading action"""
    try:
        trading_engine.stop_trading()
        st.info("🟡 Stop signal sent. Bot will look for profitable exit opportunity...")
        logger.info("Stop signal sent via UI")
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error stopping bot: {str(e)}")
        logger.error(f"UI stop error: {str(e)}")

def force_stop_action():
    """Handle force stop action"""
    if st.button("⚠️ Confirm Force Stop", type="secondary"):
        try:
            with st.spinner("Force stopping bot..."):
                trading_engine.force_stop()
            
            st.warning("⚠️ Bot force stopped. Positions may still be open.")
            logger.info("Bot force stopped via UI")
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error force stopping bot: {str(e)}")
            logger.error(f"UI force stop error: {str(e)}")

def reset_bot_action():
    """Handle reset bot action"""
    st.subheader("🔄 Reset Bot")
    st.warning("⚠️ This will reset all positions and trading history!")
    
    if config.is_simulation_mode():
        st.info("In simulation mode, this will reset your virtual portfolio.")
    else:
        st.error("⚠️ LIVE MODE: This will clear position tracking but NOT affect actual holdings!")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Confirm Reset", type="primary"):
            try:
                with st.spinner("Resetting bot..."):
                    trading_engine.reset_bot()
                
                st.success("✅ Bot reset successfully!")
                logger.info("Bot reset via UI")
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error resetting bot: {str(e)}")
                logger.error(f"UI reset error: {str(e)}")
    
    with col2:
        if st.button("❌ Cancel"):
            st.rerun()

def show_add_funds_dialog():
    """Show add funds dialog for simulation mode"""
    if not config.is_simulation_mode():
        return
    
    st.subheader("💰 Add Virtual Funds")
    
    current_balance = simulator.get_usdt_balance()
    st.info(f"Current USDT Balance: ${current_balance:.2f}")
    
    amount = st.number_input(
        "Amount to add (USDT)",
        min_value=10.0,
        max_value=10000.0,
        value=100.0,
        step=10.0
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💰 Add Funds", type="primary"):
            try:
                simulator.balances['USDT'] += amount
                simulator._save_simulation_state()
                
                st.success(f"✅ Added ${amount:.2f} to simulation balance!")
                logger.info(f"Added ${amount:.2f} virtual funds via UI")
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error adding funds: {str(e)}")
    
    with col2:
        if st.button("❌ Cancel"):
            st.rerun()

def render_profit_margin_control():
    """Render profit margin input control"""
    st.subheader("🎯 Profit Margin Settings")
    
    current_margin = config.get_user_profit_margin() * 100  # Convert to percentage
    minimum_viable = get_minimum_viable_profit_margin() * 100
    
    # Warning about fees
    st.info(f"ℹ️ **Fee Impact**: KuCoin charges ~0.1% per trade. Minimum viable margin: {minimum_viable:.3f}%")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_margin = st.number_input(
            "Desired Profit Margin (%)",
            min_value=0.001,
            max_value=5.0,
            value=current_margin,
            step=0.001,
            format="%.3f",
            help="Your desired profit per trade. System will calculate required sell price including all fees."
        )
    
    with col2:
        if st.button("💰 Update Margin", type="primary"):
            update_profit_margin(new_margin)
    
    # Show calculations if margin changed
    if abs(new_margin - current_margin) > 0.001:
        show_margin_preview(new_margin)

def update_profit_margin(new_margin: float):
    """Update profit margin setting"""
    try:
        success = trading_engine.set_profit_margin(new_margin)
        
        if success:
            st.success(f"✅ Profit margin updated to {new_margin:.3f}%")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Failed to update profit margin")
            
    except Exception as e:
        st.error(f"❌ Error updating margin: {str(e)}")

def show_margin_preview(margin_percent: float):
    """Show preview of margin calculations"""
    st.subheader("📊 Margin Preview")
    
    # Validate margin
    is_valid, message, suggested = validate_profit_margin(margin_percent / 100)
    
    if not is_valid:
        st.error(f"⚠️ {message}")
        st.info(f"💡 Suggested minimum: {suggested * 100:.3f}%")
    elif "Risky" in message:
        st.warning(f"⚠️ {message}")
    else:
        st.success(f"✅ {message}")
    
    # Example calculation
    example_buy_price = 50000
    required_sell_price = calculate_required_sell_price(example_buy_price, margin_percent / 100)
    price_difference = required_sell_price - example_buy_price
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Example Buy", f"${example_buy_price:,.0f}")
    
    with col2:
        st.metric("Required Sell", f"${required_sell_price:,.0f}")
    
    with col3:
        st.metric("Price Difference", f"${price_difference:.0f}")
    
    # Fee breakdown
    with st.expander("🔍 Detailed Breakdown", expanded=False):
        profit_details = calculate_limit_order_profit(
            buy_price=example_buy_price,
            sell_price=required_sell_price,
            amount=0.001  # 0.001 BTC for example
        )
        
        st.write(f"**Example Trade (0.001 BTC):**")
        st.write(f"• Gross buy cost: ${profit_details['gross_buy_cost']:.2f}")
        st.write(f"• Buy fee (0.1%): ${profit_details['buy_fee']:.2f}")
        st.write(f"• Net buy cost: ${profit_details['net_buy_cost']:.2f}")
        st.write(f"• Gross sell proceeds: ${profit_details['gross_sell_proceeds']:.2f}")
        st.write(f"• Sell fee (0.1%): ${profit_details['sell_fee']:.2f}")
        st.write(f"• Net sell proceeds: ${profit_details['net_sell_proceeds']:.2f}")
        st.write(f"• **Net profit: ${profit_details['net_profit']:.2f}**")
        st.write(f"• **Actual margin: {profit_details['profit_margin']*100:.3f}%**")

def render_order_type_control():
    """Render order type selection control"""
    st.subheader("📋 Order Type Settings")
    
    current_order_type = trading_engine.order_type
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_order_type = st.selectbox(
            "Order Type",
            options=["limit", "market"],
            index=0 if current_order_type == "limit" else 1,
            help="Limit orders get better fees but may not fill immediately. Market orders execute immediately but have higher fees."
        )
    
    with col2:
        if st.button("🔄 Update Type", type="primary"):
            update_order_type(new_order_type)
    
    # Show order type comparison
    if new_order_type != current_order_type:
        show_order_type_comparison(new_order_type)

def update_order_type(new_order_type: str):
    """Update order type setting"""
    try:
        success = trading_engine.set_order_type(new_order_type)
        
        if success:
            st.success(f"✅ Order type updated to {new_order_type}")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Failed to update order type")
            
    except Exception as e:
        st.error(f"❌ Error updating order type: {str(e)}")

def show_order_type_comparison(selected_type: str):
    """Show comparison between order types"""
    st.subheader("📊 Order Type Comparison")
    
    comparison_data = {
        "Feature": ["Execution Speed", "Fee Rate", "Price Guarantee", "Fill Guarantee", "Best For"],
        "Limit Orders": ["Slower", "~0.1% (Maker)", "Guaranteed", "Not Guaranteed", "Better profits"],
        "Market Orders": ["Immediate", "~0.1% (Taker)", "Not Guaranteed", "Guaranteed", "Faster cycles"]
    }
    
    st.table(comparison_data)
    
    if selected_type == "limit":
        st.info("💡 **Limit Orders**: Better for profit margins but may miss fast-moving opportunities")
    else:
        st.info("💡 **Market Orders**: Faster execution but potentially lower profits due to slippage")

def render_control_status(status: Dict[str, Any]):
    """Render current control status"""
    current_state = status['state']
    pending_exit = status.get('pending_exit', False)
    
    if current_state == 'running':
        if pending_exit:
            st.info("🟡 **Status:** Looking for profitable exit opportunity...")
            
            # Show exit progress
            positions = position_manager.get_open_positions()
            current_price = status.get('current_price', 0)
            
            if positions and current_price:
                profitable_count = 0
                for position in positions:
                    sell_target = calculate_required_sell_price(position.buy_price, trading_engine.user_profit_margin)
                    if current_price >= sell_target:
                        profitable_count += 1
                
                total_count = len(positions)
                progress = profitable_count / total_count if total_count > 0 else 0
                st.progress(progress, text=f"Profitable positions: {profitable_count}/{total_count}")
                
                if profitable_count == total_count:
                    st.success("🎉 All positions are profitable! Exit should complete shortly.")
        else:
            st.success("🟢 **Status:** Bot is actively trading")
            
            # Show trading info
            pending_orders = status.get('pending_orders', {})
            if pending_orders.get('total_pending', 0) > 0:
                st.info(f"📋 Pending orders: {pending_orders['buy_orders']} buys, {pending_orders['sell_orders']} sells")
    
    elif current_state == 'stopped':
        st.info("⚪ **Status:** Bot is stopped")
    
    elif current_state == 'stopping':
        st.warning("🟡 **Status:** Bot is stopping...")
    
    elif current_state == 'error':
        st.error("🔴 **Status:** Bot encountered an error - Check logs")

def render_advanced_controls(status: Dict[str, Any]):
   """Render advanced control options"""
   with st.expander("🔧 Advanced Controls", expanded=False):
       
       col1, col2 = st.columns(2)
       
       with col1:
           st.subheader("Manual Actions")
           
           if config.is_simulation_mode():
               current_price = status.get('current_price', 0)
               
               if st.button("🔄 Simulate Buy"):
                   if current_price:
                       try:
                           amount = 50  # Default $50 buy
                           order = simulator.simulate_market_buy(config.get_trading_symbol(), amount)
                           if order:
                               position_manager.add_position(config.get_trading_symbol(), current_price, amount / current_price)
                               st.success(f"✅ Simulated buy: ${amount} worth of BTC")
                           else:
                               st.error("❌ Failed to simulate buy")
                       except Exception as e:
                           st.error(f"❌ Error: {str(e)}")
               
               if st.button("💰 Simulate Sell All"):
                   try:
                       btc_balance = simulator.get_btc_balance()
                       if btc_balance > 0:
                           order = simulator.simulate_market_sell(config.get_trading_symbol(), btc_balance)
                           if order:
                               # Close all positions
                               for pos in position_manager.get_open_positions():
                                   position_manager.close_position(pos, current_price)
                               st.success(f"✅ Simulated sell: {btc_balance:.6f} BTC")
                           else:
                               st.error("❌ Failed to simulate sell")
                       else:
                           st.warning("⚠️ No BTC to sell")
                   except Exception as e:
                       st.error(f"❌ Error: {str(e)}")
       
       with col2:
           st.subheader("Order Management")
           
           if st.button("📋 Show Pending Orders"):
               show_pending_orders_details()
           
           if st.button("❌ Cancel All Orders"):
               cancel_all_orders_action()
           
           if st.button("💾 Export Data"):
               export_trading_data()

def show_pending_orders_details():
   """Show detailed pending orders information"""
   st.subheader("📋 Pending Orders Details")
   
   pending_details = trading_engine.get_pending_orders_details()
   
   # Buy orders
   buy_orders = pending_details['buy_orders']
   if buy_orders:
       st.write("**Pending Buy Orders:**")
       for order_data in buy_orders:
           order = order_data['order']
           st.write(f"• {order['id']}: ${order_data['amount_usdt']:.2f} at ${order_data['trigger_price']:.2f}")
   else:
       st.info("No pending buy orders")
   
   # Sell orders
   sell_orders = pending_details['sell_orders']
   if sell_orders:
       st.write("**Pending Sell Orders:**")
       for order_data in sell_orders:
           order = order_data['order']
           st.write(f"• {order['id']}: {order['amount']:.6f} BTC at ${order_data['target_price']:.2f}")
   else:
       st.info("No pending sell orders")

def cancel_all_orders_action():
   """Cancel all pending orders"""
   if st.button("⚠️ Confirm Cancel All", type="secondary"):
       try:
           trading_engine._cancel_all_pending_orders()
           st.success("✅ All pending orders cancelled")
           st.rerun()
       except Exception as e:
           st.error(f"❌ Error cancelling orders: {str(e)}")

def render_emergency_controls():
   """Render emergency control options"""
   with st.expander("🚨 Emergency Controls", expanded=False):
       st.warning("⚠️ **Emergency Controls** - Use only when necessary!")
       
       col1, col2 = st.columns(2)
       
       with col1:
           if st.button("🛑 Emergency Stop", type="secondary"):
               st.error("🚨 Emergency stop activated!")
               try:
                   trading_engine.force_stop()
                   logger.warning("Emergency stop activated via UI")
                   st.rerun()
               except Exception as e:
                   st.error(f"❌ Emergency stop failed: {str(e)}")
       
       with col2:
           if not config.is_simulation_mode():
               if st.button("⚠️ Market Sell All", type="secondary"):
                   show_emergency_sell_dialog()

def show_emergency_sell_dialog():
   """Show emergency sell confirmation dialog"""
   st.error("🚨 **EMERGENCY SELL ALL POSITIONS**")
   st.warning("This will immediately sell ALL BTC at market price!")
   
   if st.button("🔴 CONFIRM EMERGENCY SELL", type="primary"):
       try:
           from core.kucoin_client import kucoin_client
           btc_balance = kucoin_client.get_btc_balance()
           
           if btc_balance > 0:
               order = kucoin_client.place_market_sell_order(config.get_trading_symbol(), btc_balance)
               if order:
                   st.success(f"✅ Emergency sell executed: {btc_balance:.6f} BTC")
                   logger.warning(f"Emergency sell executed via UI: {btc_balance:.6f} BTC")
                   # Close all positions
                   for pos in position_manager.get_open_positions():
                       position_manager.close_position(pos, order.get('price', 0))
               else:
                   st.error("❌ Emergency sell failed")
           else:
               st.warning("⚠️ No BTC to sell")
               
       except Exception as e:
           st.error(f"❌ Emergency sell error: {str(e)}")
           logger.error(f"Emergency sell error: {str(e)}")

def export_trading_data():
   """Export trading data"""
   try:
       import json
       from datetime import datetime
       
       # Collect all data
       export_data = {
           'export_timestamp': datetime.now().isoformat(),
           'mode': 'simulation' if config.is_simulation_mode() else 'live',
           'secrets_source': config.get_secrets_source(),
           'positions': [pos.to_dict() for pos in position_manager.get_open_positions()],
           'closed_positions': [pos.to_dict() for pos in position_manager.get_closed_positions()],
           'bot_status': trading_engine.get_status(),
           'pending_orders': trading_engine.get_pending_orders_details()
       }
       
       if config.is_simulation_mode():
           export_data['simulation_data'] = {
               'balances': simulator.balances,
               'trades': simulator.get_trade_history(),
               'profit_loss': simulator.get_profit_loss(),
               'pending_orders_summary': simulator.get_pending_orders_summary()
           }
       
       # Create download
       json_data = json.dumps(export_data, indent=2, default=str)
       
       st.download_button(
           label="📥 Download Trading Data",
           data=json_data,
           file_name=f"crypto_bot_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
           mime="application/json"
       )
       
       st.success("✅ Data export ready!")
       
   except Exception as e:
       st.error(f"❌ Export failed: {str(e)}")