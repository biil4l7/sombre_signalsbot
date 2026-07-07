import pandas as pd
import numpy as np
from datetime import datetime
from app.utils.logger import logger

class MT5Connector:
    def __init__(self):
        self.is_connected = False
        self.last_data = {}
        self.trend_state = {}
        self.signal_counter = 0
        self.last_signal_time = {}
        logger.info("MT5 Connector initialized")
    
    def connect(self):
        self.is_connected = True
        logger.info("MT5 Connected")
        return True
    
    def disconnect(self):
        self.is_connected = False
        logger.info("MT5 Disconnected")
    
    def get_market_data(self, symbol, timeframe="M1", bars=100):
        """Generate realistic market data with frequent signals"""
        
        if symbol not in self.trend_state:
            self.trend_state[symbol] = {
                'trend': np.random.choice([-1, 1]),
                'strength': np.random.uniform(0.8, 2.0),
                'phase': 0,
                'base_price': self._get_base_price(symbol),
                'signal_count': 0
            }
        
        state = self.trend_state[symbol]
        
        # Change trend more often for more signals (every 10-15 bars)
        if np.random.random() < 0.05:  # 5% chance per bar
            state['trend'] *= -1
            state['strength'] = np.random.uniform(0.8, 2.0)
            logger.info(f"🔄 Trend changed for {symbol}: {'UP' if state['trend'] == 1 else 'DOWN'}")
        
        # Generate price data with clearer trends
        prices = []
        current_price = state['base_price']
        
        for i in range(bars):
            # Stronger trend component
            trend_move = state['trend'] * state['strength'] * 0.003 * current_price
            
            # Random noise
            noise = np.random.normal(0, 0.0015) * current_price
            
            # Occasional spikes
            if np.random.random() < 0.03:  # 3% chance
                spike = np.random.choice([-1, 1]) * 0.015 * current_price
            else:
                spike = 0
            
            change = trend_move + noise + spike
            current_price += change
            
            # Keep price in reasonable range
            if current_price < state['base_price'] * 0.92:
                current_price = state['base_price'] * 0.92
                state['trend'] = 1
            elif current_price > state['base_price'] * 1.08:
                current_price = state['base_price'] * 1.08
                state['trend'] = -1
            
            prices.append(current_price)
        
        state['base_price'] = prices[-1]
        
        df = pd.DataFrame({
            'open': prices,
            'high': [p * (1 + np.random.uniform(0, 0.004)) for p in prices],
            'low': [p * (1 - np.random.uniform(0, 0.004)) for p in prices],
            'close': prices,
            'volume': np.random.randint(100, 1000, bars)
        })
        
        self.signal_counter += 1
        if self.signal_counter % 3 == 0:
            logger.info(f"📊 {symbol} - Price: {prices[-1]:.4f}, Trend: {'UP' if state['trend'] == 1 else 'DOWN'}")
        
        return df
    
    def _get_base_price(self, symbol):
        base_prices = {
            'USDJPY': 145.0,
            'USDCHF': 0.89,
            'USDBRL': 5.80,
            'JODCNY': 9.20
        }
        return base_prices.get(symbol, 100.0)
