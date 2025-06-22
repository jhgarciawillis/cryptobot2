import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from core.trading_engine import trading_engine
from core.position_manager import position_manager
from core.simulator import simulator
from utils.config import config
from utils.helpers import format_currency, format_percentage

def render_performance_chart():
    """Render portfolio performance chart"""
    st.subheader("📈 Portfolio Performance")
    
    if config.is_simulation_mode():
        render_simulation_performance()
    else:
        render_live_performance()

def render_simulation_performance():
    """Render simulation performance chart"""
    trades = simulator.get_trade_history()
    
    if not trades:
        st.info("No trades yet to display performance")
        return
    
    # Calculate portfolio value over time
    performance_data = []
    balance = simulator.initial_balance
    btc_holdings = 0
    
    for trade in trades:
        timestamp = datetime.fromisoformat(trade['timestamp'])
        
        if trade['side'] == 'buy':
            balance -= trade['cost']
            btc_holdings += trade['amount']
        else:  # sell
            balance += trade['cost'] - trade.get('fees', 0)
            btc_holdings -= trade['amount']
        
        # Calculate total portfolio value
        portfolio_value = balance + (btc_holdings * trade['price'])
        
        performance_data.append({
            'timestamp': timestamp,
            'portfolio_value': portfolio_value,
            'balance': balance,
            'btc_value': btc_holdings * trade['price'],
            'btc_amount': btc_holdings,
            'trade_type': trade['side']
        })
    
    if not performance_data:
        return
    
    df = pd.DataFrame(performance_data)
    
    # Create performance chart
    fig = go.Figure()
    
    # Portfolio value line
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['portfolio_value'],
        mode='lines+markers',
        name='Portfolio Value',
        line=dict(color='blue', width=3),
        hovertemplate='<b>Portfolio Value</b><br>%{y:$,.2f}<br>%{x}<extra></extra>'
    ))
    
    # Initial balance line
    fig.add_hline(
        y=simulator.initial_balance,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Initial: {format_currency(simulator.initial_balance)}"
    )
    
    # Mark trades
    buy_trades = df[df['trade_type'] == 'buy']
    sell_trades = df[df['trade_type'] == 'sell']
    
    if not buy_trades.empty:
        fig.add_trace(go.Scatter(
            x=buy_trades['timestamp'],
            y=buy_trades['portfolio_value'],
            mode='markers',
            name='Buy',
            marker=dict(color='green', size=10, symbol='triangle-up'),
            hovertemplate='<b>BUY</b><br>Portfolio: %{y:$,.2f}<extra></extra>'
        ))
    
    if not sell_trades.empty:
        fig.add_trace(go.Scatter(
            x=sell_trades['timestamp'],
            y=sell_trades['portfolio_value'],
            mode='markers',
            name='Sell',
            marker=dict(color='red', size=10, symbol='triangle-down'),
            hovertemplate='<b>SELL</b><br>Portfolio: %{y:$,.2f}<extra></extra>'
        ))
    
    fig.update_layout(
        title="Portfolio Performance Over Time",
        xaxis_title="Time",
        yaxis_title="Portfolio Value (USD)",
        height=500,
        showlegend=True,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Performance metrics
    current_value = df['portfolio_value'].iloc[-1]
    total_return = current_value - simulator.initial_balance
    return_pct = (total_return / simulator.initial_balance) * 100
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Return", format_currency(total_return), delta=format_percentage(return_pct))
    with col2:
        st.metric("Current Value", format_currency(current_value))
    with col3:
        total_trades = len(trades)
        st.metric("Total Trades", total_trades)

def render_live_performance():
    """Render live trading performance"""
    st.info("Live performance tracking coming soon...")
    # Implementation for live trading would require tracking actual trades

def render_profit_distribution():
    """Render profit distribution chart"""
    st.subheader("💰 Profit Distribution")
    
    closed_positions = position_manager.get_closed_positions()
    
    if not closed_positions:
        st.info("No completed trades to analyze")
        return
    
    # Calculate profit/loss for each trade
    trade_data = []
    for pos in closed_positions:
        if pos.exit_price and pos.buy_price:
            profit_pct = ((pos.exit_price - pos.buy_price) / pos.buy_price) * 100
            profit_usd = (pos.exit_price - pos.buy_price) * pos.amount
            
            trade_data.append({
                'trade_id': len(trade_data) + 1,
                'profit_pct': profit_pct,
                'profit_usd': profit_usd,
                'buy_price': pos.buy_price,
                'sell_price': pos.exit_price,
                'amount': pos.amount,
                'timestamp': pos.exit_timestamp
            })
    
    if not trade_data:
        return
    
    df = pd.DataFrame(trade_data)
    
    # Profit distribution histogram
    fig = px.histogram(
        df,
        x='profit_pct',
        nbins=20,
        title='Profit Distribution (%)',
        labels={'profit_pct': 'Profit Percentage', 'count': 'Number of Trades'},
        color_discrete_sequence=['lightblue']
    )
    
    # Add vertical line at break-even
    fig.add_vline(x=0, line_dash="dash", line_color="red", annotation_text="Break Even")
    
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        winning_trades = len(df[df['profit_pct'] > 0])
        win_rate = (winning_trades / len(df)) * 100
        st.metric("Win Rate", f"{win_rate:.1f}%")
    
    with col2:
        avg_profit = df['profit_pct'].mean()
        st.metric("Avg Profit", format_percentage(avg_profit))
    
    with col3:
        best_trade = df['profit_pct'].max()
        st.metric("Best Trade", format_percentage(best_trade))
    
    with col4:
        worst_trade = df['profit_pct'].min()
        st.metric("Worst Trade", format_percentage(worst_trade))

def render_price_analysis():
    """Render price analysis charts"""
    st.subheader("📊 Price Analysis")
    
    # This would typically fetch real price data
    # For now, we'll show a placeholder
    current_price = trading_engine.get_status().get('current_price', 0)
    
    if not current_price:
        st.warning("No price data available")
        return
    
    # Create sample price movement chart
    # In production, you'd fetch real OHLCV data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='1H')
    
    # Generate sample OHLCV data
    base_price = current_price
    price_data = []
    
    for i, date in enumerate(dates):
        # Simple random walk for demo
        change = (i - 50) * 2  # Trend component
        noise = (hash(str(date)) % 200 - 100) / 10  # Random component
        price = base_price + change + noise
        
        price_data.append({
            'timestamp': date,
            'price': max(price, base_price * 0.8),  # Don't go too low
            'volume': abs(noise) * 1000  # Volume based on price volatility
        })
    
    df = pd.DataFrame(price_data)
    
    # Price chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['price'],
        mode='lines',
        name='BTC Price',
        line=dict(color='orange', width=2)
    ))
    
    # Add support/resistance levels
    positions = position_manager.get_open_positions()
    if positions:
        avg_buy_price = position_manager.get_average_buy_price()
        profit_target = avg_buy_price * config.get_profit_threshold()
        
        fig.add_hline(
            y=avg_buy_price,
            line_dash="dot",
            line_color="blue",
            annotation_text=f"Avg Buy: {format_currency(avg_buy_price)}"
        )
        
        fig.add_hline(
            y=profit_target,
            line_dash="dash",
            line_color="green",
            annotation_text=f"Target: {format_currency(profit_target)}"
        )
    
    fig.update_layout(
        title="BTC Price Movement (Sample Data)",
        xaxis_title="Time",
        yaxis_title="Price (USD)",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Volume chart
    vol_fig = px.bar(
        df,
        x='timestamp',
        y='volume',
        title='Trading Volume (Sample Data)',
        labels={'volume': 'Volume', 'timestamp': 'Time'}
    )
    vol_fig.update_layout(height=200)
    st.plotly_chart(vol_fig, use_container_width=True)

def render_risk_metrics():
    """Render risk analysis metrics"""
    st.subheader("⚠️ Risk Analysis")
    
    status = trading_engine.get_status()
    current_price = status.get('current_price', 0)
    positions = position_manager.get_open_positions()
    
    if not positions or not current_price:
        st.info("No position data for risk analysis")
        return
    
    # Calculate risk metrics
    total_investment = sum(pos.buy_price * pos.amount for pos in positions)
    current_value = sum(pos.amount * current_price for pos in positions)
    unrealized_pnl = current_value - total_investment
    
    # Position concentration
    position_sizes = [pos.amount * pos.buy_price for pos in positions]
    max_position = max(position_sizes)
    concentration = (max_position / total_investment) * 100
    
    # Drawdown calculation
    avg_buy_price = position_manager.get_average_buy_price()
    max_drawdown = 0
    if avg_buy_price and current_price < avg_buy_price:
        max_drawdown = ((avg_buy_price - current_price) / avg_buy_price) * 100
    
    # Risk metrics display
    col1, col2, col3 = st.columns(3)
    
    with col1:
        risk_color = "normal"
        if concentration > 50:
            risk_color = "inverse"
        st.metric(
            "Position Concentration",
            f"{concentration:.1f}%",
            help="Percentage of portfolio in largest position"
        )
    
    with col2:
        drawdown_color = "normal"
        if max_drawdown > 10:
            drawdown_color = "inverse"
        st.metric(
            "Current Drawdown",
            format_percentage(max_drawdown),
            delta=f"-{max_drawdown:.1f}%" if max_drawdown > 0 else "0%"
        )
    
    with col3:
        exposure = (total_investment / (status['balances']['USDT'] + total_investment)) * 100
        st.metric(
            "Market Exposure",
            f"{exposure:.1f}%",
            help="Percentage of total capital invested in BTC"
        )
    
    # Risk warnings
    if concentration > 70:
        st.warning("⚠️ High position concentration - Consider diversifying entry points")
    
    if max_drawdown > 15:
        st.error("🚨 High drawdown detected - Monitor positions closely")
    
    if exposure > 90:
        st.warning("⚠️ High market exposure - Limited funds for additional purchases")