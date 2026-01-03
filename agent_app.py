"""
7MS Trading Strategy Agent - Enhanced Gradio GUI with Beautiful Output
Complete version with stunning visualizations
"""

import gradio as gr
import MetaTrader5 as mt5
from datetime import datetime
import json
import uuid
import threading
from typing import Dict, List, Optional, Tuple
import time

# Import from your existing app.py
from app import (
    create_7ms_agent,
    initialize_mt5,
    check_symbol,
    SYMBOL,
    get_retcode_description
)

# ==================== GLOBAL STATE ====================
class AgentState:
    def __init__(self):
        self.agent = None
        self.current_thread_id = None
        self.is_running = False
        self.pending_interrupt = None
        self.interrupt_response = None
        self.output_buffer = []
        
agent_state = AgentState()

# ==================== ENHANCED FORMATTING UTILITIES ====================

def create_header(title: str, icon: str = "🎯") -> str:
    """Create a beautiful section header"""
    return f"""
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 15px; margin: 20px 0; box-shadow: 0 10px 30px rgba(0,0,0,0.3);">
    <h2 style="color: white; margin: 0; font-size: 24px; text-align: center;">
        {icon} {title}
    </h2>
</div>
"""

def create_info_card(title: str, content: str, color: str = "#667eea") -> str:
    """Create an info card"""
    return f"""
<div style="background: linear-gradient(135deg, {color}15 0%, {color}05 100%); border-left: 4px solid {color}; padding: 15px; border-radius: 10px; margin: 10px 0;">
    <h4 style="margin: 0 0 10px 0; color: {color}; font-size: 16px;">📊 {title}</h4>
    <div style="color: #333; line-height: 1.6;">{content}</div>
</div>
"""

def create_metric_card(label: str, value: str, icon: str = "📈", color: str = "#10b981") -> str:
    """Create a metric display card"""
    return f"""
<div style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; margin: 10px 0;">
    <div style="font-size: 32px; margin-bottom: 10px;">{icon}</div>
    <div style="color: #666; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;">{label}</div>
    <div style="color: {color}; font-size: 24px; font-weight: bold;">{value}</div>
</div>
"""

def format_phase_indicator(phase: str) -> str:
    """Create a phase indicator"""
    phases = {
        'init': ('🔄', 'Initialization', '#3b82f6'),
        'analysis': ('🔍', 'Market Analysis', '#8b5cf6'),
        'orderblocks': ('📦', 'Order Blocks Detection', '#ec4899'),
        'liquidity': ('💧', 'Liquidity Sweep Analysis', '#06b6d4'),
        'mss': ('📊', 'MSS & POI Detection', '#10b981'),
        'calculation': ('🧮', 'Risk Calculation', '#f59e0b'),
        'execution': ('⚡', 'Trade Execution', '#ef4444'),
        'complete': ('✅', 'Complete', '#10b981')
    }
    
    icon, title, color = phases.get(phase, ('🎯', phase.title(), '#667eea'))
    
    return f"""
<div style="background: {color}; color: white; padding: 12px 25px; border-radius: 25px; display: inline-block; margin: 15px 0; box-shadow: 0 4px 15px {color}33; animation: pulse 2s infinite;">
    <span style="font-size: 18px; font-weight: bold;">{icon} {title}</span>
</div>
<style>
@keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.8; }}
}}
</style>
"""

def format_tool_call_beautiful(tool_name: str, args: dict) -> str:
    """Format tool call with beautiful styling"""
    tool_icons = {
        'get_market_data': '📊',
        'identify_order_blocks': '📦',
        'detect_liquidity_sweep': '💧',
        'find_mss_and_poi': '🎯',
        'calculate_entry_sl_tp': '🧮',
        'send_order': '⚡',
        'get_open_positions': '📈',
        'write_file': '📝'
    }
    
    icon = tool_icons.get(tool_name, '🔧')
    args_html = ""
    
    for key, value in args.items():
        args_html += f"""
        <div style="margin: 5px 0;">
            <span style="color: #8b5cf6; font-weight: 600;">{key}:</span>
            <span style="color: #1f2937;">{value}</span>
        </div>
        """
    
    return f"""
<div style="background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); border-radius: 12px; padding: 15px; margin: 15px 0; border: 2px solid #d1d5db;">
    <div style="display: flex; align-items: center; margin-bottom: 10px;">
        <span style="font-size: 24px; margin-right: 10px;">{icon}</span>
        <span style="color: #1f2937; font-weight: bold; font-size: 16px;">Tool Call: {tool_name}</span>
    </div>
    <div style="background: white; padding: 12px; border-radius: 8px; border-left: 4px solid #8b5cf6;">
        {args_html}
    </div>
</div>
"""

