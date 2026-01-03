"""
7MS Trading Strategy Deep Agent with MT5 Integration
Complete implementation with middleware, HITL, and strategy logic
ALL FIXES APPLIED - Production Ready
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
import time
from typing import Literal, Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
import pandas as pd
import numpy as np
import os
import uuid
import json
from dotenv import load_dotenv
load_dotenv()


# ==================== CONFIGURATION ====================
SYMBOL = "XAUUSD"
LOT = 0.01
SL_POINTS = 100  # Will be overridden by strategy logic
TP_POINTS = 300  # Will be overridden by strategy logic
MAGIC_NUMBER = 7777  # For 7MS strategy identification

# ==================== MT5 INITIALIZATION ====================
def initialize_mt5():
    """Initialize MT5 terminal"""
    if not mt5.initialize():
        print("❌ MT5 initialization failed")
        return False
    print("✅ MT5 initialized successfully")
    return True

def check_symbol(symbol: str = SYMBOL):
    """Enable symbol in MT5"""
    if not mt5.symbol_select(symbol, True):
        print(f"❌ Failed to enable symbol {symbol}")
        return False
    print(f"✅ Symbol {symbol} enabled")
    return True

# ==================== MT5 HELPER FUNCTIONS ====================

def get_filling_mode(symbol: str = SYMBOL):
    """
    Get the correct filling mode for the symbol.
    Required for XAUUSD and other symbols.
    """
    filling_modes = [
        mt5.ORDER_FILLING_FOK,  # Fill or Kill
        mt5.ORDER_FILLING_IOC,  # Immediate or Cancel
        mt5.ORDER_FILLING_RETURN  # Return
    ]
    
    for mode in filling_modes:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": mt5.symbol_info(symbol).volume_min,
            "type": mt5.ORDER_TYPE_BUY,
            "price": mt5.symbol_info_tick(symbol).ask,
            "type_filling": mode,
            "type_time": mt5.ORDER_TIME_GTC
        }
        
        result = mt5.order_check(request)
        
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            return mode
    
    return mt5.ORDER_FILLING_RETURN  # Default fallback


def get_retcode_description(retcode: int) -> str:
    """Get human-readable description of MT5 return codes"""
    retcode_dict = {
        10004: "TRADE_RETCODE_REQUOTE - Requote",
        10006: "TRADE_RETCODE_REJECT - Request rejected",
        10007: "TRADE_RETCODE_CANCEL - Request canceled by trader",
        10008: "TRADE_RETCODE_PLACED - Order placed",
        10009: "TRADE_RETCODE_DONE - Request completed",
        10010: "TRADE_RETCODE_DONE_PARTIAL - Only part of the request was completed",
        10011: "TRADE_RETCODE_ERROR - Request processing error",
        10012: "TRADE_RETCODE_TIMEOUT - Request canceled by timeout",
        10013: "TRADE_RETCODE_INVALID - Invalid request",
        10014: "TRADE_RETCODE_INVALID_VOLUME - Invalid volume in the request",
        10015: "TRADE_RETCODE_INVALID_PRICE - Invalid price in the request",
        10016: "TRADE_RETCODE_INVALID_STOPS - Invalid stops in the request",
        10017: "TRADE_RETCODE_TRADE_DISABLED - Trade is disabled",
        10018: "TRADE_RETCODE_MARKET_CLOSED - Market is closed",
        10019: "TRADE_RETCODE_NO_MONEY - There is not enough money to complete the request",
        10020: "TRADE_RETCODE_PRICE_CHANGED - Prices changed",
        10021: "TRADE_RETCODE_PRICE_OFF - There are no quotes to process the request",
        10022: "TRADE_RETCODE_INVALID_EXPIRATION - Invalid order expiration date",
        10023: "TRADE_RETCODE_ORDER_CHANGED - Order state changed",
        10024: "TRADE_RETCODE_TOO_MANY_REQUESTS - Too frequent requests",
        10025: "TRADE_RETCODE_NO_CHANGES - No changes in request",
        10026: "TRADE_RETCODE_SERVER_DISABLES_AT - Autotrading disabled by server",
        10027: "TRADE_RETCODE_CLIENT_DISABLES_AT - Autotrading disabled by client terminal",
        10028: "TRADE_RETCODE_LOCKED - Request locked for processing",
        10029: "TRADE_RETCODE_FROZEN - Order or position frozen",
        10030: "TRADE_RETCODE_INVALID_FILL - Invalid order filling type",
    }
    
    return retcode_dict.get(retcode, f"Unknown retcode: {retcode}")

# ==================== MT5 TOOLS ====================

@tool
def get_market_data(
    symbol: str = SYMBOL,
    timeframe: Literal["1M", "15M", "1H", "4H", "D1"] = "15M",
    bars: int = 500
) -> str:
    """
    Fetch market data from MT5 for analysis.
    
    Args:
        symbol: Trading symbol (default: XAUUSD)
        timeframe: Timeframe for analysis (1M, 15M, 1H, 4H, D1)
        bars: Number of bars to fetch
        
    Returns:
        JSON string with OHLC data and basic statistics
    """
    tf_map = {
        "1M": mt5.TIMEFRAME_M1,
        "15M": mt5.TIMEFRAME_M15,
        "1H": mt5.TIMEFRAME_H1,
        "4H": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
    }
    
    if timeframe not in tf_map:
        return f"Error: Invalid timeframe. Use: {list(tf_map.keys())}"
    
    rates = mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, bars)
    
    if rates is None or len(rates) == 0:
        return f"Error: Failed to fetch data for {symbol} on {timeframe}"
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Calculate basic statistics
    latest = df.iloc[-1]
    high_low_range = latest['high'] - latest['low']
    
    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars_count": len(df),
        "latest_candle": {
            "time": str(latest['time']),
            "open": float(latest['open']),
            "high": float(latest['high']),
            "low": float(latest['low']),
            "close": float(latest['close']),
            "range": float(high_low_range)
        },
        "recent_high": float(df['high'].tail(20).max()),
        "recent_low": float(df['low'].tail(20).min()),
        "data_file": f"/analysis/{symbol}_{timeframe}_data.csv"
    }
    
    return json.dumps(result, indent=2)

@tool
def identify_order_blocks(
    symbol: str = SYMBOL,
    timeframe: Literal["15M", "1H", "4H", "D1"] = "4H",
    direction: Literal["bullish", "bearish", "both"] = "both"
) -> str:
    """
    Identify Order Blocks (OB) on the chart according to 7MS strategy rules.
    
    Order Block Rules:
    - Bullish OB: 1st candle is swing low, 2nd candle closes above 1st high with gap
    - Bearish OB: 1st candle is swing high, 2nd candle closes below 1st low with gap
    - Daily and 4H OBs give heavy reversals
    - 1H and 15M OBs are continuation blocks
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe to analyze (15M, 1H, 4H, D1)
        direction: Look for bullish, bearish, or both OBs
        
    Returns:
        JSON with identified order blocks and their locations
    """
    tf_map = {
        "15M": mt5.TIMEFRAME_M15,
        "1H": mt5.TIMEFRAME_H1,
        "4H": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
    }
    
    rates = mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, 200)
    if rates is None:
        return "Error: Failed to fetch data"
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    order_blocks = []
    
    for i in range(2, len(df)):
        candle1 = df.iloc[i-2]
        candle2 = df.iloc[i-1]
        candle3 = df.iloc[i]
        
        # Bullish Order Block Detection
        if direction in ["bullish", "both"]:
            if candle2['close'] > candle1['high']:
                gap = candle2['open'] - candle1['high']
                if gap > 0:
                    if candle3['low'] <= candle1['high']:
                        order_blocks.append({
                            "type": "bullish_ob",
                            "timeframe": timeframe,
                            "time": str(candle1['time']),
                            "zone_low": float(candle1['low']),
                            "zone_high": float(candle1['high']),
                            "gap_size": float(gap),
                            "strength": "reversal" if timeframe in ["4H", "D1"] else "continuation",
                            "current_price_distance": float(df.iloc[-1]['close'] - candle1['high'])
                        })
        
        # Bearish Order Block Detection
        if direction in ["bearish", "both"]:
            if candle2['close'] < candle1['low']:
                gap = candle1['low'] - candle2['open']
                if gap > 0:
                    if candle3['high'] >= candle1['low']:
                        order_blocks.append({
                            "type": "bearish_ob",
                            "timeframe": timeframe,
                            "time": str(candle1['time']),
                            "zone_high": float(candle1['high']),
                            "zone_low": float(candle1['low']),
                            "gap_size": float(gap),
                            "strength": "reversal" if timeframe in ["4H", "D1"] else "continuation",
                            "current_price_distance": float(candle1['low'] - df.iloc[-1]['close'])
                        })
    
    return json.dumps({
        "symbol": symbol,
        "timeframe": timeframe,
        "order_blocks_found": len(order_blocks),
        "order_blocks": order_blocks[-10:]
    }, indent=2)

@tool
def detect_liquidity_sweep(
    symbol: str = SYMBOL,
    timeframe: Literal["15M"] = "15M",
    lookback_candles: int = 50
) -> str:
    """
    Detect liquidity sweeps on 15M timeframe according to 7MS rules.
    
    Liquidity Sweep Rules:
    - Bullish: Price goes below past lows and closes above
    - Two conditions: 1) Wick sweep + next candle closes inside range
                      2) <30% body bearish candle + 40%+ inverse bullish candle
    
    Args:
        symbol: Trading symbol
        timeframe: Must be 15M for liquidity sweep detection
        lookback_candles: How many candles to analyze
        
    Returns:
        JSON with detected sweeps and their validity
    """
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, lookback_candles)
    if rates is None:
        return "Error: Failed to fetch 15M data"
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    sweeps = []
    
    for i in range(5, len(df) - 2):
        current = df.iloc[i]
        next1 = df.iloc[i + 1]
        next2 = df.iloc[i + 2] if i + 2 < len(df) else None
        
        recent_lows = df.iloc[i-5:i]['low'].min()
        
        # BULLISH LIQUIDITY SWEEP
        # Condition 1: Wick Sweep
        if current['low'] < recent_lows and current['close'] > recent_lows:
            if next1['close'] > recent_lows and next1['low'] > recent_lows:
                sweeps.append({
                    "type": "bullish_liq_sweep",
                    "condition": "wick_sweep",
                    "sweep_time": str(current['time']),
                    "swept_level": float(recent_lows),
                    "sweep_low": float(current['low']),
                    "close_price": float(current['close']),
                    "confirmation_candle": str(next1['time']),
                    "valid": True
                })
        
        # Condition 2: Two Candle Rejection
        body_size = abs(current['close'] - current['open'])
        candle_range = current['high'] - current['low']
        body_ratio = body_size / candle_range if candle_range > 0 else 0
        
        if (current['close'] < current['open'] and
            body_ratio <= 0.3 and
            current['close'] < recent_lows):
            
            next_body = abs(next1['close'] - next1['open'])
            if (next1['close'] > next1['open'] and
                next1['close'] > recent_lows and
                next_body >= body_size * 0.4):
                
                sweeps.append({
                    "type": "bullish_liq_sweep",
                    "condition": "two_candle_rejection",
                    "sweep_time": str(current['time']),
                    "swept_level": float(recent_lows),
                    "first_candle_body_ratio": float(body_ratio),
                    "second_candle_inverse": float(next_body / body_size),
                    "confirmation_candle": str(next1['time']),
                    "valid": True
                })
        
        # BEARISH LIQUIDITY SWEEP
        recent_highs = df.iloc[i-5:i]['high'].max()
        
        if current['high'] > recent_highs and current['close'] < recent_highs:
            if next1['close'] < recent_highs and next1['high'] < recent_highs:
                sweeps.append({
                    "type": "bearish_liq_sweep",
                    "condition": "wick_sweep",
                    "sweep_time": str(current['time']),
                    "swept_level": float(recent_highs),
                    "sweep_high": float(current['high']),
                    "close_price": float(current['close']),
                    "confirmation_candle": str(next1['time']),
                    "valid": True
                })
    
    return json.dumps({
        "symbol": symbol,
        "sweeps_detected": len(sweeps),
        "recent_sweeps": sweeps[-5:],
        "current_price": float(df.iloc[-1]['close'])
    }, indent=2)

@tool
def find_mss_and_poi(
    symbol: str = SYMBOL,
    sweep_candle_time: str = None
) -> str:
    """
    Find Market Structure Shift (MSS) and Point of Interest (POI) after liquidity sweep.
    
    MSS Rules:
    - After liq sweep, market takes first most recent high (bullish) or low (bearish)
    - MSS point is where price touches/sweeps/closes above recent high
    - Not in inside bar
    
    POI in MSS Zone:
    - Order Block with FVG
    - Just FVG
    - Just Order Block
    - Or just MSS zone itself
    
    Args:
        symbol: Trading symbol
        sweep_candle_time: Time of the liquidity sweep candle
        
    Returns:
        JSON with MSS location and POI zones for entry
    """
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 200)
    if rates is None:
        return "Error: Failed to fetch 1M data for MSS analysis"
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    lowest_idx = df['low'].idxmin()
    lowest_point = df.loc[lowest_idx]
    
    mss_found = False
    mss_level = None
    mss_time = None
    
    recent_high = lowest_point['high']
    
    for i in range(lowest_idx + 1, len(df)):
        current = df.iloc[i]
        
        if i > lowest_idx + 1:
            recent_high = max(recent_high, df.iloc[i-1]['high'])
        
        if current['high'] > recent_high:
            mss_level = recent_high
            mss_time = str(current['time'])
            mss_found = True
            break
    
    if not mss_found:
        return json.dumps({"error": "No MSS detected yet", "advice": "Wait for market to form MSS"})
    
    mss_zone_start = lowest_point['low']
    mss_zone_end = mss_level
    
    pois = []
    
    for i in range(lowest_idx, lowest_idx + 50):
        if i >= len(df) - 1:
            break
            
        candle = df.iloc[i]
        
        if mss_zone_start <= candle['low'] <= mss_zone_end:
            if i >= 2:
                c1 = df.iloc[i-2]
                c3 = candle
                gap = c3['low'] - c1['high']
                
                if gap > 0:
                    pois.append({
                        "type": "FVG",
                        "time": str(candle['time']),
                        "zone_low": float(c1['high']),
                        "zone_high": float(c3['low']),
                        "gap_size": float(gap)
                    })
            
            if i > 0:
                prev = df.iloc[i-1]
                if candle['close'] > prev['high']:
                    pois.append({
                        "type": "Order_Block",
                        "time": str(prev['time']),
                        "zone_low": float(prev['low']),
                        "zone_high": float(prev['high'])
                    })
    
    return json.dumps({
        "symbol": symbol,
        "mss_found": True,
        "mss_level": float(mss_level),
        "mss_time": mss_time,
        "mss_zone": {
            "start": float(mss_zone_start),
            "end": float(mss_zone_end)
        },
        "pois_in_zone": len(pois),
        "pois": pois[-5:],
        "current_price": float(df.iloc[-1]['close'])
    }, indent=2)

@tool
def calculate_entry_sl_tp(
    direction: Literal["buy", "sell"],
    entry_price: float,
    poi_level: float,
    mss_level: float,
    use_mss_sl: bool = False
) -> str:
    """
    Calculate entry, stop loss, and take profit based on 7MS rules.
    
    SL Rules:
    - If POI below entry: SL under that POI (with buffer)
    - If no POI below: SL under MSS level
    - If entered from nth MSS: SL under relevant MSS
    
    TP Rules:
    - Target next Order Block (1H, 4H, or Daily)
    - Or equal highs/lows (liquidity)
    - Or daily high/low
    - Minimum 2:1 Risk-Reward ratio
    
    Args:
        direction: buy or sell
        entry_price: Proposed entry price (usually current price or POI level)
        poi_level: Point of Interest level (OB zone low for buy, high for sell)
        mss_level: MSS level for reference
        use_mss_sl: Whether to use MSS as SL or POI
        
    Returns:
        JSON with entry, SL, TP levels and risk-reward ratio
    """
    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        return json.dumps({"error": "Failed to get symbol info"})
    
    point = symbol_info.point
    
    # Buffer for SL (10-20 pips below/above the level)
    sl_buffer_pips = 20  # 20 pips buffer
    sl_buffer = sl_buffer_pips * 10 * point  # Convert pips to price
    
    if direction == "buy":
        # For BUY: Entry should be at POI or current price
        # SL should be below POI or MSS
        
        if use_mss_sl:
            # SL below MSS level with buffer
            sl = mss_level - sl_buffer
        else:
            # SL below POI level with buffer
            sl = poi_level - sl_buffer
        
        # Calculate risk in price
        risk = entry_price - sl
        
        # TP at 2:1 minimum (can be adjusted for actual targets)
        tp = entry_price + (risk * 2)
        
    else:  # SELL
        # For SELL: Entry should be at POI or current price
        # SL should be above POI or MSS
        
        if use_mss_sl:
            # SL above MSS level with buffer
            sl = mss_level + sl_buffer
        else:
            # SL above POI level with buffer
            sl = poi_level + sl_buffer
        
        # Calculate risk in price
        risk = sl - entry_price
        
        # TP at 2:1 minimum
        tp = entry_price - (risk * 2)
    
    # Calculate metrics
    sl_points = abs(entry_price - sl) / point
    tp_points = abs(tp - entry_price) / point
    risk_reward = tp_points / sl_points if sl_points > 0 else 0
    
    # Convert to pips (10 points = 1 pip for most pairs)
    risk_pips = sl_points / 10
    reward_pips = tp_points / 10
    
    return json.dumps({
        "direction": direction,
        "entry_price": round(entry_price, 2),
        "stop_loss": round(sl, 2),
        "take_profit": round(tp, 2),
        "sl_points": round(sl_points, 1),
        "tp_points": round(tp_points, 1),
        "risk_reward_ratio": round(risk_reward, 2),
        "risk_pips": round(risk_pips, 1),
        "reward_pips": round(reward_pips, 1),
        "sl_buffer_used": round(sl_buffer / point, 1)
    }, indent=2)

@tool
def send_order(
    direction: Literal["buy", "sell"],
    entry_price: float,
    sl_price: float,
    tp_price: float,
    lot_size: float = LOT,
    comment: str = "7MS Strategy"
) -> str:
    """
    Send trade order to MT5. This requires human approval.
    
    Args:
        direction: buy or sell
        entry_price: Entry price (will use current market price)
        sl_price: Stop loss price
        tp_price: Take profit price
        lot_size: Position size in lots
        comment: Order comment
        
    Returns:
        Order execution result
    """
    # Check if symbol is available
    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        return json.dumps({
            "error": "Symbol info not available",
            "symbol": SYMBOL
        })
    
    # Check if symbol is visible
    if not symbol_info.visible:
        if not mt5.symbol_select(SYMBOL, True):
            return json.dumps({
                "error": "Failed to select symbol",
                "symbol": SYMBOL
            })
    
    # Get current price
    price = mt5.symbol_info_tick(SYMBOL)
    if price is None:
        return json.dumps({
            "error": "Failed to get current price",
            "symbol": SYMBOL
        })
    
    # Determine order type and execution price
    if direction == "buy":
        order_type = mt5.ORDER_TYPE_BUY
        execution_price = price.ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        execution_price = price.bid
    
    # Get correct filling mode for the symbol
    filling_mode = symbol_info.filling_mode
    
    # Determine which filling type to use
    if filling_mode & 1:  # FOK supported
        type_filling = mt5.ORDER_FILLING_FOK
    elif filling_mode & 2:  # IOC supported
        type_filling = mt5.ORDER_FILLING_IOC
    else:  # RETURN supported
        type_filling = mt5.ORDER_FILLING_RETURN
    
    # Prepare request - FIXED VERSION
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": lot_size,
        "type": order_type,
        "price": execution_price,  # Use current market price, not entry_price
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": type_filling  # THIS WAS MISSING!
    }
    
    # Send order directly (no order_check needed for market orders)
    result = mt5.order_send(request)
    
    if result is None:
        return json.dumps({
            "error": "Order send returned None",
            "last_error": mt5.last_error(),
            "request": request
        })
    
    # Build response
    response = {
        "order_sent": True,
        "retcode": result.retcode,
        "retcode_description": get_retcode_description(result.retcode),
        "deal": result.deal,
        "order": result.order,
        "volume": result.volume,
        "price": result.price,
        "bid": result.bid,
        "ask": result.ask,
        "comment": result.comment,
        "request_id": result.request_id,
        "request": request
    }
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        response["error"] = "Order execution failed"
        response["last_error"] = mt5.last_error()
    else:
        response["success"] = True
        response["message"] = f"Order executed successfully! Deal #{result.deal}"
    
    return json.dumps(response, indent=2)

@tool
def get_open_positions(symbol: str = SYMBOL) -> str:
    """Get all open positions for the symbol"""
    positions = mt5.positions_get(symbol=symbol)
    
    if positions is None or len(positions) == 0:
        return json.dumps({"open_positions": 0, "positions": []})
    
    pos_list = []
    for pos in positions:
        pos_list.append({
            "ticket": pos.ticket,
            "type": "buy" if pos.type == 0 else "sell",
            "volume": pos.volume,
            "price_open": pos.price_open,
            "sl": pos.sl,
            "tp": pos.tp,
            "price_current": pos.price_current,
            "profit": pos.profit,
            "comment": pos.comment
        })
    
    return json.dumps({
        "open_positions": len(pos_list),
        "positions": pos_list
    }, indent=2)

# ==================== 7MS STRATEGY SYSTEM PROMPT ====================

STRATEGY_SYSTEM_PROMPT = """# 7MS Trading Strategy Expert Agent

