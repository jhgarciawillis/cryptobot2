import streamlit as st
import time
import threading
from datetime import datetime
import os

# Configure Streamlit page
st.set_page_config(
    page_title="Crypto Profit Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import components
from components.dashboard import render_dashboard
from components.controls import render_controls
from components.charts import render_performance_chart, render_profit_distribution, render_price_analysis, render_risk_metrics
from core.trading_engine import trading_engine, BotState
from utils.config import config
from utils.logger import logger
from utils.helpers import ensure_directory

# Initialize directories
ensure_directory("data")
ensure_directory("data/logs")
ensure_directory("config")

def initialize_app():
    """Initialize the Streamlit application"""
    try:
        # Initialize session state
        if 'last_update' not in st.session_state:
            st.session_state.last_update = datetime.now()
        
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = True
        
        if 'refresh_interval' not in st.session_state:
            st.session_state.refresh_interval = config.get('ui.refresh_interval', 5)
        
        # Check secrets configuration
        validate_secrets_setup()
        
        logger.info("Streamlit app initialized")
        return True
        
    except Exception as e:
        st.error(f"Failed to initialize app: {str(e)}")
        logger.error(f"App initialization error: {str(e)}")
        return False

def validate_secrets_setup():
    """Validate Streamlit secrets setup"""
    try:
        secrets_source = config.get_secrets_source()
        
        if secrets_source == "streamlit_secrets":
            # Validate required secrets
            required_keys = ['api_key', 'api_secret', 'api_passphrase']
            missing_keys = []
            
            for key in required_keys:
                if not config.get_secret(key):
                    missing_keys.append(key)
            
            if missing_keys:
                st.error(f"❌ Missing required secrets: {', '.join(missing_keys)}")
                show_secrets_setup_guide()
                return False
            
            st.success("✅ Streamlit secrets configured correctly")
            return True
            
        else:
            st.warning("⚠️ Using environment variables for secrets. Consider using Streamlit secrets for better security.")
            return True
            
    except Exception as e:
        st.error(f"❌ Error validating secrets: {str(e)}")
        return False

def show_secrets_setup_guide():
    """Show guide for setting up Streamlit secrets"""
    st.subheader("🔧 Streamlit Secrets Setup Required")
    
    st.markdown("""
    **To use this bot, you need to configure Streamlit secrets:**
    
    1. **Create a `.streamlit/secrets.toml` file** in your project root
    2. **Add your KuCoin API credentials:**
    
    ```toml
    [api_credentials]
    api_key = "your_kucoin_api_key"
    api_secret = "your_kucoin_api_secret"
    api_passphrase = "your_kucoin_api_passphrase"
    live_trading_access_key = "your_secure_access_key"
    initial_balance = 50
    ```
    
    3. **Get your KuCoin API credentials:**
    - Log into KuCoin
    - Go to API Management
    - Create new API with "General" and "Spot Trading" permissions
    - **Never enable "Withdrawal" permissions**
    
    4. **Set a secure live trading access key:**
    - This is your own security key to prevent unauthorized live trading
    - Use a strong, unique password
    - Only needed if you plan to use live trading mode
    
    5. **Restart the Streamlit app** after creating the secrets file
    """)
    
    st.info("💡 **Tip**: You can start with simulation mode, which doesn't require API credentials!")

def render_sidebar():
    """Render the sidebar with configuration and settings"""
    st.sidebar.title("🤖 Crypto Bot")
    
    # Mode indicator
    mode = "SIMULATION" if config.is_simulation_mode() else "LIVE TRADING"
    mode_color = "🟢" if config.is_simulation_mode() else "🔴"
    st.sidebar.markdown(f"**Mode:** {mode_color} {mode}")
    
    # Live access status
    if not config.is_simulation_mode():
        if config.requires_live_access_key():
            if config.is_live_access_validated():
                st.sidebar.success("🔓 Live access validated")
            else:
                st.sidebar.error("🔐 Live access required")
        else:
            st.sidebar.info("🔓 No access key required")
    
    # Connection status
    if config.is_simulation_mode():
        st.sidebar.success("✅ Simulation Mode Active")
    else:
        try:
            if config.validate_secrets():
                from core.kucoin_client import kucoin_client
                if kucoin_client.is_connected:
                    st.sidebar.success("✅ KuCoin Connected")
                else:
                    st.sidebar.error("❌ KuCoin Disconnected")
            else:
                st.sidebar.error("❌ API Credentials Missing")
        except Exception as e:
            st.sidebar.error(f"❌ Connection Error: {str(e)}")
    
    # Secrets source indicator
    secrets_source = config.get_secrets_source()
    if secrets_source == "streamlit_secrets":
        st.sidebar.info("🔑 Using Streamlit Secrets")
    else:
        st.sidebar.warning("🔑 Using Environment Variables")
    
    st.sidebar.divider()
    
    # Navigation
    st.sidebar.subheader("📊 Navigation")
    
    # Page selection
    page = st.sidebar.selectbox(
        "Choose View",
        ["Dashboard", "Performance", "Risk Analysis", "Settings"],
        key="page_selector"
    )
    
    st.sidebar.divider()
    
    # Auto-refresh settings
    st.sidebar.subheader("🔄 Auto Refresh")
    
    auto_refresh = st.sidebar.checkbox(
        "Enable Auto Refresh",
        value=st.session_state.auto_refresh,
        key="auto_refresh_checkbox"
    )
    
    if auto_refresh:
        refresh_interval = st.sidebar.slider(
            "Refresh Interval (seconds)",
            min_value=1,
            max_value=60,
            value=st.session_state.refresh_interval,
            key="refresh_interval_slider"
        )
        st.session_state.refresh_interval = refresh_interval
    
    st.session_state.auto_refresh = auto_refresh
    
    st.sidebar.divider()
    
    # Quick stats
    render_sidebar_stats()
    
    st.sidebar.divider()
    
    # Quick actions
    render_sidebar_actions()
    
    return page

def render_sidebar_stats():
    """Render quick stats in sidebar"""
    st.sidebar.subheader("📈 Quick Stats")
    
    try:
        status = trading_engine.get_status()
        
        # Bot status
        state = status['state']
        state_emoji = {
            'running': '🟢',
            'stopped': '⚪',
            'stopping': '🟡',
            'error': '🔴'
        }.get(state, '❓')
        
        st.sidebar.metric("Bot Status", f"{state_emoji} {state.title()}")
        
        # Current price
        current_price = status.get('current_price', 0)
        if current_price:
            st.sidebar.metric("BTC Price", f"${current_price:,.2f}")
        
        # Position count
        position_count = status.get('positions', {}).get('count', 0)
        st.sidebar.metric("Open Positions", position_count)
        
        # Pending orders
        pending_orders = status.get('pending_orders', {})
        total_pending = pending_orders.get('total_pending', 0)
        if total_pending > 0:
            st.sidebar.metric("Pending Orders", total_pending)
        
        # P&L
        if status.get('pnl'):
            unrealized = status['pnl']['unrealized']
            pnl_value = unrealized.get('absolute', 0)
            pnl_pct = unrealized.get('percentage', 0)
            
            pnl_color = "🟢" if pnl_value >= 0 else "🔴"
            st.sidebar.metric(
                "Unrealized P&L",
                f"{pnl_color} ${pnl_value:.2f}",
                delta=f"{pnl_pct:+.2f}%"
            )
        
    except Exception as e:
        st.sidebar.error(f"Stats error: {str(e)}")

def render_sidebar_actions():
    """Render quick actions in sidebar"""
    st.sidebar.subheader("⚡ Quick Actions")
    
    # Check access for live mode
    can_trade = True
    if not config.is_simulation_mode() and config.requires_live_access_key():
        can_trade = config.is_live_access_validated()
    
    if not can_trade:
        st.sidebar.warning("🔐 Live access required")
        return
    
    status = trading_engine.get_status()
    current_state = status['state']
    
    # Quick start/stop
    if current_state == 'stopped':
        if st.sidebar.button("🚀 Quick Start", use_container_width=True):
            with st.spinner("Starting..."):
                trading_engine.start_trading()
            st.rerun()
    elif current_state == 'running':
        if st.sidebar.button("⏹️ Quick Stop", use_container_width=True):
            trading_engine.stop_trading()
            st.rerun()
    
    # Emergency stop
    if current_state in ['running', 'stopping']:
        if st.sidebar.button("🛑 Emergency Stop", use_container_width=True, type="secondary"):
            trading_engine.force_stop()
            st.rerun()
    
    # Manual refresh
    if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
        st.rerun()

def render_main_content(page: str):
    """Render main content based on selected page"""
    
    if page == "Dashboard":
        render_dashboard_page()
    elif page == "Performance":
        render_performance_page()
    elif page == "Risk Analysis":
        render_risk_page()
    elif page == "Settings":
        render_settings_page()

def render_dashboard_page():
    """Render main dashboard page"""
    # Controls at the top
    render_controls()
    
    st.divider()
    
    # Main dashboard
    render_dashboard()

def render_performance_page():
    """Render performance analysis page"""
    st.title("📈 Performance Analysis")
    
    tab1, tab2 = st.tabs(["Portfolio Performance", "Trade Analysis"])
    
    with tab1:
        render_performance_chart()
    
    with tab2:
        render_profit_distribution()

def render_risk_page():
    """Render risk analysis page"""
    st.title("⚠️ Risk Analysis")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        render_price_analysis()
    
    with col2:
        render_risk_metrics()

def render_settings_page():
    """Render settings and configuration page"""
    st.title("⚙️ Settings & Configuration")
    
    # Trading parameters
    with st.expander("🎯 Trading Parameters", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"**Trading Symbol:** {config.get_trading_symbol()}")
            st.info(f"**Profit Margin:** {config.get_user_profit_margin()*100:.3f}%")
            st.info(f"**Buy Trigger:** {config.get_buy_trigger_percent():.1f}% drop")
            st.info(f"**Order Type:** {config.get_order_type_preference().title()}")
        
        with col2:
            st.info(f"**Min Trade Amount:** ${config.get('trading.min_trade_amount', 10)}")
            st.info(f"**Max Position Size:** {config.get('trading.max_position_size', 1.0) * 100:.0f}%")
            st.info(f"**Refresh Interval:** {config.get('ui.refresh_interval', 5)}s")
            st.info(f"**Mode:** {'Simulation' if config.is_simulation_mode() else 'Live Trading'}")
    
    # API Configuration
    with st.expander("🔌 API Configuration", expanded=False):
        secrets_source = config.get_secrets_source()
        
        if secrets_source == "streamlit_secrets":
            st.success("✅ Using Streamlit secrets for API credentials")
            
            if config.validate_secrets():
                st.success("✅ KuCoin API credentials configured")
                
                # Show which credentials are set (without revealing values)
                creds_status = []
                for cred in ['api_key', 'api_secret', 'api_passphrase']:
                    if config.get_secret(cred):
                        creds_status.append(f"✅ {cred}")
                    else:
                        creds_status.append(f"❌ {cred}")
                
                st.write("**Credential Status:**")
                for status in creds_status:
                    st.write(status)
                
                # Live access key status
                if config.get_secret('live_trading_access_key'):
                    st.info("🔐 Live trading access key configured")
                else:
                    st.warning("⚠️ Live trading access key not configured")
                
                st.info(f"**Sandbox Mode:** {'Yes' if config.is_sandbox_mode() else 'No'}")
            else:
                st.error("❌ KuCoin API credentials missing or incomplete")
        else:
            st.warning("⚠️ Using environment variables for API credentials")
            st.markdown("""
            **Required Environment Variables:**
            - `KUCOIN_API_KEY`
            - `KUCOIN_API_SECRET`
            - `KUCOIN_API_PASSPHRASE`
            - `LIVE_TRADING_ACCESS_KEY` (optional)
            """)
    
    # Security Settings
    with st.expander("🔐 Security Settings", expanded=False):
        st.subheader("Live Trading Access")
        
        if config.get_secret('live_trading_access_key'):
            st.success("✅ Live trading access key is configured")
            
            if not config.is_simulation_mode():
                if config.is_live_access_validated():
                    st.success("🔓 Live trading access is currently validated")
                else:
                    st.error("🔐 Live trading access validation required")
            else:
                st.info("ℹ️ Access key not required in simulation mode")
        else:
            st.warning("⚠️ No live trading access key configured")
            st.info("Anyone with access to this app can use live trading mode")
        
        st.markdown("""
        **Security Recommendations:**
        - Always use a strong, unique live trading access key
        - Never share your access key with unauthorized users
        - Regularly rotate your API credentials
        - Use IP restrictions on your KuCoin API keys
        - Monitor your trading activity regularly
        """)
    
    # Data Management
    with st.expander("💾 Data Management", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📤 Export Data", use_container_width=True):
                from components.controls import export_trading_data
                export_trading_data()
        
        with col2:
            if st.button("🗑️ Clear Data", use_container_width=True):
                if st.button("⚠️ Confirm Clear", type="secondary"):
                    trading_engine.reset_bot()
                    st.success("✅ Data cleared")
        
        with col3:
            if st.button("📋 View Logs", use_container_width=True):
                show_logs()
    
    # System Information
    with st.expander("ℹ️ System Information", expanded=False):
        st.info(f"**Streamlit Version:** {st.__version__}")
        st.info(f"**Config File:** {config.config_path}")
        st.info(f"**Secrets Source:** {secrets_source}")
        st.info(f"**Log Directory:** data/logs/")
        st.info(f"**Data Directory:** data/")

def show_logs():
    """Display recent logs"""
    st.subheader("📋 Recent Logs")
    
    try:
        import glob
        import os
        
        # Find most recent log file
        log_files = glob.glob("data/logs/*.log")
        if not log_files:
            st.warning("No log files found")
            return
        
        latest_log = max(log_files, key=os.path.getctime)
        
        # Read last 100 lines
        with open(latest_log, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-100:] if len(lines) > 100 else lines
        
        # Display in code block
        log_content = ''.join(recent_lines)
        st.code(log_content, language='text')
        
    except Exception as e:
        st.error(f"Error reading logs: {str(e)}")

def handle_auto_refresh():
    """Handle auto-refresh functionality"""
    if st.session_state.auto_refresh and trading_engine.state == BotState.RUNNING:
        # Auto refresh for running bot
        time.sleep(st.session_state.refresh_interval)
        st.rerun()

def main():
    """Main application entry point"""
    
    # Initialize app
    if not initialize_app():
        st.stop()
    
    # Custom CSS
    st.markdown("""
    <style>
    .metric-container {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    
    .status-running {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 0.75rem;
        margin: 1rem 0;
    }
    
    .status-stopped {
        background-color: #f8f9fa;
        border-left: 4px solid #6c757d;
        padding: 0.75rem;
        margin: 1rem 0;
    }
    
    .status-error {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 0.75rem;
        margin: 1rem 0;
    }
    
    .live-mode {
        background-color: #f8d7da;
        border: 2px solid #dc3545;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    
    .simulation-mode {
        background-color: #d4edda;
        border: 2px solid #28a745;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    try:
        # Render sidebar and get selected page
        page = render_sidebar()
        
        # Render main content
        render_main_content(page)
        
        # Footer
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.caption("🤖 Crypto Profit Bot v2.0")
        
        with col2:
            st.caption(f"Mode: {'SIM' if config.is_simulation_mode() else 'LIVE'}")
        
        with col3:
            st.caption(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
        
        with col4:
            if st.session_state.auto_refresh:
                st.caption(f"🔄 Auto-refresh: {st.session_state.refresh_interval}s")
        
        # Handle auto-refresh
        if st.session_state.auto_refresh:
            time.sleep(0.1)  # Small delay to prevent too frequent updates
            # Use a placeholder to auto-refresh
            placeholder = st.empty()
            
            # Auto-refresh timer
            if trading_engine.state == BotState.RUNNING:
                with placeholder.container():
                    time.sleep(st.session_state.refresh_interval)
                    st.rerun()
    
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        logger.error(f"Main app error: {str(e)}")
        
        # Show error details in expander
        with st.expander("Error Details", expanded=False):
            st.exception(e)

if __name__ == "__main__":
    main()