def format_tool_response_beautiful(tool_name: str, response: dict) -> str:
    """Format tool response with beautiful styling"""
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except:
            pass
    
    # Special formatting for different tool responses
    if tool_name == 'get_market_data' and isinstance(response, dict):
        latest = response.get('latest_candle', {})
        return create_info_card(
            f"Market Data: {response.get('symbol', 'N/A')} ({response.get('timeframe', 'N/A')})",
            f"""
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">
                {create_metric_card('Open', str(latest.get('open', 'N/A')), '🟢', '#10b981')}
                {create_metric_card('High', str(latest.get('high', 'N/A')), '🔼', '#3b82f6')}
                {create_metric_card('Low', str(latest.get('low', 'N/A')), '🔽', '#ef4444')}
                {create_metric_card('Close', str(latest.get('close', 'N/A')), '⚪', '#8b5cf6')}
            </div>
            <div style="margin-top: 10px; color: #666;">
                📏 Range: {latest.get('range', 'N/A')} | 
                📈 Recent High: {response.get('recent_high', 'N/A')} | 
                📉 Recent Low: {response.get('recent_low', 'N/A')}
            </div>
            """,
            '#3b82f6'
        )
    
    elif tool_name == 'identify_order_blocks' and isinstance(response, dict):
        obs = response.get('order_blocks', [])
        if obs:
            obs_html = ""
            for idx, ob in enumerate(obs[:3], 1):  # Show first 3
                obs_html += f"""
                <div style="background: white; padding: 12px; border-radius: 8px; margin: 8px 0; border-left: 4px solid {'#ef4444' if 'bearish' in ob.get('type', '') else '#10b981'};">
                    <div style="font-weight: bold; color: {'#ef4444' if 'bearish' in ob.get('type', '') else '#10b981'};">
                        {'🔴 Bearish OB' if 'bearish' in ob.get('type', '') else '🟢 Bullish OB'} #{idx}
                    </div>
                    <div style="color: #666; font-size: 14px; margin-top: 5px;">
                        📅 {ob.get('time', 'N/A')}<br>
                        📊 Zone: {ob.get('zone_low', 'N/A')} - {ob.get('zone_high', 'N/A')}<br>
                        💪 Strength: {ob.get('strength', 'N/A')}<br>
                        📍 Distance: {ob.get('current_price_distance', 'N/A')}
                    </div>
                </div>
                """
            return create_info_card(
                f"Order Blocks Found: {response.get('order_blocks_found', 0)}",
                obs_html,
                '#ec4899'
            )
        else:
            return create_info_card(
                "Order Blocks",
                "<div style='text-align: center; padding: 20px; color: #999;'>❌ No order blocks detected</div>",
                '#94a3b8'
            )
    
    elif tool_name == 'calculate_entry_sl_tp' and isinstance(response, dict):
        direction = response.get('direction', 'N/A').upper()
        color = '#10b981' if direction == 'BUY' else '#ef4444'
        icon = '🟢' if direction == 'BUY' else '🔴'
        
        return f"""
<div style="background: linear-gradient(135deg, {color}15 0%, {color}05 100%); border-radius: 15px; padding: 20px; margin: 15px 0; border: 3px solid {color};">
    <h3 style="margin: 0 0 15px 0; color: {color}; text-align: center; font-size: 20px;">
        {icon} {direction} TRADE SETUP
    </h3>
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
        {create_metric_card('Entry', str(response.get('entry_price', 'N/A')), '🎯', color)}
        {create_metric_card('Stop Loss', str(response.get('stop_loss', 'N/A')), '🛑', '#ef4444')}
        {create_metric_card('Take Profit', str(response.get('take_profit', 'N/A')), '💰', '#10b981')}
    </div>
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-top: 15px;">
        {create_metric_card('Risk:Reward', f"{response.get('risk_reward_ratio', 'N/A')}:1", '⚖️', '#8b5cf6')}
        {create_metric_card('Risk Pips', str(response.get('risk_pips', 'N/A')), '📊', '#f59e0b')}
    </div>
</div>
"""
    
    elif tool_name == 'send_order' and isinstance(response, dict):
        if response.get('order_sent'):
            return f"""
<div style="background: linear-gradient(135deg, #10b98120 0%, #10b98105 100%); border-radius: 15px; padding: 25px; margin: 20px 0; border: 3px solid #10b981; box-shadow: 0 10px 30px rgba(16, 185, 129, 0.2);">
    <div style="text-align: center; margin-bottom: 20px;">
        <div style="font-size: 48px; margin-bottom: 10px;">✅</div>
        <h2 style="color: #10b981; margin: 0; font-size: 24px;">ORDER EXECUTED SUCCESSFULLY</h2>
    </div>
    <div style="background: white; border-radius: 12px; padding: 20px;">
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
            <div>
                <div style="color: #666; font-size: 12px; text-transform: uppercase;">Order #</div>
                <div style="color: #1f2937; font-size: 18px; font-weight: bold;">{response.get('order', 'N/A')}</div>
            </div>
            <div>
                <div style="color: #666; font-size: 12px; text-transform: uppercase;">Deal #</div>
                <div style="color: #1f2937; font-size: 18px; font-weight: bold;">{response.get('deal', 'N/A')}</div>
            </div>
            <div>
                <div style="color: #666; font-size: 12px; text-transform: uppercase;">Volume</div>
                <div style="color: #1f2937; font-size: 18px; font-weight: bold;">{response.get('volume', 'N/A')} lots</div>
            </div>
            <div>
                <div style="color: #666; font-size: 12px; text-transform: uppercase;">Price</div>
                <div style="color: #1f2937; font-size: 18px; font-weight: bold;">{response.get('price', 'N/A')}</div>
            </div>
        </div>
        <div style="margin-top: 15px; padding: 12px; background: #f0fdf4; border-radius: 8px; border-left: 4px solid #10b981;">
            <div style="color: #10b981; font-weight: 600;">✓ {response.get('retcode_description', 'Success')}</div>
        </div>
    </div>
</div>
"""
    
    # Default response formatting
    response_html = ""
    if isinstance(response, dict):
        for key, value in response.items():
            if not isinstance(value, (list, dict)):
                response_html += f"""
                <div style="margin: 5px 0;">
                    <span style="color: #8b5cf6; font-weight: 600;">{key}:</span>
                    <span style="color: #1f2937;">{value}</span>
                </div>
                """
    
    return f"""
<div style="background: white; border-radius: 12px; padding: 15px; margin: 15px 0; border: 2px solid #10b981; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.1);">
    <div style="color: #10b981; font-weight: bold; margin-bottom: 10px; font-size: 16px;">
        ✅ Response: {tool_name}
    </div>
    <div style="background: #f9fafb; padding: 12px; border-radius: 8px;">
        {response_html}
    </div>
</div>
"""

