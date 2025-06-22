import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import time
import sys
from datetime import datetime, timedelta
from bot import TradingBot

# Page config
st.set_page_config(
    page_title="Crypto Profit Bot",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
if 'bot' not in st.session_state:
    st.session_state.bot = None
if 'live_access_validated' not in st.session_state:
    st.session_state.live_access_validated = False
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True

def init_bot(simulation: bool = True):
    """Initialize trading bot"""
    try:
        if simulation:
            initial_balance = float(st.secrets.get("api_credentials", {}).get("initial_balance", 50))
            return TradingBot(simulation=True, initial_balance=initial_balance)
        else:
            # Live trading
            creds = st.secrets["api_credentials"]
            return TradingBot(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                api_passphrase=creds["api_passphrase"],
                sandbox=True,  # Use sandbox for safety
                simulation=False
            )
    except Exception as e:
        st.error(f"Failed to initialize bot: {e}")
        return None

def validate_live_access():
    """Validate live trading access"""
    if 'api_credentials' not in st.secrets:
        return False
    
    required_live_key = st.secrets["api_credentials"].get("live_trading_access_key")
    if not required_live_key:
        return True  # No access key required
    
    return st.session_state.live_access_validated

def render_live_access_gate():
    """Render live trading access validation"""
    st.error("🔐 **Live Trading Access Required**")
    
    required_key = st.secrets["api_credentials"].get("live_trading_access_key")
    
    with st.form("live_access_form"):
        access_key = st.text_input("Live Trading Access Key", type="password")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.form_submit_button("🔓 Unlock Live Trading"):
                if access_key == required_key:
                    st.session_state.live_access_validated = True
                    st.success("✅ Access granted!")
                    st.rerun()
                else:
                    st.error("❌ Invalid access key")
        
        with col2:
            if st.form_submit_button("🔄 Use Simulation Instead"):
                st.session_state.bot = init_bot(simulation=True)
                st.rerun()

def render_sidebar():
    """Render sidebar controls"""
    st.sidebar.title("🤖 Crypto Bot")
    
    # Auto-refresh toggle
    st.session_state.auto_refresh = st.sidebar.checkbox(
        "🔄 Auto Refresh", 
        value=st.session_state.auto_refresh,
        help="Automatically refresh when bot is running"
    )
    
    st.sidebar.divider()
    
    # Mode selection
    mode = st.sidebar.radio(
        "Trading Mode",
        ["Simulation", "Live Trading"],
        help="Simulation uses virtual money, Live uses real money"
    )
    
    simulation_mode = mode == "Simulation"
    
    # Initialize bot if needed
    if st.session_state.bot is None:
        if simulation_mode:
            st.session_state.bot = init_bot(simulation=True)
        else:
            if validate_live_access():
                st.session_state.bot = init_bot(simulation=False)
            else:
                render_live_access_gate()
                return
    
    # Switch modes if needed
    if st.session_state.bot and st.session_state.bot.simulation != simulation_mode:
        if not simulation_mode and not validate_live_access():
            render_live_access_gate()
            return
        st.session_state.bot = init_bot(simulation=simulation_mode)
    
    if not st.session_state.bot:
        st.sidebar.error("Bot not initialized")
        return
    
    bot = st.session_state.bot
    status = bot.get_status()
    
    # Status display
    st.sidebar.divider()
    if status["status"] == "running":
        if status.get("pending_exit"):
            st.sidebar.warning("🟡 Looking for exit...")
        else:
            st.sidebar.success("🟢 Bot Running")
    else:
        st.sidebar.info("⚪ Bot Stopped")
    
    # Controls
    st.sidebar.divider()
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if status["status"] == "stopped":
            if st.button("🚀 Start", use_container_width=True):
                if bot.start():
                    st.success("Started!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to start")
        else:
            if st.button("⏹️ Stop", use_container_width=True):
                bot.stop()
                st.info("Stopping...")
                time.sleep(1)
                st.rerun()
    
    with col2:
        if st.button("🛑 Force Stop", use_container_width=True):
            bot.force_stop()
            st.warning("Force stopped")
            time.sleep(1)
            st.rerun()
    
    # Settings
    st.sidebar.divider()
    st.sidebar.subheader("⚙️ Settings")
    
    # Profit margin
    current_margin = status["settings"]["profit_margin"]
    new_margin = st.sidebar.number_input(
        "Profit Margin (%)",
        min_value=0.1,
        max_value=5.0,
        value=current_margin,
        step=0.1,
        format="%.1f",
        help="Target profit percentage per trade"
    )
    
    if abs(new_margin - current_margin) > 0.05:
        if st.sidebar.button("💰 Update Margin"):
            if bot.set_profit_margin(new_margin):
                st.success(f"Margin set to {new_margin:.1f}%")
                st.rerun()
    
    # Quick stats
    st.sidebar.divider()
    st.sidebar.metric("Current Price", f"${status['current_price']:,.2f}" if status['current_price'] else "N/A")
    st.sidebar.metric("USDT Balance", f"${status['balances']['USDT']:.2f}")
    st.sidebar.metric("BTC Balance", f"{status['balances']['BTC']:.6f}")
    
    positions = status['positions']
    st.sidebar.metric(
        "Positions", 
        f"{positions['count']}/{positions['max_positions']}",
        help=f"Profitable: {positions['profitable_count']}"
    )
    
    if status['pnl']['unrealized_usd'] != 0:
        st.sidebar.metric(
            "Unrealized P&L", 
            f"${status['pnl']['unrealized_usd']:+.2f}",
            delta=f"{status['pnl']['unrealized_percent']:+.2f}%"
        )
    
    # Portfolio value for simulation
    if bot.simulation and status['portfolio']['total_value'] > 0:
        st.sidebar.metric(
            "Portfolio Value",
            f"${status['portfolio']['total_value']:.2f}",
            delta=f"${status['portfolio']['total_return']:+.2f}"
        )
    
    # Advanced controls
    st.sidebar.divider()
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🔄 Reset", use_container_width=True):
            bot.reset()
            st.success("Reset!")
            st.rerun()
    
    with col2:
        if st.button("🗑️ Cancel Orders", use_container_width=True):
            if bot.cancel_all_orders():
                st.success("Orders cancelled!")
                st.rerun()

def render_dashboard():
    """Render main dashboard"""
    if not st.session_state.bot:
        st.error("Bot not initialized")
        return
    
    bot = st.session_state.bot
    status = bot.get_status()
    
    # Header
    st.title("🤖 Crypto Profit Bot")
    
    mode_color = "🟢" if bot.simulation else "🔴"
    mode_text = "SIMULATION" if bot.simulation else "LIVE TRADING"
    st.markdown(f"**Mode:** {mode_color} {mode_text}")
    
    # Strategy info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"📊 **Strategy:** Smart Limit Orders")
    with col2:
        st.info(f"🎯 **Target Profit:** {status['settings']['profit_margin']:.1f}%")
    with col3:
        st.info(f"📉 **Buy Trigger:** {status['settings']['buy_trigger_percent']:.1f}% drop")
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Current Price", f"${status['current_price']:,.2f}" if status['current_price'] else "N/A")
    
    with col2:
        st.metric("USDT Balance", f"${status['balances']['USDT']:.2f}")
    
    with col3:
        st.metric("BTC Holdings", f"{status['balances']['BTC']:.6f}")
    
    with col4:
        positions = status['positions']
        profitable_text = f" ({positions['profitable_count']} profitable)" if positions['count'] > 0 else ""
        st.metric("Open Positions", f"{positions['count']}{profitable_text}")
    
    # P&L Section
    if status['pnl']['unrealized_usd'] != 0 or (bot.simulation and status['portfolio']['total_return'] != 0):
        st.divider()
        
        if bot.simulation:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Portfolio Value",
                    f"${status['portfolio']['total_value']:.2f}",
                    help="Total value of USDT + BTC holdings"
                )
            
            with col2:
                st.metric(
                    "Total Return",
                    f"${status['portfolio']['total_return']:+.2f}",
                    delta=f"{(status['portfolio']['total_return']/status['portfolio']['initial_value'])*100:+.2f}%"
                )
            
            with col3:
                st.metric(
                    "Unrealized P&L",
                    f"${status['pnl']['unrealized_usd']:+.2f}",
                    delta=f"{status['pnl']['unrealized_percent']:+.2f}%"
                )
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    "Unrealized P&L",
                    f"${status['pnl']['unrealized_usd']:+.2f}",
                    delta=f"{status['pnl']['unrealized_percent']:+.2f}%"
                )
            
            with col2:
                if status['positions']['count'] > 0:
                    st.metric("Avg Buy Price", f"${status['positions']['avg_buy_price']:,.2f}")

