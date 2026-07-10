import pandas as pd
import numpy as np
from datetime import datetime
from app.utils.logger import logger

class MT5Connector:
    def __init__(self):
        self.is_connected = False
        self.trend_state = {}
        self.signal_counter = 0
        logger.info("MT5 Connector initialized - XAUUSD Only")
    
    def connect(self):
        self.is_connected = True
        logger.info("MT5 Connected")
        return True
    
    def disconnect(self):
        self.is_connected = False
        logger.info("MT5 Disconnected")
    
    def get_market_data(self, symbol, timeframe="M1", bars=100):
        """Generate XAUUSD data with CONSTANT signals"""
        
        config = {'base': 2350.0, 'volatility': 0.003, 'trend_strength': 2.0}
        
        if symbol not in self.trend_state:
            self.trend_state[symbol] = {
                'trend': 1,
                'base_price': config['base'],
                'cycle': 0
            }
        
        state = self.trend_state[symbol]
        state['cycle'] += 1
        
        # Force trend change every 3 cycles for variety
        if state['cycle'] % 3 == 0:
            state['trend'] *= -1
            logger.info(f"🔄 XAUUSD Trend: {'UP' if state['trend'] == 1 else 'DOWN'}")
        
        # Generate prices with clear trends
        prices = []
        current_price = state['base_price']
        
        for i in range(bars):
            # Strong trend
            trend_move = state['trend'] * 0.008 * current_price
            noise = np.random.normal(0, config['volatility']) * current_price
            
            change = trend_move + noise
            current_price += change
            
            # Keep in range
            if current_price < state['base_price'] * 0.85:
                current_price = state['base_price'] * 0.85
                state['trend'] = 1
            elif current_price > state['base_price'] * 1.15:
                current_price = state['base_price'] * 1.15
                state['trend'] = -1
            
            prices.append(current_price)
        
        state['base_price'] = prices[-1]
        
        # FORCE SIGNALS - Create extreme movements every cycle
        if state['cycle'] % 2 == 0:
            # Force a strong signal
            force_direction = 1 if state['trend'] == 1 else -1
            for j in range(-8, 0):
                prices[j] = prices[j] * (1 + force_direction * 0.01 * (9 + j))
            logger.info(f"💪 FORCED XAUUSD {'UP' if force_direction == 1 else 'DOWN'} trend for signal")
        
        # Update prices
        df = pd.DataFrame({
            'open': prices,
            'high': [p * (1 + np.random.uniform(0, 0.005)) for p in prices],
            'low': [p * (1 - np.random.uniform(0, 0.005)) for p in prices],
            'close': prices,
            'volume': np.random.randint(100, 1000, bars)
        })
        
        logger.info(f"📊 XAUUSD: {prices[-1]:.2f} | Trend: {'UP' if state['trend'] == 1 else 'DOWN'}")
        
        return df