def format_agent_message_beautiful(content: str) -> str:
    """Format agent message beautifully"""
    return f"""
<div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 12px; padding: 20px; margin: 15px 0; border-left: 5px solid #f59e0b; box-shadow: 0 4px 15px rgba(245, 158, 11, 0.2);">
    <div style="display: flex; align-items: center; margin-bottom: 10px;">
        <span style="font-size: 24px; margin-right: 10px;">🤖</span>
        <span style="color: #92400e; font-weight: bold; font-size: 16px;">Agent Analysis</span>
    </div>
    <div style="color: #78350f; line-height: 1.8; white-space: pre-wrap;">{content}</div>
</div>
"""

def format_interrupt_request_beautiful(action_requests: List[Dict]) -> str:
    """Format interrupt request beautifully"""
    output = f"""
<div style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); border-radius: 20px; padding: 30px; margin: 30px 0; border: 4px solid #ef4444; box-shadow: 0 15px 40px rgba(239, 68, 68, 0.3); animation: attention 1.5s infinite;">
    <div style="text-align: center; margin-bottom: 25px;">
        <div style="font-size: 64px; margin-bottom: 15px; animation: bounce 2s infinite;">⚠️</div>
        <h2 style="color: #991b1b; margin: 0; font-size: 28px; text-transform: uppercase; letter-spacing: 2px;">
            TRADE APPROVAL REQUIRED
        </h2>
        <div style="color: #7f1d1d; margin-top: 10px; font-size: 16px;">
            Please review and approve the following trade execution
        </div>
    </div>
"""
    
    for idx, action in enumerate(action_requests):
        args = action['args']
        direction = args.get('direction', 'N/A').upper()
        color = '#10b981' if direction == 'BUY' else '#ef4444'
        icon = '📈' if direction == 'BUY' else '📉'
        
        output += f"""
        <div style="background: white; border-radius: 15px; padding: 25px; margin: 20px 0; border: 3px solid {color}; box-shadow: 0 8px 20px rgba(0,0,0,0.1);">
            <h3 style="margin: 0 0 20px 0; color: {color}; font-size: 22px; text-align: center;">
                {icon} {direction} ORDER #{idx + 1}
            </h3>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;">
                <div style="background: #f9fafb; padding: 15px; border-radius: 10px; text-align: center;">
                    <div style="color: #666; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Entry Price</div>
                    <div style="color: {color}; font-size: 28px; font-weight: bold; margin-top: 8px;">{args.get('entry_price', 'N/A')}</div>
                </div>
                <div style="background: #f9fafb; padding: 15px; border-radius: 10px; text-align: center;">
                    <div style="color: #666; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Lot Size</div>
                    <div style="color: #1f2937; font-size: 28px; font-weight: bold; margin-top: 8px;">{args.get('lot_size', 'N/A')}</div>
                </div>
                <div style="background: #fef2f2; padding: 15px; border-radius: 10px; text-align: center;">
                    <div style="color: #666; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Stop Loss</div>
                    <div style="color: #ef4444; font-size: 28px; font-weight: bold; margin-top: 8px;">{args.get('sl_price', 'N/A')}</div>
                </div>
                <div style="background: #f0fdf4; padding: 15px; border-radius: 10px; text-align: center;">
                    <div style="color: #666; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Take Profit</div>
                    <div style="color: #10b981; font-size: 28px; font-weight: bold; margin-top: 8px;">{args.get('tp_price', 'N/A')}</div>
                </div>
            </div>
        </div>
        """
    
    output += """
</div>
<style>
@keyframes attention {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.02); }
}
@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}
</style>
"""
    
    return output

