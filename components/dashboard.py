import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List

from core.trading_engine import trading_engine, BotState
from core.position_manager import position_manager
from core.simulator import simulator
from utils.config import config
from utils.helpers import format_currency, format_percentage, calculate_required_sell_price

def render_dashboard():
    """Render the main dashboard"""
    
    # Get current status
    status = trading_engine.get_status()
    current_price = status.get('current_price', 0)
    
    # Header
    st.title("🤖 Crypto Profit Bot")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"**Mode:** {status['mode'].upper()}")
    with col2:
        st.markdown(f"**Symbol:** {status['symbol']}")
    with col3:
        st.markdown(f"**Current Price:** {format_currency(current_price)}")
    
    # Status indicator
    render_status_indicator(status)
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "USDT Balance", 
            format_currency(status['balances']['USDT']),
            help="Available USDT for trading"
        )
    
    with col2:
        st.metric(
            "BTC Balance", 
            f"{status['balances']['BTC']:.6f}",
            help="Current BTC holdings"
        )
    
    with col3:
        if status.get('pnl'):
            unrealized = status['pnl']['unrealized']
            st.metric(
                "Unrealized P&L",
                format_currency(unrealized['absolute']),
                delta=format_percentage(unrealized['percentage']),
                help="Profit/Loss on open positions"
            )
        else:
            st.metric("Unrealized P&L", format_currency(0))
    
    with col4:
        pending_orders = status.get('pending_orders', {})
        total_pending = pending_orders.get('total_pending', 0)
        st.metric(
            "Pending Orders",
            total_pending,
            delta=f"{pending_orders.get('buy_orders', 0)} buys, {pending_orders.get('sell_orders', 0)} sells",
            help="Orders waiting to be filled"
        )
    
    # Strategy settings display
    render_strategy_info(status)
    
    # Detailed sections
    col1, col2 = st.columns([2, 1])
    
    with col1:
        render_price_chart(status)
        render_trade_history()
    
    with col2:
        render_positions_summary(status)
        render_pending_orders_summary(status)

def render_status_indicator(status: Dict):
    """Render bot status indicator"""
    state = status['state']
    pending_exit = status.get('pending_exit', False)
    
    if state == 'running':
        if pending_exit:
            st.warning("🟡 **Looking for profitable exit opportunity...**")
        else:
            st.success("🟢 **Bot is running and monitoring market**")
    elif state == 'stopped':
        st.info("⚪ **Bot is stopped**")
    elif state == 'stopping':
        st.warning("🟡 **Bot is stopping...**")
    elif state == 'error':
        st.error("🔴 **Bot encountered an error**")
    
    # Last update time
    if status.get('last_check_time'):
        last_update = datetime.fromisoformat(status['last_check_time'])
        time_diff = datetime.now() - last_update
        if time_diff.total_seconds() > 30:
            st.warning(f"⚠️ Last update: {time_diff.total_seconds():.0f}s ago")

def render_strategy_info(status: Dict):
    """Render current strategy information"""
    st.subheader("📋 Strategy Configuration")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        profit_margin = status.get('profit_margin', 0.5)
        st.metric(
            "Profit Target",
            f"{profit_margin:.3f}%",
            help="Target profit margin per trade"
        )
    
    with col2:
        order_type = status.get('order_type', 'limit')
        st.metric(
            "Order Type",
            order_type.title(),
            help="Type of orders being placed"
        )
    
    with col3:
        buy_trigger = config.get_buy_trigger_percent()
        st.metric(
            "Buy Trigger",
            f"{buy_trigger:.1f}%",
            help="Price drop that triggers new buy"
        )
    
    with col4:
        if status.get('positions', {}).get('average_buy_price'):
            avg_buy = status['positions']['average_buy_price']
            required_sell = calculate_required_sell_price(avg_buy, trading_engine.user_profit_margin)
            st.metric(
                "Target Sell Price",
                format_currency(required_sell),
                help="Required price for profitable exit"
            )
        else:
            st.metric("Target Sell Price", "N/A")