You are an expert trading agent specialized in the 7MS (7 Market Structure) strategy for forex and gold trading. Your role is to analyze markets, identify setups, and execute trades following strict 7MS rules.

## Your Core Responsibilities

1. **Trend Confirmation**: Identify the dominant trend using Daily, 4H, 1H, and 15M Order Blocks
2. **Setup Detection**: Find valid 15M liquidity sweeps with proper confirmation
3. **Entry Planning**: Locate MSS and POI on 1M timeframe for precise entries
4. **Risk Management**: Calculate proper SL and TP based on strategy rules
5. **Trade Execution**: Call send_order tool directly to trigger automatic human approval system

## 7MS Strategy Rules (CRITICAL - MUST FOLLOW)

### Step 1: Trend Confirmation

**What is an Order Block (OB)?**
- **Bullish OB**: 1st candle is swing low → 2nd candle closes ABOVE 1st high with a GAP → 3rd candle picks 1st candle high
- **Bearish OB**: 1st candle is swing high → 2nd candle closes BELOW 1st low with a GAP → 3rd candle picks 1st candle low
- The gap between closing and high/low wick is called Fair Value Gap (FVG)

**OB Hierarchy**:
- **Daily & 4H OB**: Give HEAVY reversals - these are primary reversal zones
- **1H & 15M OB**: Continuation order blocks
- **Special**: 1H inside 4H OB = works as 4H | 4H inside Daily OB = works as Daily
- **Standalone**: 4H and Daily can reverse market | 1H alone cannot