def format_positions_beautiful(positions) -> str:
    """Format open positions beautifully"""
    if not positions or len(positions) == 0:
        return """
<div style="text-align: center; padding: 60px; background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); border-radius: 20px; margin: 20px 0;">
    <div style="font-size: 64px; margin-bottom: 20px; opacity: 0.5;">📊</div>
    <div style="color: #9ca3af; font-size: 20px; font-weight: 600;">No Open Positions</div>
    <div style="color: #d1d5db; font-size: 14px; margin-top: 10px;">Start trading to see your positions here</div>
</div>
"""
    
    output = create_header("Open Positions", "📊")
    
    for pos in positions:
        pos_type = "BUY" if pos.type == 0 else "SELL"
        color = '#10b981' if pos.type == 0 else '#ef4444'
        icon = '📈' if pos.type == 0 else '📉'
        profit_color = '#10b981' if pos.profit >= 0 else '#ef4444'
        profit_icon = '🟢' if pos.profit >= 0 else '🔴'
        
        output += f"""
<div style="background: white; border-radius: 15px; padding: 25px; margin: 20px 0; border-left: 6px solid {color}; box-shadow: 0 8px 25px rgba(0,0,0,0.1);">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
            <span style="font-size: 24px; margin-right: 10px;">{icon}</span>
            <span style="color: {color}; font-size: 22px; font-weight: bold;">{pos_type}</span>
            <span style="color: #9ca3af; font-size: 14px; margin-left: 10px;">#{pos.ticket}</span>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 32px;">{profit_icon}</div>
            <div style="color: {profit_color}; font-size: 24px; font-weight: bold;">${pos.profit:.2f}</div>
        </div>
    </div>
    
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
        <div style="background: #f9fafb; padding: 12px; border-radius: 8px; text-align: center;">
            <div style="color: #666; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">Volume</div>
            <div style="color: #1f2937; font-size: 18px; font-weight: bold; margin-top: 5px;">{pos.volume}</div>
        </div>
        <div style="background: #f9fafb; padding: 12px; border-radius: 8px; text-align: center;">
            <div style="color: #666; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">Open Price</div>
            <div style="color: #1f2937; font-size: 18px; font-weight: bold; margin-top: 5px;">{pos.price_open}</div>
        </div>
        <div style="background: #f9fafb; padding: 12px; border-radius: 8px; text-align: center;">
            <div style="color: #666; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">Current</div>
            <div style="color: #1f2937; font-size: 18px; font-weight: bold; margin-top: 5px;">{pos.price_current}</div>
        </div>
    </div>
    
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-top: 15px;">
        <div style="background: #fef2f2; padding: 12px; border-radius: 8px; text-align: center;">
            <div style="color: #666; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">Stop Loss</div>
            <div style="color: #ef4444; font-size: 18px; font-weight: bold; margin-top: 5px;">{pos.sl}</div>
        </div>
        <div style="background: #f0fdf4; padding: 12px; border-radius: 8px; text-align: center;">
            <div style="color: #666; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">Take Profit</div>
            <div style="color: #10b981; font-size: 18px; font-weight: bold; margin-top: 5px;">{pos.tp}</div>
        </div>
    </div>
    
    <div style="margin-top: 15px; padding: 10px; background: #f3f4f6; border-radius: 8px; text-align: center; color: #666; font-size: 13px;">
        💬 {pos.comment}
    </div>
</div>
"""
    
    return output