def render_price_chart():
   """Render price chart with position markers"""
   if not st.session_state.bot:
       return
   
   st.subheader("📈 Smart Order Execution")
   
   bot = st.session_state.bot
   current_price = bot.last_price or bot.client.get_current_price()
   
   if not current_price:
       st.warning("No price data available")
       return
   
   # Generate sample price data (in real implementation, use historical data)
   import numpy as np
   
   times = pd.date_range(end=datetime.now(), periods=100, freq='5min')
   np.random.seed(42)
   price_changes = np.cumsum(np.random.normal(0, 0.001, 100))
   prices = [current_price * (1 + change) for change in price_changes]
   
   fig = go.Figure()
   
   # Price line
   fig.add_trace(go.Scatter(
       x=times,
       y=prices,
       mode='lines',
       name='BTC Price',
       line=dict(color='orange', width=2)
   ))
   
   # Position markers
   positions = bot.get_positions_detail()
   if positions:
       buy_prices = [pos['buy_price'] for pos in positions]
       buy_times = [datetime.fromtimestamp(pos['buy_timestamp']) for pos in positions]
       
       fig.add_trace(go.Scatter(
           x=buy_times,
           y=buy_prices,
           mode='markers',
           name='Smart Buy Orders',
           marker=dict(color='green', size=10, symbol='triangle-up'),
           hovertemplate='<b>SMART BUY</b><br>Price: %{y:$,.2f}<br>Time: %{x}<extra></extra>'
       ))
       
       # Sell target lines for each position
       for pos in positions:
           target_price = pos['target_price']
           color = "green" if pos['is_profitable'] else "orange"
           fig.add_hline(
               y=target_price,
               line_dash="dot",
               line_color=color,
               opacity=0.5,
               annotation_text=f"Target: ${target_price:,.2f}"
           )
   
   # Current price line
   fig.add_hline(
       y=current_price,
       line_color="orange",
       line_width=3,
       annotation_text=f"Current: ${current_price:,.2f}"
   )
   
   # Market depth indicator
   try:
       spread_info = bot.client.get_bid_ask_spread()
       if spread_info:
           fig.add_hline(
               y=spread_info['bid'],
               line_dash="dash",
               line_color="blue",
               opacity=0.3,
               annotation_text=f"Bid: ${spread_info['bid']:,.2f}"
           )
           fig.add_hline(
               y=spread_info['ask'],
               line_dash="dash",
               line_color="red",
               opacity=0.3,
               annotation_text=f"Ask: ${spread_info['ask']:,.2f}"
           )
   except:
       pass
   
   fig.update_layout(
       title="BTC Price with Smart Order Positions",
       xaxis_title="Time",
       yaxis_title="Price (USD)",
       height=400,
       showlegend=True
   )
   
   st.plotly_chart(fig, use_container_width=True)