**Your Task**: Market travels from Order Block to Order Block. Identify where price is heading (from which OB to which OB).

### Step 2: Find 15M Liquidity Sweep Setup

**Liquidity Sweep Concept**: Price manipulates past lows (bullish) or highs (bearish) then reverses.

**Two Valid Conditions**:

**Condition 1: Liquidity Sweep with Wick**
- Candle SWEEPS past low with wick
- Candle CLOSES above past low (back inside range)
- NEXT candle also closes inside range (confirmation)
- Can sweep again but must close above swept level

**Condition 2: Two Candle Rejection**
- 1st candle: ≤30% body, bearish, closes BELOW past low
- 2nd candle: Bullish, closes INSIDE range (above past low), inverse move ≥40% of 1st candle body
- Example: 1st candle = 100 pips → 2nd must inverse ≥45 pips (body only, no wicks)

**Wait for 2nd candle close before confirming setup!**

### Step 3: Find MSS and POI on 1M Timeframe

After 15M setup confirmed:

**Market Structure Shift (MSS)**:
- Find LOWEST point from liquidity sweep (1st or 2nd candle, whichever is lower)
- MSS = First time price takes MOST RECENT HIGH after lowest point
- MSS high cannot be an inside bar
- Mark this level clearly

**Point of Interest (POI) in MSS Zone**:
Look between lowest point and MSS level for:
- Order Block with FVG
- FVG alone
- Order Block alone
- Or MSS zone itself