# ==================== STREAM PROCESSING ====================

def stream_agent_with_interrupt(agent, initial_input, config):
    """Stream agent execution with beautiful formatting"""
    output_html = create_header("7MS Agent Analysis", "🤖")
    
    def process_stream(stream_input):
        nonlocal output_html
        current_phase = 'init'
        
        for chunk in agent.stream(stream_input, config=config, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                if node_output is None:
                    continue
                
                # Handle messages
                if "messages" in node_output:
                    try:
                        messages = node_output["messages"]
                        if not isinstance(messages, list):
                            messages = [messages] if messages else []
                        
                        for msg in messages:
                            # Agent text messages
                            if hasattr(msg, 'content') and msg.content and isinstance(msg.content, str):
                                if len(msg.content) > 50:  # Only show substantial messages
                                    output_html += format_agent_message_beautiful(msg.content[:500])
                            
                            # Tool calls
                            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    tool_name = tool_call['name']
                                    
                                    # Phase tracking based on tool calls
                                    if "get_market_data" in tool_name:
                                        output_html += format_phase_indicator('analysis')
                                    elif "identify_order_blocks" in tool_name:
                                        output_html += format_phase_indicator('orderblocks')
                                    elif "detect_liquidity_sweep" in tool_name:
                                        output_html += format_phase_indicator('liquidity')
                                    elif "find_mss_and_poi" in tool_name:
                                        output_html += format_phase_indicator('mss')
                                    elif "calculate_entry_sl_tp" in tool_name:
                                        output_html += format_phase_indicator('calculation')
                                    elif "send_order" in tool_name:
                                        output_html += format_phase_indicator('execution')
                                    
                                    output_html += format_tool_call_beautiful(
                                        tool_name,
                                        tool_call['args']
                                    )
                            
                            # Tool responses
                            if hasattr(msg, 'name') and hasattr(msg, 'content') and msg.name:
                                try:
                                    response_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                                    output_html += format_tool_response_beautiful(
                                        msg.name,
                                        response_data
                                    )
                                except:
                                    pass
                    except Exception as e:
                        pass
            
            # Check for interrupt
            if "__interrupt__" in chunk:
                interrupt_data = chunk["__interrupt__"][0].value
                
                if interrupt_data:
                    action_requests = interrupt_data.get("action_requests", [])
                    
                    if action_requests:
                        output_html += format_interrupt_request_beautiful(action_requests)
                        return (output_html, True, action_requests)
        
        output_html += format_phase_indicator('complete')
        return (output_html, False, None)
    
    return process_stream(initial_input)

# ==================== AGENT EXECUTION ====================

def run_agent_analysis(symbol: str):
    """Main function to run agent analysis"""
    
    if agent_state.is_running:
        return (
            create_info_card("Warning", "Agent is already running. Please wait for completion.", "#f59e0b"),
            gr.update(visible=False),
            "",
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False)
        )
    
    agent_state.is_running = True
    agent_state.pending_interrupt = None
    output_html = ""
    
    try:
        # Initialize MT5 if not already
        if agent_state.agent is None:
            output_html += create_info_card("Initialization", "🔄 Initializing MT5 and creating agent...", "#3b82f6")
            
            if not initialize_mt5():
                agent_state.is_running = False
                return (
                    create_info_card("Error", "❌ Failed to initialize MT5", "#ef4444"),
                    gr.update(visible=False),
                    "",
                    gr.update(interactive=False),
                    gr.update(interactive=False),
                    gr.update(interactive=False)
                )
            
            if not check_symbol(symbol):
                agent_state.is_running = False
                return (
                    create_info_card("Error", f"❌ Failed to enable symbol {symbol}", "#ef4444"),
                    gr.update(visible=False),
                    "",
                    gr.update(interactive=False),
                    gr.update(interactive=False),
                    gr.update(interactive=False)
                )
            
            agent_state.agent = create_7ms_agent()
            output_html += create_info_card("Success", "✅ Agent initialized successfully", "#10b981")
        
        # Create new thread
        thread_id = str(uuid.uuid4())
        agent_state.current_thread_id = thread_id
        config = {"configurable": {"thread_id": thread_id}}
        
        output_html += create_header(f"Starting Analysis for {symbol}", "🎯")
        
        initial_message = {
            "messages": [{
                "role": "user",
                "content": f"""Analyze {symbol} and look for 7MS trading opportunities.

Follow the complete workflow:
1. Confirm the trend by identifying Order Blocks on Daily, 4H, and 1H timeframes
2. Look for 15M liquidity sweep setups
3. If setup found, find MSS and POI on 1M timeframe
4. Calculate entry, SL, and TP
5. Present complete trade plan
6. **CALL send_order tool with the calculated parameters**
7. The system will ask for your approval before executing
8. Monitor the position

Remember: CALL send_order directly - don't just ask for approval in text."""
            }]
        }
        
        # Process stream and check for interrupts
        stream_output, has_interrupt, interrupt_data = stream_agent_with_interrupt(
            agent_state.agent,
            initial_message,
            config
        )
        
        output_html += stream_output
        
        if has_interrupt:
            # Store interrupt data and show approval UI
            agent_state.pending_interrupt = interrupt_data
            
            # Format trade details for approval panel
            trade_details = ""
            for idx, action in enumerate(interrupt_data):
                trade_details += f"**Action {idx+1}: {action['name']}**\n"
                for key, value in action['args'].items():
                    trade_details += f"  • {key}: {value}\n"
                trade_details += "\n"
            
            return (
                output_html,
                gr.update(visible=True),  # Show approval group
                trade_details,
                gr.update(interactive=True, value=action['args'].get('entry_price', 0)),
                gr.update(interactive=True, value=action['args'].get('sl_price', 0)),
                gr.update(interactive=True, value=action['args'].get('tp_price', 0)),
            )
        
        # No interrupt, analysis complete
        output_html += create_header("Analysis Complete", "✅")
        
        return (
            output_html,
            gr.update(visible=False),
            "",
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False)
        )
        
    except Exception as e:
        import traceback
        error_html = create_info_card("Error", f"❌ {str(e)}<br><pre>{traceback.format_exc()}</pre>", "#ef4444")
        
        return (
            output_html + error_html,
            gr.update(visible=False),
            "",
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False)
        )
    
    finally:
        agent_state.is_running = False