def render_price_chart(status: Dict):
    """Render price chart with position markers"""
    st.subheader("📈 Price Chart & Orders")
    
    current_price = status.get('current_price', 0)
    if not current_price:
        st.warning("No price data available")
        return
    
    # Create sample price data for demonstration
    # In a real implementation, you'd fetch historical price data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    
    # Generate realistic price movement around current price
    import numpy as np
    np.random.seed(42)  # For consistent demo data
    price_changes = np.random.normal(0, 0.002, 100)  # 0.2% std deviation
    prices = [current_price * (1 + sum(price_changes[:i+1])) for i in range(100)]
    
    df = pd.DataFrame({
        'timestamp': dates,
        'price': prices
    })
    
    fig = go.Figure()
    
    # Add price line
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['price'],
        mode='lines',
        name='BTC Price',
        line=dict(color='orange', width=2)
    ))
    
    # Add position markers
    positions = position_manager.get_open_positions()
    if positions:
        buy_prices = [pos.buy_price for pos in positions]
        buy_times = [datetime.fromisoformat(pos.timestamp) for pos in positions]
        
        fig.add_trace(go.Scatter(
            x=buy_times,
            y=buy_prices,
            mode='markers',
            name='Buy Orders',
            marker=dict(color='green', size=10, symbol='triangle-up'),
            hovertemplate='<b>BUY</b><br>Price: %{y:$,.2f}<br>Time: %{x}<extra></extra>'
        ))
        
        # Add sell target lines for each position
        for pos in positions:
            sell_target = calculate_required_sell_price(pos.buy_price, trading_engine.user_profit_margin)
            fig.add_hline(
                y=sell_target,
                line_dash="dot",
                line_color="green",
                opacity=0.5,
                annotation_text=f"Sell Target: {format_currency(sell_target)}"
            )
    
    # Add pending order indicators
    pending_details = trading_engine.get_pending_orders_details()
    
    # Pending buy orders
    buy_orders = pending_details.get('buy_orders', [])
    if buy_orders:
        buy_prices_pending = [order['trigger_price'] for order in buy_orders]
        buy_times_pending = [datetime.now() for _ in buy_orders]  # Show at current time
        
        fig.add_trace(go.Scatter(
            x=buy_times_pending,
            y=buy_prices_pending,
            mode='markers',
            name='Pending Buys',
            marker=dict(color='blue', size=8, symbol='triangle-up-open'),
            hovertemplate='<b>PENDING BUY</b><br>Price: %{y:$,.2f}<extra></extra>'
        ))
    
    # Pending sell orders
    sell_orders = pending_details.get('sell_orders', [])
    if sell_orders:
        sell_prices_pending = [order['target_price'] for order in sell_orders]
        sell_times_pending = [datetime.now() for _ in sell_orders]
        
        fig.add_trace(go.Scatter(
            x=sell_times_pending,
            y=sell_prices_pending,
            mode='markers',
            name='Pending Sells',
            marker=dict(color='red', size=8, symbol='triangle-down-open'),
            hovertemplate='<b>PENDING SELL</b><br>Price: %{y:$,.2f}<extra></extra>'
        ))
    
    # Add current price line
    fig.add_hline(
        y=current_price,
        line_dash="solid",
        line_color="orange",
        line_width=3,
        annotation_text=f"Current: {format_currency(current_price)}"
    )
    
    fig.update_layout(
        title="BTC Price Movement with Trading Orders",
        xaxis_title="Time",
        yaxis_title="Price (USD)",
        height=400,
        showlegend=True,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_positions_summary(status: Dict):
    """Render positions summary"""
    st.subheader("📊 Open Positions")
    
    positions = position_manager.get_open_positions()
    current_price = status.get('current_price', 0)
    
    if not positions:
        st.info("No open positions")
        return
    
    # Positions table
    position_data = []
    for i, pos in enumerate(positions):
        profit_pct = 0
        profit_usd = 0
        sell_target = calculate_required_sell_price(pos.buy_price, trading_engine.user_profit_margin)
        
        if current_price and current_price > 0:
            profit_pct = ((current_price - pos.buy_price) / pos.buy_price) * 100
            profit_usd = (current_price - pos.buy_price) * pos.amount
        
        status_icon = "✅" if current_price >= sell_target else "⏳"
        target_profit = trading_engine.user_profit_margin * 100
        
        position_data.append({
            'Position': i + 1,
            'Amount (BTC)': f"{pos.amount:.6f}",
            'Buy Price': format_currency(pos.buy_price),
            'Sell Target': format_currency(sell_target),
            'Current P&L': format_currency(profit_usd),
            'P&L %': format_percentage(profit_pct),
            'Status': f'{status_icon} {"Ready" if current_price >= sell_target else f"Need +{target_profit:.3f}%"}'
        })
    
    df_positions = pd.DataFrame(position_data)
    st.dataframe(df_positions, use_container_width=True, hide_index=True)
    
    # Summary metrics
    total_btc = sum(pos.amount for pos in positions)
    avg_buy_price = position_manager.get_average_buy_price()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total BTC", f"{total_btc:.6f}")
    with col2:
        st.metric("Avg Buy Price", format_currency(avg_buy_price) if avg_buy_price else "N/A")
    with col3:
        profitable_count = len([pos for pos in positions if current_price >= calculate_required_sell_price(pos.buy_price, trading_engine.user_profit_margin)])
        st.metric("Profitable Positions", f"{profitable_count}/{len(positions)}")

def render_pending_orders_summary(status: Dict):
    """Render pending orders summary"""
    st.subheader("📋 Pending Orders")
    
    pending_details = trading_engine.get_pending_orders_details()
    buy_orders = pending_details.get('buy_orders', [])
    sell_orders = pending_details.get('sell_orders', [])
    
    if not buy_orders and not sell_orders:
        st.info("No pending orders")
        return
    
    # Buy orders
    if buy_orders:
        st.write("**Pending Buy Orders:**")
        buy_data = []
        for order_data in buy_orders:
            buy_data.append({
                'Amount (USDT)': f"${order_data['amount_usdt']:.2f}",
                'Trigger Price': format_currency(order_data['trigger_price']),
                'Time': datetime.fromisoformat(order_data['timestamp']).strftime('%H:%M:%S')
            })
        
        df_buys = pd.DataFrame(buy_data)
        st.dataframe(df_buys, use_container_width=True, hide_index=True)
    
    # Sell orders
    if sell_orders:
        st.write("**Pending Sell Orders:**")
        sell_data = []
        for order_data in sell_orders:
            order = order_data['order']
            sell_data.append({
                'Amount (BTC)': f"{order['amount']:.6f}",
                'Target Price': format_currency(order_data['target_price']),
                'Time': datetime.fromisoformat(order_data['timestamp']).strftime('%H:%M:%S')
            })
        
        df_sells = pd.DataFrame(sell_data)
        st.dataframe(df_sells, use_container_width=True, hide_index=True)
    
    # Summary
    total_buy_value = sum(order['amount_usdt'] for order in buy_orders)
    total_sell_btc = sum(order['order']['amount'] for order in sell_orders)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Buy Value", format_currency(total_buy_value))
    with col2:
        st.metric("Total Sell Amount", f"{total_sell_btc:.6f} BTC")

def render_trade_history():
    """Render trade history"""
    st.subheader("📜 Recent Trades")
    
    if config.is_simulation_mode():
        trades = simulator.get_trade_history()
    else:
        # For live trading, you might want to fetch from exchange
        trades = []
    
    if not trades:
        st.info("No trades yet")
        return
    
    # Show last 10 trades
    recent_trades = trades[-10:] if len(trades) > 10 else trades
    
    trade_data = []
    for trade in reversed(recent_trades):  # Most recent first
        side_color = "🟢" if trade['side'] == 'buy' else "🔴"
        order_type = trade.get('type', 'market').title()
        
        trade_data.append({
            'Time': datetime.fromisoformat(trade['timestamp']).strftime('%H:%M:%S'),
            'Side': f"{side_color} {trade['side'].upper()}",
            'Type': order_type,
            'Amount': f"{trade['amount']:.6f}",
            'Price': format_currency(trade['price']),
            'Total': format_currency(trade['cost']),
            'Fees': format_currency(trade.get('fees', 0))
        })
    
    df_trades = pd.DataFrame(trade_data)
    st.dataframe(df_trades, use_container_width=True, hide_index=True)
    
    # Trade statistics
    if len(trades) > 1:
        col1, col2, col3 = st.columns(3)
        
        buy_trades = [t for t in trades if t['side'] == 'buy']
        sell_trades = [t for t in trades if t['side'] == 'sell']
        
        with col1:
            st.metric("Total Trades", len(trades))
        with col2:
            st.metric("Buy/Sell Ratio", f"{len(buy_trades)}/{len(sell_trades)}")
        with col3:
            total_fees = sum(t.get('fees', 0) for t in trades)
            st.metric("Total Fees", format_currency(total_fees))

def render_profit_analysis():
    """Render profit analysis section"""
    st.subheader("💰 Profit Analysis")
    
    if config.is_simulation_mode():
        pnl_data = simulator.get_profit_loss()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Initial Balance",
                format_currency(pnl_data['initial_balance'])
            )
        
        with col2:
            st.metric(
                "Current Value",
                format_currency(pnl_data['current_value']),
                delta=format_currency(pnl_data['absolute_pnl'])
            )
        
        with col3:
            st.metric(
                "Total Return",
                format_percentage(pnl_data['percentage_pnl']),
                delta=format_currency(pnl_data['absolute_pnl'])
            )
        
        # Progress bar for profit
        if pnl_data['percentage_pnl'] > 0:
            st.success(f"📈 Portfolio up {pnl_data['percentage_pnl']:.2f}%")
        elif pnl_data['percentage_pnl'] < 0:
            st.error(f"📉 Portfolio down {abs(pnl_data['percentage_pnl']):.2f}%")
        else:
            st.info("📊 Portfolio unchanged")
    
    # Realized vs Unrealized P&L
    status = trading_engine.get_status()
    if status.get('pnl'):
        st.write("**Position Breakdown:**")
        
        unrealized = status['pnl']['unrealized']
        realized = status['pnl']['realized']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Unrealized P&L:** {format_currency(unrealized.get('absolute', 0))}")
            st.write(f"**Current Value:** {format_currency(unrealized.get('current_value', 0))}")
        
        with col2:
            st.write(f"**Realized P&L:** {format_currency(realized.get('absolute', 0))}")
            st.write(f"**Completed Trades:** {realized.get('total_trades', 0)}")
            if realized.get('total_trades', 0) > 0:
                st.write(f"**Win Rate:** {realized.get('win_rate', 0):.1f}%")

def render_market_info():
    """Render market information"""
    st.subheader("📊 Market Information")
    
    try:
        # Get bid/ask spread if available
        if not config.is_simulation_mode():
            from core.kucoin_client import kucoin_client
            spread_info = kucoin_client.get_bid_ask_spread()
            
            if spread_info:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Bid Price", format_currency(spread_info['bid']))
                
                with col2:
                    st.metric("Ask Price", format_currency(spread_info['ask']))
                
                with col3:
                    st.metric("Spread", f"{spread_info['spread_percent']:.3f}%")
        
        # Show order book depth or other market info
        st.info("💡 Using limit orders helps you get better fill prices and lower fees!")
        
    except Exception as e:
        st.warning(f"Could not fetch market data: {str(e)}")