def render_positions_table():
   """Render detailed positions table"""
   if not st.session_state.bot:
       return
   
   bot = st.session_state.bot
   positions = bot.get_positions_detail()
   
   if not positions:
       st.info("No open positions")
       return
   
   st.subheader("📊 Smart Order Positions")
   
   position_data = []
   for pos in positions:
       status_icon = "✅" if pos['is_profitable'] else "⏳"
       status_text = "Ready to Sell" if pos['is_profitable'] else "Waiting for Profit"
       
       position_data.append({
           "Position": pos['position_id'],
           "Size (BTC)": f"{pos['size']:.6f}",
           "Buy Price": f"${pos['buy_price']:,.2f}",
           "Target Price": f"${pos['target_price']:,.2f}",
           "Current P&L": f"${pos['current_profit_usd']:+.2f}",
           "P&L %": f"{pos['current_profit_percent']:+.2f}%",
           "Status": f"{status_icon} {status_text}",
           "Sell Order": "✅" if pos['sell_order_id'] else "❌"
       })
   
   df = pd.DataFrame(position_data)
   st.dataframe(df, use_container_width=True, hide_index=True)
   
   # Position summary
   profitable_count = sum(1 for pos in positions if pos['is_profitable'])
   total_count = len(positions)
   
   col1, col2, col3 = st.columns(3)
   with col1:
       st.metric("Total Positions", total_count)
   with col2:
       st.metric("Profitable", f"{profitable_count}/{total_count}")
   with col3:
       if total_count > 0:
           avg_profit = sum(pos['current_profit_percent'] for pos in positions) / total_count
           st.metric("Avg P&L", f"{avg_profit:+.2f}%")