def handle_approval(decision: str, entry_price: float, sl_price: float, tp_price: float, lot_size: float, output_html: str):
    """Handle trade approval/reject/edit"""
    
    if agent_state.pending_interrupt is None:
        return output_html + create_info_card("Warning", "⚠️ No pending trade approval", "#f59e0b"), gr.update(visible=False)
    
    try:
        action_requests = agent_state.pending_interrupt
        config = {"configurable": {"thread_id": agent_state.current_thread_id}}
        
        resume_value = None
        
        if decision == "approve":
            resume_value = {"decisions": [{"type": "approve"} for _ in action_requests]}
            output_html += create_info_card("Approved", "✅ Trade Approved - Executing...", "#10b981")
            
        elif decision == "reject":
            resume_value = {
                "decisions": [{
                    "type": "reject",
                    "message": "Trade rejected by user"
                } for _ in action_requests]
            }
            output_html += create_info_card("Rejected", "❌ Trade Rejected", "#ef4444")
            
        elif decision == "edit":
            decisions = []
            for action in action_requests:
                edited_args = action['args'].copy()
                edited_args['entry_price'] = entry_price
                edited_args['sl_price'] = sl_price
                edited_args['tp_price'] = tp_price
                edited_args['lot_size'] = lot_size
                
                decisions.append({
                    "type": "edit",
                    "edited_action": {
                        "name": action['name'],
                        "args": edited_args
                    }
                })
            resume_value = {"decisions": decisions}
            output_html += create_info_card("Edited", "✏️ Trade Edited - Executing with new parameters...", "#3b82f6")
        
        # Resume agent execution
        if resume_value and agent_state.agent:
            from langgraph.types import Command
            
            stream_output, has_interrupt, interrupt_data = stream_agent_with_interrupt(
                agent_state.agent,
                Command(resume=resume_value),
                config
            )
            
            output_html += stream_output
            
            if has_interrupt:
                # Another interrupt (shouldn't happen but handle it)
                agent_state.pending_interrupt = interrupt_data
                return output_html, gr.update(visible=True)
            
            # Execution complete
            output_html += create_header("Trade Execution Complete", "✅")
            
        agent_state.pending_interrupt = None
        return output_html, gr.update(visible=False)
        
    except Exception as e:
        import traceback
        error_html = create_info_card("Error", f"❌ Error during approval: {str(e)}<br><pre>{traceback.format_exc()}</pre>", "#ef4444")
        agent_state.pending_interrupt = None
        return output_html + error_html, gr.update(visible=False)