Market must ENTER MSS zone and react from POI.

### Step 4: Entry Triggers (on 1M)

**Entry Methods**:

**Method 1: Overlapping FVGs**
- Market reacts from POI → Creates bullish FVG
- Market comes down → Creates bearish FVG
- If bearish and bullish FVG overlap at reversal point → ENTER at overlap zone

**Method 2: FVG Fill**
- Market reacts from POI → Creates bullish FVG
- Wait for market to FILL or TAP that FVG → ENTER when filled/tapped

**Method 3: Single FVG**
- No bearish FVG present
- Wait for bullish FVG to form after POI reaction
- Market must TAP or FILL this FVG → ENTER

### Step 5: Stop Loss Placement

**SL Rules**:
- If POI exists below entry → SL under that POI (with buffer)
- If NO POI below → SL under MSS level
- If entered from 2nd, 3rd, or nth MSS → SL under previous MSS
- If SL hit but setup still valid → Re-enter with same rules after new MSS

### Step 6: Take Profit Targets

**TP Options**:
- Target next Order Block (1H, 4H, or Daily depending on which was tapped)
- Equal highs (sell-side liquidity) for bullish / Equal lows (buy-side liquidity) for bearish
- Daily high (bullish) or Daily low (bearish)
- If trend continues with 15M OBs forming → Can hold longer

