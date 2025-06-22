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
    current_margin = status["profit_margin"]
    new_margin = st.sidebar.number_input(
        "Profit Margin (%)",
        min_value=0.1,
        max_value=5.0,
        value=current_margin,
        step=0.1,
        format="%.1f"
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
    st.sidebar.metric("Open Positions", status['positions']['count'])
    
    if status['pnl']['unrealized_usd'] != 0:
        st.sidebar.metric(
            "Unrealized P&L", 
            f"${status['pnl']['unrealized_usd']:+.2f}",
            delta=f"{status['pnl']['unrealized_percent']:+.2f}%"
        )
    
    # Reset and export
    st.sidebar.divider()
    if st.sidebar.button("🔄 Reset Bot"):
        bot.reset()
        st.success("Bot reset!")
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
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Current Price", f"${status['current_price']:,.2f}" if status['current_price'] else "N/A")
    
    with col2:
        st.metric("USDT Balance", f"${status['balances']['USDT']:.2f}")
    
    with col3:
        st.metric("BTC Holdings", f"{status['balances']['BTC']:.6f}")
    
    with col4:
        st.metric("Open Positions", status['positions']['count'])
    
    # P&L Section
    if status['pnl']['unrealized_usd'] != 0:
        st.divider()
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Unrealized P&L",
                f"${status['pnl']['unrealized_usd']:+.2f}",
                delta=f"{status['pnl']['unrealized_percent']:+.2f}%"
            )
        
        with col2:
            if status['positions']['count'] > 0:
                st.metric("Avg Buy Price", f"${status['positions']['avg_buy_price']:,.2f}")
        
        with col3:
            if bot.simulation:
                total_value = bot.client.get_total_value()
                initial_balance = 50  # Default initial balance
                profit = total_value - initial_balance
                st.metric(
                    "Total Return",
                    f"${profit:+.2f}",
                    delta=f"{(profit/initial_balance)*100:+.2f}%"
                )

def render_price_chart():
    """Render price chart with position markers"""
    if not st.session_state.bot:
        return
    
    st.subheader("📈 Price Chart")
    
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
    if bot.positions:
        buy_prices = [pos.buy_price for pos in bot.positions]
        buy_times = [datetime.fromtimestamp(pos.timestamp) for pos in bot.positions]
        
        fig.add_trace(go.Scatter(
            x=buy_times,
            y=buy_prices,
            mode='markers',
            name='Buy Orders',
            marker=dict(color='green', size=10, symbol='triangle-up')
        ))
        
        # Sell target lines
        for pos in bot.positions:
            sell_target = bot._calculate_required_sell_price(pos.buy_price)
            fig.add_hline(
                y=sell_target,
                line_dash="dot",
                line_color="green",
                opacity=0.5,
                annotation_text=f"Target: ${sell_target:,.2f}"
            )
    
    # Current price line
    fig.add_hline(
        y=current_price,
        line_color="orange",
        line_width=3,
        annotation_text=f"Current: ${current_price:,.2f}"
    )
    
    fig.update_layout(
        title="BTC Price with Trading Positions",
        xaxis_title="Time",
        yaxis_title="Price (USD)",
        height=400,
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_positions_table():
    """Render positions table"""
    if not st.session_state.bot:
        return
    
    bot = st.session_state.bot
    
    if not bot.positions:
        st.info("No open positions")
        return
    
    st.subheader("📊 Open Positions")
    
    current_price = bot.last_price or bot.client.get_current_price()
    
    position_data = []
    for i, pos in enumerate(bot.positions, 1):
        profit_pct = pos.get_profit_at_price(current_price) if current_price else 0
        profit_usd = (current_price - pos.buy_price) * pos.size if current_price else 0
        sell_target = bot._calculate_required_sell_price(pos.buy_price)
        
        status_icon = "✅" if current_price and current_price >= sell_target else "⏳"
        
        position_data.append({
            "Position": i,
            "Size (BTC)": f"{pos.size:.6f}",
            "Buy Price": f"${pos.buy_price:,.2f}",
            "Target Price": f"${sell_target:,.2f}",
            "Current P&L": f"${profit_usd:+.2f}",
            "P&L %": f"{profit_pct:+.2f}%",
            "Status": f"{status_icon} {'Ready' if current_price and current_price >= sell_target else 'Waiting'}"
        })
    
    df = pd.DataFrame(position_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

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
    balance = 50  # Initial balance
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
            "trade_side": trade["side"]
        })
    
    if performance_data:
        df = pd.DataFrame(performance_data)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df["time"],
            y=df["portfolio_value"],
            mode='lines+markers',
            name='Portfolio Value',
            line=dict(color='blue', width=2)
        ))
        
        # Mark trades
        buys = df[df["trade_side"] == "buy"]
        sells = df[df["trade_side"] == "sell"]
        
        if not buys.empty:
            fig.add_trace(go.Scatter(
                x=buys["time"],
                y=buys["portfolio_value"],
                mode='markers',
                name='Buy',
                marker=dict(color='green', size=8, symbol='triangle-up')
            ))
        
        if not sells.empty:
            fig.add_trace(go.Scatter(
                x=sells["time"],
                y=sells["portfolio_value"],
                mode='markers',
                name='Sell',
                marker=dict(color='red', size=8, symbol='triangle-down')
            ))
        
        # Initial balance line
        fig.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="Initial: $50")
        
        fig.update_layout(
            title="Portfolio Value Over Time",
            xaxis_title="Time",
            yaxis_title="Value (USD)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)

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
        # Auto-refresh if running
        if st.session_state.bot.status == "running":
            time.sleep(2)
            st.rerun()
        
        # Dashboard
        render_dashboard()
        
        st.divider()
        
        # Charts and tables
        col1, col2 = st.columns([2, 1])
        
        with col1:
            render_price_chart()
            if st.session_state.bot.simulation:
                render_performance_chart()
        
        with col2:
            render_positions_table()
            render_trade_history()
        
        # Footer
        st.divider()
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.caption("🤖 Crypto Profit Bot v2.0")
        
        with col2:
            mode = "SIM" if st.session_state.bot.simulation else "LIVE"
            st.caption(f"Mode: {mode}")
        
        with col3:
            st.caption(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

def cli_mode():
    """CLI mode for headless operation"""
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        print("Starting in CLI mode...")
        
        # Simple CLI implementation
        try:
            bot = TradingBot(simulation=True)
            
            if "--start" in sys.argv:
                bot.start()
                
                while True:
                    status = bot.get_status()
                    print(f"Status: {status['status']} | Price: ${status['current_price']:,.2f} | Positions: {status['positions']['count']}")
                    time.sleep(30)
            else:
                print("Use --start to begin trading")
                
        except KeyboardInterrupt:
            print("\nShutting down...")
            if 'bot' in locals():
                bot.force_stop()
        
        sys.exit(0)

if __name__ == "__main__":
    cli_mode()  # Check for CLI mode first
    main()      # Otherwise run Streamlit app