def get_current_positions():
    """Get current open positions"""
    try:
        positions = mt5.positions_get(symbol=SYMBOL)
        return format_positions_beautiful(positions)
    except Exception as e:
        return create_info_card("Error", f"❌ Error fetching positions: {str(e)}", "#ef4444")

# ==================== GRADIO INTERFACE ====================

def create_interface():
    """Create Gradio interface"""
    
    with gr.Blocks(title="7MS Trading Agent", theme=gr.themes.Soft()) as demo:
        gr.HTML("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; border-radius: 20px; margin-bottom: 30px; box-shadow: 0 15px 50px rgba(0,0,0,0.3);">
            <h1 style="color: white; text-align: center; font-size: 48px; margin: 0; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                🎯 7MS Trading Strategy Agent
            </h1>
            <p style="color: rgba(255,255,255,0.9); text-align: center; font-size: 20px; margin-top: 15px;">
                Automated Market Analysis & Trade Execution with Human-in-the-Loop Approval
            </p>
        </div>
        """)
        
        with gr.Tab("📊 Trading Dashboard"):
            with gr.Row():
                with gr.Column(scale=2):
                    symbol_input = gr.Textbox(
                        value="XAUUSD",
                        label="Trading Symbol",
                        placeholder="Enter symbol (e.g., XAUUSD)"
                    )
                    
                    start_btn = gr.Button("🚀 Start Analysis", variant="primary", size="lg")
                    
                    gr.Markdown("### 📈 Agent Output")
                    output_display = gr.HTML(label="")
                
                with gr.Column(scale=1):
                    gr.Markdown("### 📊 Open Positions")
                    positions_display = gr.HTML(label="")
                    refresh_positions_btn = gr.Button("🔄 Refresh Positions")
                    
                    # Timer for auto-refresh
                    positions_timer = gr.Timer(value=5.0)
                    
                    gr.Markdown("### ⏸️ Trade Approval")
                    
                    with gr.Group(visible=False) as approval_group:
                        gr.HTML("""
                        <div style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); padding: 20px; border-radius: 15px; text-align: center; border: 3px solid #ef4444;">
                            <h3 style="color: #991b1b; margin: 0;">⚠️ TRADE PENDING APPROVAL</h3>
                        </div>
                        """)
                        trade_details = gr.Textbox(label="Trade Details", lines=5, interactive=False)
                        
                        with gr.Row():
                            approve_btn = gr.Button("✅ Approve", variant="primary")
                            reject_btn = gr.Button("❌ Reject", variant="stop")
                        
                        with gr.Accordion("✏️ Edit Trade Parameters", open=False):
                            edit_entry = gr.Number(label="Entry Price", precision=5)
                            edit_sl = gr.Number(label="Stop Loss", precision=5)
                            edit_tp = gr.Number(label="Take Profit", precision=5)
                            edit_lot = gr.Number(label="Lot Size", value=0.01, precision=2)
                            edit_btn = gr.Button("💾 Apply & Execute", variant="primary")
        
        with gr.Tab("📚 Strategy Guide"):
            gr.HTML("""
            <div style="padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 20px; margin-bottom: 30px;">
                    <h2 style="color: white; margin: 0;">7MS Trading Strategy Rules</h2>
                </div>
                
                <div style="background: white; border-radius: 15px; padding: 25px; margin: 20px 0; box-shadow: 0 5px 20px rgba(0,0,0,0.1);">
                    <h3 style="color: #667eea;">📊 Step 1: Trend Confirmation</h3>
                    <ul style="line-height: 2;">
                        <li>Identify Order Blocks on Daily, 4H, 1H timeframes</li>
                        <li>Daily & 4H OBs give heavy reversals</li>
                        <li>1H & 15M OBs are continuation blocks</li>
                    </ul>
                </div>
                
                <div style="background: white; border-radius: 15px; padding: 25px; margin: 20px 0; box-shadow: 0 5px 20px rgba(0,0,0,0.1);">
                    <h3 style="color: #8b5cf6;">💧 Step 2: 15M Liquidity Sweep</h3>
                    <ul style="line-height: 2;">
                        <li><strong>Condition 1:</strong> Wick sweep + close above/below swept level</li>
                        <li><strong>Condition 2:</strong> Two candle rejection pattern</li>
                    </ul>
                </div>
                
                <div style="background: white; border-radius: 15px; padding: 25px; margin: 20px 0; box-shadow: 0 5px 20px rgba(0,0,0,0.1);">
                    <h3 style="color: #ec4899;">🎯 Step 3: MSS & POI (1M Timeframe)</h3>
                    <ul style="line-height: 2;">
                        <li>Find Market Structure Shift after sweep</li>
                        <li>Identify Point of Interest in MSS zone</li>
                        <li>Look for: Order Block, FVG, or both</li>
                    </ul>
                </div>
                
                <div style="background: white; border-radius: 15px; padding: 25px; margin: 20px 0; box-shadow: 0 5px 20px rgba(0,0,0,0.1);">
                    <h3 style="color: #06b6d4;">⚡ Step 4: Entry Triggers</h3>
                    <ul style="line-height: 2;">
                        <li>Overlapping FVGs</li>
                        <li>FVG Fill/Tap</li>
                        <li>Single FVG reaction</li>
                    </ul>
                </div>
                
                <div style="background: white; border-radius: 15px; padding: 25px; margin: 20px 0; box-shadow: 0 5px 20px rgba(0,0,0,0.1);">
                    <h3 style="color: #10b981;">⚖️ Step 5: Risk Management</h3>
                    <ul style="line-height: 2;">
                        <li>SL below POI or MSS level</li>
                        <li>TP at next Order Block or liquidity</li>
                        <li>Minimum 2:1 Risk-Reward ratio</li>
                    </ul>
                </div>
                
                <div style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); border-radius: 15px; padding: 25px; margin: 20px 0; border: 3px solid #ef4444;">
                    <h3 style="color: #991b1b; margin-top: 0;">🛡️ Human-in-the-Loop Safety</h3>
                    <p style="color: #7f1d1d; font-size: 18px; line-height: 1.8;">
                        All trades require your approval before execution! Review, edit, or reject any trade setup.
                    </p>
                </div>
            </div>
            """)
        
        with gr.Tab("⚙️ Settings"):
            gr.Markdown("### MT5 Connection")
            mt5_status = gr.Textbox(label="Status", value="Not connected")
            connect_btn = gr.Button("🔌 Connect to MT5")
            
            gr.Markdown("### Agent Configuration")
            risk_percent = gr.Slider(1, 5, value=2, step=0.5, label="Risk per Trade (%)")
            min_rr = gr.Slider(1, 5, value=2, step=0.5, label="Minimum Risk:Reward")
        
        # Event handlers
        start_btn.click(
            fn=run_agent_analysis,
            inputs=[symbol_input],
            outputs=[output_display, approval_group, trade_details, edit_entry, edit_sl, edit_tp]
        )
        
        approve_btn.click(
            fn=lambda o: handle_approval("approve", 0, 0, 0, 0.01, o),
            inputs=[output_display],
            outputs=[output_display, approval_group]
        )
        
        reject_btn.click(
            fn=lambda o: handle_approval("reject", 0, 0, 0, 0.01, o),
            inputs=[output_display],
            outputs=[output_display, approval_group]
        )
        
        edit_btn.click(
            fn=lambda e, s, t, l, o: handle_approval("edit", e, s, t, l, o),
            inputs=[edit_entry, edit_sl, edit_tp, edit_lot, output_display],
            outputs=[output_display, approval_group]
        )
        
        refresh_positions_btn.click(
            fn=get_current_positions,
            outputs=[positions_display]
        )
        
        connect_btn.click(
            fn=lambda: "✅ MT5 Connected" if initialize_mt5() else "❌ Connection Failed",
            outputs=[mt5_status]
        )
        
        # Auto-refresh positions with timer
        positions_timer.tick(
            fn=get_current_positions,
            outputs=[positions_display]
        )
    
    return demo

# ==================== MAIN ====================

if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        debug=True,
        share=False
    )