def render_order_status():
   """Render open orders status"""
   if not st.session_state.bot:
       return
   
   st.subheader("📋 Open Orders")
   
   try:
       open_orders = st.session_state.bot.get_open_orders()
       
       if not open_orders:
           st.info("No open orders")
           return
       
       order_data = []
       for order in open_orders:
           side_icon = "🟢" if order['side'] == 'buy' else "🔴"
           
           order_data.append({
               "Order ID": order['id'][:12] + "...",
               "Side": f"{side_icon} {order['side'].upper()}",
               "Size": f"{float(order['size']):.6f}",
               "Price": f"${float(order['price']):,.2f}",
               "Status": order.get('status', 'active').title()
           })
       
       df = pd.DataFrame(order_data)
       st.dataframe(df, use_container_width=True, hide_index=True)
       
   except Exception as e:
       st.error(f"Error fetching orders: {e}")

def render_trade_history():
   """Render trade history"""
   if not st.session_state.bot:
       return
   
   st.subheader("📜 Trade History")
   
   trades = st.session_state.bot.get_trade_history()
   
   if not trades:
       st.info("No trades yet")
       return
   
   # Show last 10 trades
   recent_trades = trades[-10:] if len(trades) > 10 else trades
   
   trade_data = []
   for trade in reversed(recent_trades):
       side_icon = "🟢" if trade["side"] == "buy" else "🔴"
       
       trade_data.append({
           "Time": datetime.fromtimestamp(trade["timestamp"]).strftime("%H:%M:%S"),
           "Side": f"{side_icon} {trade['side'].upper()}",
           "Size": f"{trade['size']:.6f}",
           "Price": f"${trade['price']:,.2f}",
           "Total": f"${trade['funds']:.2f}",
           "Fee": f"${trade['fee']:.2f}"
       })
   
   if trade_data:
       df = pd.DataFrame(trade_data)
       st.dataframe(df, use_container_width=True, hide_index=True)
       
       # Trade summary
       if len(trades) > 1:
           col1, col2, col3 = st.columns(3)
           
           buy_trades = [t for t in trades if t["side"] == "buy"]
           sell_trades = [t for t in trades if t["side"] == "sell"]
           total_fees = sum(t.get("fee", 0) for t in trades)
           
           with col1:
               st.metric("Total Trades", len(trades))
           with col2:
               st.metric("Buy/Sell", f"{len(buy_trades)}/{len(sell_trades)}")
           with col3:
               st.metric("Total Fees", f"${total_fees:.2f}")