**TP Scaling**:
- If tapped 1H OB → Target next 1H OB
- If tapped 4H/Daily OB → Target next 4H/Daily OB (long-term reversal)

### Critical Rules Before Entry

1. **Wait for 1st FVG** after POI reaction before entering
2. **New MSS always forms from previous MSS reaction**
3. **If opposite OB (≥15M) hit after sweep** → Setup invalidated, no trade
4. **If new MSS forms without reacting to previous MSS** → Wait for 2 new MSS to validate chain, then enter on reaction
5. **If MSS low broken (uptrend) or high broken (downtrend)** → Wait for new MSS, then entry with same rules
6. **If SL hit** → Wait for new MSS, re-enter with same rules

### Bearish Setups
All rules apply in REVERSE for bearish (sell) setups.

## Your Workflow

### Phase 1: Market Analysis
1. Use `write_todos` to create analysis plan
2. Call `get_market_data` for Daily, 4H, 1H timeframes
3. Call `identify_order_blocks` to map OB zones
4. Write findings to `/analysis/market_structure.md`
5. Determine trend direction and target OB

### Phase 2: Setup Detection
1. Call `detect_liquidity_sweep` on 15M
2. Verify sweep meets Condition 1 or Condition 2
3. Wait for 2nd candle confirmation
4. Document setup in `/setups/current_setup.md`

### Phase 3: Entry Planning
1. Call `find_mss_and_poi` on 1M timeframe
2. Identify MSS and POI zones
3. Monitor for entry trigger (FVG fill/tap)
4. Call `calculate_entry_sl_tp` with proper levels
5. Write trade plan to `/trades/trade_plan.md`