def render_performance_chart():
   """Render performance chart for simulation"""
   if not st.session_state.bot or not st.session_state.bot.simulation:
       return
   
   st.subheader("📈 Portfolio Performance")
   
   trades = st.session_state.bot.get_trade_history()
   if not trades:
       st.info("No trades to show performance")
       return
   
   # Calculate portfolio value over time
   performance_data = []
   balance = st.session_state.bot.client.initial_balance
   btc_holdings = 0
   
   for trade in trades:
       if trade["side"] == "buy":
           balance -= trade["funds"]
           btc_holdings += trade["size"]
       else:
           balance += trade["funds"] - trade["fee"]
           btc_holdings -= trade["size"]
       
       portfolio_value = balance + (btc_holdings * trade["price"])
       
       performance_data.append({
           "time": datetime.fromtimestamp(trade["timestamp"]),
           "portfolio_value": portfolio_value,
           "trade_side": trade["side"],
           "price": trade["price"]
       })
   
   if performance_data:
       df = pd.DataFrame(performance_data)
       
       fig = go.Figure()
       
       # Portfolio value line
       fig.add_trace(go.Scatter(
           x=df["time"],
           y=df["portfolio_value"],
           mode='lines+markers',
           name='Portfolio Value',
           line=dict(color='blue', width=2),
           hovertemplate='<b>Portfolio Value</b><br>%{y:$,.2f}<br>%{x}<extra></extra>'
       ))
       
       # Mark trades
       buys = df[df["trade_side"] == "buy"]
       sells = df[df["trade_side"] == "sell"]
       
       if not buys.empty:
           fig.add_trace(go.Scatter(
               x=buys["time"],
               y=buys["portfolio_value"],
               mode='markers',
               name='Smart Buy',
               marker=dict(color='green', size=8, symbol='triangle-up'),
               hovertemplate='<b>SMART BUY</b><br>Portfolio: %{y:$,.2f}<extra></extra>'
           ))
       
       if not sells.empty:
           fig.add_trace(go.Scatter(
               x=sells["time"],
               y=sells["portfolio_value"],
               mode='markers',
               name='Smart Sell',
               marker=dict(color='red', size=8, symbol='triangle-down'),
               hovertemplate='<b>SMART SELL</b><br>Portfolio: %{y:$,.2f}<extra></extra>'
           ))
       
       # Initial balance line
       initial_balance = st.session_state.bot.client.initial_balance
       fig.add_hline(
           y=initial_balance, 
           line_dash="dash", 
           line_color="gray", 
           annotation_text=f"Initial: ${initial_balance}"
       )
       
       fig.update_layout(
           title="Smart Trading Performance Over Time",
           xaxis_title="Time",
           yaxis_title="Portfolio Value (USD)",
           height=400
       )
       
       st.plotly_chart(fig, use_container_width=True)
       
       # Performance metrics
       current_value = df["portfolio_value"].iloc[-1]
       total_return = current_value - initial_balance
       return_pct = (total_return / initial_balance) * 100
       
       col1, col2, col3 = st.columns(3)
       with col1:
           st.metric("Total Return", f"${total_return:+.2f}", delta=f"{return_pct:+.2f}%")
       with col2:
           st.metric("Current Value", f"${current_value:.2f}")
       with col3:
           total_trades = len(trades)
           st.metric("Total Trades", total_trades)

def render_market_info():
   """Render market information and spread data"""
   if not st.session_state.bot:
       return
   
   st.subheader("📊 Market Information")
   
   try:
       spread_info = st.session_state.bot.client.get_bid_ask_spread()
       
       if spread_info:
           col1, col2, col3, col4 = st.columns(4)
           
           with col1:
               st.metric("Best Bid", f"${spread_info['bid']:,.2f}")
           
           with col2:
               st.metric("Best Ask", f"${spread_info['ask']:,.2f}")
           
           with col3:
               st.metric("Spread", f"${spread_info['spread']:.2f}")
           
           with col4:
               st.metric("Spread %", f"{spread_info['spread_percent']:.3f}%")
           
           # Strategy explanation
           st.info("""
           💡 **Smart Order Strategy:**
           - **Buy orders** placed just above highest bid (maker fee: 0.1%)
           - **Sell orders** placed just below lowest ask (maker fee: 0.1%)
           - **No slippage** - exact price execution guaranteed
           - **Better fees** compared to market orders (taker fee: 0.1%)
           """)
       else:
           st.warning("Unable to fetch market depth data")
           
   except Exception as e:
       st.error(f"Error fetching market data: {e}")