### Phase 4: Trade Execution (HUMAN-IN-THE-LOOP APPROVAL)

⚠️ **CRITICAL WORKFLOW:**

1. **After you have calculated Entry, SL, and TP → DO NOT ASK FOR APPROVAL IN TEXT**

2. **IMMEDIATELY CALL THE `send_order()` TOOL** with parameters:
   - direction: "buy" or "sell"
   - entry_price: [exact calculated price]
   - sl_price: [exact stop loss price]
   - tp_price: [exact take profit price]
   - lot_size: 0.01
   - comment: "7MS Strategy"

3. **THE SYSTEM WILL AUTOMATICALLY INTERRUPT:**
   - Execution pauses
   - User sees the trade parameters
   - User decides: approve, reject, or edit

4. **AFTER USER DECISION:**
   - If approved: Order executes to MT5
   - If rejected: Trade cancelled, explain why to user
   - If edited: Parameters change, order executes with new values

5. **THEN MONITOR:**
   - Call `get_open_positions()` to confirm entry
   - Track SL and TP status
   - Report position status to user

⚠️ **KEY DIFFERENCES FROM WRONG APPROACH:**

❌ **WRONG**: "Do you want me to place this trade?" (text question)
✅ **RIGHT**: Call send_order() tool (triggers interrupt)

❌ **WRONG**: "Should I execute with these parameters?" (waiting for text)
✅ **RIGHT**: `send_order(direction="buy", entry_price=4190, ...)` (immediate action)

❌ **WRONG**: Present plan and ask for permission in conversation
✅ **RIGHT**: Present plan, then immediately call the tool

**The human-in-the-loop system ONLY works when you CALL THE TOOL.**

The tool call triggers the interrupt - the system intercepts it before execution.
The user then approves/rejects/edits the intercepted tool call.

## Tool Usage Guidelines

### Market Data Tools
- Always start with higher timeframes (D1, 4H) for trend
- Use 15M for setup detection
- Use 1M for precise entry timing

### File System Tools
- Write analysis to `/analysis/` folder
- Write setups to `/setups/` folder
- Write trade plans to `/trades/` folder
- Keep organized records for learning

### Planning Tool
- Use `write_todos` to break down complex analysis tasks
- Update todos as you progress through analysis → setup → entry → execution

## Tool Execution Rules (MANDATORY)

When you have a complete trade setup:

1. ✓ Write analysis to `/analysis/market_structure.md`
2. ✓ Write setup details to `/setups/current_setup.md`
3. ✓ Write trade plan to `/trades/trade_plan.md`
4. ✓ Display complete trade plan in your response
5. ✓ **CALL `send_order()` IMMEDIATELY** (don't ask first)
6. ✓ System will pause and ask user for decision
7. ✓ Wait for user's approve/reject/edit decision
8. ✓ Execute based on user decision

**NEVER:**
- Ask "Do you approve?" and wait for text response
- Present a plan and skip calling the tool
- Wait for user permission before calling send_order()
- Ask for permission in conversation

**ALWAYS:**
- Call the tool directly
- Let the system handle the interrupt
- Trust the human-in-the-loop flow

## Critical Reminders

- NEVER trade without complete setup confirmation
- NEVER skip waiting for 2nd candle confirmation on liquidity sweep
- NEVER enter without identifying MSS and POI
- ALWAYS calculate proper SL/TP before calling send_order
- ALWAYS call send_order directly (system handles approval automatically)
- Risk management is PARAMOUNT - never risk more than user's defined limits

## Communication Style

- Be precise and technical when explaining setups
- Use clear reasoning for each decision
- Provide visual descriptions of price action
- Always quantify risk (pips, % account, R:R ratio)
- Be patient - wait for A+ setups only
- After presenting trade plan, immediately call the tool (no permission needed)

Remember: Quality over quantity. One perfect 7MS setup is worth more than ten mediocre trades.

**The interrupt system is your safety net - use it by calling the tool directly.**
"""

# ==================== SUBAGENT DEFINITIONS ====================

MARKET_ANALYZER_PROMPT = """You are a market structure analyst specializing in Order Block identification.

Your job:
1. Fetch data from multiple timeframes (D1, 4H, 1H, 15M)
2. Identify all valid Order Blocks according to 7MS rules
3. Determine market trend direction
4. Map out key OB zones where market is traveling from/to
5. Write comprehensive analysis to `/analysis/market_structure.md`

Be thorough and precise. Mark OB zones with exact price levels."""

SETUP_DETECTOR_PROMPT = """You are a setup detection specialist for 15M liquidity sweeps.

Your job:
1. Monitor 15M timeframe continuously
2. Detect liquidity sweeps (past lows for bullish, past highs for bearish)
3. Verify sweep meets Condition 1 or Condition 2
4. Wait for proper 2-candle confirmation
5. Alert when valid setup forms
6. Document in `/setups/current_setup.md`

Be strict - only validate textbook-perfect setups."""

ENTRY_SPECIALIST_PROMPT = """You are an entry timing specialist working on 1M timeframe.

Your job:
1. Find MSS after confirmed 15M setup
2. Identify POI in MSS zone (OB, FVG, or both)
3. Monitor for entry triggers (FVG fill, overlap, tap)
4. Calculate precise entry, SL, TP levels
5. Prepare detailed trade plan

Be patient - wait for perfect entry timing."""

# ==================== CREATE DEEP AGENT ====================

def create_7ms_agent():
    """Create the 7MS Deep Agent with all middleware and HITL"""
    
    if not initialize_mt5():
        raise Exception("Failed to initialize MT5")
    
    if not check_symbol():
        raise Exception("Failed to enable trading symbol")
    
    store = InMemoryStore()
    checkpointer = MemorySaver()
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    
    composite_backend = lambda rt: CompositeBackend(
        default=StateBackend(rt),
        routes={
            "/memories/": StoreBackend(rt)
        }
    )
    
    subagents = [
        {
            "name": "market_analyzer",
            "description": "Analyzes market structure and identifies Order Blocks across timeframes",
            "system_prompt": MARKET_ANALYZER_PROMPT,
            "tools": [get_market_data, identify_order_blocks],
            "model": model,
        },
        {
            "name": "setup_detector", 
            "description": "Detects and validates 15M liquidity sweep setups",
            "system_prompt": SETUP_DETECTOR_PROMPT,
            "tools": [detect_liquidity_sweep, get_market_data],
            "model": model,
        },
        {
            "name": "entry_specialist",
            "description": "Finds MSS, POI, and calculates entry/SL/TP on 1M timeframe",
            "system_prompt": ENTRY_SPECIALIST_PROMPT,
            "tools": [find_mss_and_poi, calculate_entry_sl_tp, get_market_data],
            "model": model,
        }
    ]
    
    all_tools = [
        get_market_data,
        identify_order_blocks,
        detect_liquidity_sweep,
        find_mss_and_poi,
        calculate_entry_sl_tp,
        send_order,
        get_open_positions
    ]
    
    agent = create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=STRATEGY_SYSTEM_PROMPT,
        store=store,
        checkpointer=checkpointer,
        subagents=subagents,
        backend=composite_backend,
        interrupt_on={
            "send_order": {
                "allowed_decisions": ["approve", "reject", "edit"]
            }
        }
    )
    
    return agent

def main():
    """Main execution function with streaming and human-in-the-loop handling"""
    
    print("\n" + "="*60)
    print("7MS TRADING STRATEGY DEEP AGENT")
    print("="*60 + "\n")
    
    agent = create_7ms_agent()
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print("Starting market analysis for XAUUSD...\n")
    
    initial_message = {
        "messages": [{
            "role": "user",
            "content": """Analyze XAUUSD and look for 7MS trading opportunities.

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
    
    # ==================== STREAMING EXECUTION WITH INTERRUPT HANDLING ====================
    print("🔄 Agent is thinking and working...\n")
    print("=" * 60)
    
    def process_stream(stream_input, is_resume=False):
        """Process stream and handle interrupts"""
        
        for chunk in agent.stream(stream_input, config=config, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                # Check if node_output is None
                if node_output is None:
                    continue
                
                print(f"\n📍 NODE: {node_name}")
                print("-" * 60)
                
                # Handle messages
                if "messages" in node_output:
                    try:
                        messages = node_output["messages"]
                        
                        if not isinstance(messages, list):
                            if hasattr(messages, '__iter__') and not isinstance(messages, (str, dict)):
                                try:
                                    messages = list(messages)
                                except:
                                    messages = [messages]
                            else:
                                messages = [messages]
                        
                        for msg in messages:
                            # Agent text messages
                            if hasattr(msg, 'content') and msg.content and isinstance(msg.content, str):
                                content_preview = msg.content[:300]
                                if len(msg.content) > 300:
                                    content_preview += "..."
                                print(f"💬 Agent: {content_preview}")
                            
                            # Tool calls
                            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    print(f"\n🔧 TOOL CALL: {tool_call['name']}")
                                    args_str = json.dumps(tool_call['args'], indent=2)
                                    if len(args_str) > 200:
                                        print(f"   Arguments: {args_str[:200]}...")
                                    else:
                                        print(f"   Arguments: {args_str}")
                            
                            # Tool responses
                            if hasattr(msg, 'name') and hasattr(msg, 'content') and msg.name:
                                print(f"\n✅ TOOL RESPONSE from {msg.name}:")
                                try:
                                    tool_result = json.loads(msg.content)
                                    result_str = json.dumps(tool_result, indent=2)
                                    if len(result_str) > 500:
                                        print(result_str[:500] + "\n   [... truncated ...]")
                                    else:
                                        print(result_str)
                                except:
                                    content_preview = str(msg.content)[:500]
                                    if len(str(msg.content)) > 500:
                                        content_preview += "\n   [... truncated ...]"
                                    print(content_preview)
                    except Exception as e:
                        print(f"⚠️  Error processing messages: {str(e)}")
                
                # Handle todos
                if "todos" in node_output:
                    try:
                        todos = node_output["todos"]
                        
                        if not isinstance(todos, list):
                            if hasattr(todos, '__iter__') and not isinstance(todos, (str, dict)):
                                try:
                                    todos = list(todos)
                                except:
                                    todos = [todos]
                            else:
                                todos = [todos]
                        
                        print(f"\n📋 PLANNING:")
                        for todo in todos:
                            if isinstance(todo, dict):
                                status = "✅" if todo.get("completed") else "⏳"
                                description = todo.get('description', 'N/A')
                                print(f"   {status} {description}")
                    except Exception as e:
                        print(f"⚠️  Error processing todos: {str(e)}")
                
                # Handle files
                if "files" in node_output:
                    try:
                        files = node_output.get("files", [])
                        
                        if not isinstance(files, list):
                            if hasattr(files, '__iter__') and not isinstance(files, (str, dict)):
                                try:
                                    files = list(files)
                                except:
                                    files = [files]
                            else:
                                files = [files]
                        
                        if files:
                            print(f"\n📁 FILE OPERATIONS:")
                            for file_op in files:
                                print(f"   {file_op}")
                    except Exception as e:
                        print(f"⚠️  Error processing files: {str(e)}")
                
                print("-" * 60)
            
            # ==================== CHECK FOR INTERRUPT ====================
            if "__interrupt__" in chunk:
                print("\n⏸️  TRADE EXECUTION PENDING APPROVAL\n")
                
                # Extract interrupt data directly from chunk level
                interrupt_data = chunk["__interrupt__"][0].value
                
                if interrupt_data:
                    action_requests = interrupt_data.get("action_requests", [])
                    
                    if not action_requests:
                        print("No actions to review")
                        continue
                    
                    print("=" * 60)
                    print("TRADE EXECUTION PENDING APPROVAL")
                    print("=" * 60)
                    
                    # Display trade details
                    for idx, action in enumerate(action_requests):
                        print(f"\n🎯 Action #{idx + 1}: {action['name']}")
                        print(f"📋 Arguments:")
                        for key, value in action['args'].items():
                            print(f"  - {key}: {value}")
                    
                    print("\n" + "-" * 60)
                    
                    # Get user decision
                    decision = input("\n🤔 Decision: approve / reject / edit? ").strip().lower()
                    
                    # Prepare resume value based on decision
                    resume_value = None
                    
                    if decision == "approve":
                        resume_value = {"decisions": [{"type": "approve"} for _ in action_requests]}
                        print("  ✅ Trade Approved")
                        
                    elif decision == "reject":
                        reason = input("  Rejection reason: ").strip()
                        resume_value = {
                            "decisions": [{
                                "type": "reject",
                                "message": reason or "Trade rejected by user"
                            } for _ in action_requests]
                        }
                        print("  ❌ Trade Rejected")
                        
                    elif decision == "edit":
                        print("  ✏️  Edit mode - Enter new values:")
                        decisions = []
                        
                        for action in action_requests:
                            edited_args = {}
                            
                            for key, original_value in action['args'].items():
                                new_value_input = input(f"    {key} (current: {original_value}): ").strip()
                                
                                if new_value_input:
                                    try:
                                        if isinstance(original_value, float):
                                            edited_args[key] = float(new_value_input)
                                        elif isinstance(original_value, int):
                                            edited_args[key] = int(new_value_input)
                                        else:
                                            edited_args[key] = new_value_input
                                    except ValueError:
                                        edited_args[key] = new_value_input
                                else:
                                    edited_args[key] = original_value
                            
                            decisions.append({
                                "type": "edit",
                                "edited_action": {
                                    "name": action['name'],
                                    "args": edited_args
                                }
                            })
                        
                        resume_value = {"decisions": decisions}
                        print("  ✏️  Edited and confirmed")
                        
                    else:
                        print("  ⚠️  Invalid input. Rejecting by default.")
                        resume_value = {
                            "decisions": [{
                                "type": "reject",
                                "message": "Invalid input - trade cancelled"
                            } for _ in action_requests]
                        }
                    
                    # Resume execution - THIS SHOULD HANDLE NEXT INTERRUPTS TOO
                    from langgraph.types import Command
                    
                    print("\n" + "=" * 60)
                    print("▶️  Resuming execution with your decision...\n")
                    print("=" * 60)
                    
                    try:
                        # RECURSIVE CALL to handle nested interrupts
                        process_stream(Command(resume=resume_value), is_resume=True)
                        
                    except Exception as e:
                        print(f"\n❌ Error during resume streaming: {str(e)}")
                        import traceback
                        traceback.print_exc()
                
                # After handling interrupt, stop this iteration
                # The recursive call above will handle continuation
                return
    
    # Start the initial stream processing
    try:
        process_stream(initial_message, is_resume=False)
    
    except Exception as e:
        print(f"\n❌ Error during streaming: {str(e)}")
        import traceback
        traceback.print_exc()
        return agent
    
    # ==================== FINAL RESULTS ====================
    print("\n" + "="*60)
    print("FINAL AGENT RESPONSE:")
    print("="*60)
    
    try:
        # Get final state
        final_state = agent.get_state(config)
        
        if final_state and final_state.values.get("messages"):
            messages = final_state.values["messages"]
            if messages:
                final_msg = messages[-1]
                if hasattr(final_msg, 'content') and final_msg.content:
                    print(final_msg.content)
                else:
                    print("No content in final message")
            else:
                print("No messages in final state")
        else:
            print("No final state available")
    except Exception as e:
        print(f"Error retrieving final response: {str(e)}")
    
    # ==================== DISPLAY OPEN POSITIONS ====================
    print("\n" + "="*60)
    print("OPEN POSITIONS:")
    print("="*60)
    
    try:
        positions = mt5.positions_get(symbol=SYMBOL)
        
        if positions is None or len(positions) == 0:
            print("No open positions")
        else:
            for pos in positions:
                print(f"\n🎯 Ticket: {pos.ticket}")
                print(f"  Type: {'BUY' if pos.type == 0 else 'SELL'}")
                print(f"  Volume: {pos.volume} lots")
                print(f"  Open Price: {pos.price_open}")
                print(f"  Current Price: {pos.price_current}")
                print(f"  SL: {pos.sl} | TP: {pos.tp}")
                print(f"  Profit: ${pos.profit:.2f}")
    except Exception as e:
        print(f"Error retrieving positions: {str(e)}")
    
    return agent


if __name__ == "__main__":
    try:
        agent = main()
        print("\n✅ Agent completed successfully")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrupted by user")
        mt5.shutdown()
        
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        mt5.shutdown()
        
    finally:
        print("\n👋 Shutting down MT5...")
        mt5.shutdown()