def main():
   """Main application"""
   # Custom CSS
   st.markdown("""
   <style>
   .metric-container {
       background-color: #f0f2f6;
       padding: 1rem;
       border-radius: 0.5rem;
       margin: 0.5rem 0;
   }
   .success-box {
       background-color: #d4edda;
       border-left: 4px solid #28a745;
       padding: 0.75rem;
       margin: 1rem 0;
   }
   .warning-box {
       background-color: #fff3cd;
       border-left: 4px solid #ffc107;
       padding: 0.75rem;
       margin: 1rem 0;
   }
   </style>
   """, unsafe_allow_html=True)
   
   # Check if secrets are configured
   try:
       if 'api_credentials' not in st.secrets:
           st.error("❌ Streamlit secrets not configured")
           st.markdown("""
           **Setup Required:**
           
           Create `.streamlit/secrets.toml` with:
           ```toml
           [api_credentials]
           api_key = "your_kucoin_api_key"
           api_secret = "your_kucoin_api_secret"
           api_passphrase = "your_kucoin_api_passphrase"
           initial_balance = 50
           live_trading_access_key = "your_secure_key"
           ```
           """)
           st.stop()
   except Exception as e:
       st.error(f"Configuration error: {e}")
       st.stop()
   
   # Sidebar
   render_sidebar()
   
   # Main content
   if st.session_state.bot:
       # Auto-refresh if running and enabled
       if (st.session_state.bot.status == "running" and 
           st.session_state.auto_refresh):
           time.sleep(3)
           st.rerun()
       
       # Dashboard
       render_dashboard()
       
       st.divider()
       
       # Market info
       render_market_info()
       
       st.divider()
       
       # Charts and tables in tabs
       tab1, tab2, tab3 = st.tabs(["📊 Positions & Orders", "📈 Performance", "📜 History"])
       
       with tab1:
           col1, col2 = st.columns([2, 1])
           
           with col1:
               render_price_chart()
           
           with col2:
               render_positions_table()
               st.divider()
               render_order_status()
       
       with tab2:
           if st.session_state.bot.simulation:
               render_performance_chart()
           else:
               st.info("Performance tracking available in simulation mode")
       
       with tab3:
           render_trade_history()
       
       # Footer
       st.divider()
       col1, col2, col3, col4 = st.columns(4)
       
       with col1:
           st.caption("🤖 Smart Crypto Bot v3.0")
       
       with col2:
           mode = "SIM" if st.session_state.bot.simulation else "LIVE"
           st.caption(f"Mode: {mode}")
       
       with col3:
           st.caption(f"Strategy: Smart Limit Orders")
       
       with col4:
           st.caption(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

def cli_mode():
   """CLI mode for headless operation"""
   if len(sys.argv) > 1 and sys.argv[1] == "--cli":
       print("🚀 Starting Smart Crypto Bot in CLI mode...")
       
       try:
           bot = TradingBot(simulation=True)
           
           if "--start" in sys.argv:
               if bot.start():
                   print("✅ Bot started successfully")
                   
                   while True:
                       status = bot.get_status()
                       positions = status['positions']
                       pnl = status['pnl']
                       
                       print(f"\n📊 Status: {status['status']}")
                       print(f"💰 Price: ${status['current_price']:,.2f}")
                       print(f"📈 Positions: {positions['count']} ({positions['profitable_count']} profitable)")
                       print(f"💵 P&L: ${pnl['unrealized_usd']:+.2f} ({pnl['unrealized_percent']:+.2f}%)")
                       print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
                       
                       time.sleep(30)
               else:
                   print("❌ Failed to start bot")
           else:
               print("Use --start to begin trading")
               print("Example: python main.py --cli --start")
               
       except KeyboardInterrupt:
           print("\n🛑 Shutting down...")
           if 'bot' in locals():
               bot.force_stop()
       except Exception as e:
           print(f"❌ Error: {e}")
       
       sys.exit(0)

if __name__ == "__main__":
   cli_mode()  # Check for CLI mode first
   main()      # Otherwise run Streamlit app