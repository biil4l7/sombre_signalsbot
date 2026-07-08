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
        logger.info("MT5 Connector initialized - XAUUSD Only")
    
    def connect(self):
        self.is_connected = True
        logger.info("MT5 Connected")
        return True
    
    def disconnect(self):
        self.is_connected = False
        logger.info("MT5 Disconnected")
    
    def get_market_data(self, symbol, timeframe="M1", bars=100):
        """Generate XAUUSD (Gold) market data with frequent signals"""
        
        config = {
            'base': 2350.0,
            'volatility': 0.002,
            'trend_strength': 1.5
        }
        
        if symbol not in self.trend_state:
            self.trend_state[symbol] = {
                'trend': np.random.choice([-1, 1]),
                'strength': np.random.uniform(0.8, 1.8) * config['trend_strength'],
                'base_price': config['base'],
                'cycle': 0
            }
        
        state = self.trend_state[symbol]
        state['cycle'] += 1
        
        # Change trend more often for more signals
        if np.random.random() < 0.1:  # 10% chance - more frequent changes
            state['trend'] *= -1
            state['strength'] = np.random.uniform(0.8, 1.8) * config['trend_strength']
            logger.info(f"🔄 XAUUSD Trend: {'UP' if state['trend'] == 1 else 'DOWN'}")
        
        # Generate price data
        prices = []
        current_price = state['base_price']
        
        for i in range(bars):
            trend_move = state['trend'] * state['strength'] * 0.004 * current_price
            noise = np.random.normal(0, config['volatility']) * current_price
            
            if np.random.random() < 0.02:
                spike = np.random.choice([-1, 1]) * 0.015 * current_price
            else:
                spike = 0
            
            change = trend_move + noise + spike
            current_price += change
            
            if current_price < state['base_price'] * 0.90:
                current_price = state['base_price'] * 0.90
                state['trend'] = 1
            elif current_price > state['base_price'] * 1.10:
                current_price = state['base_price'] * 1.10
                state['trend'] = -1
            
            prices.append(current_price)
        
        state['base_price'] = prices[-1]
        
        # FORCE MORE SIGNALS - Create clear trends every cycle
        last_10 = prices[-10:]
        if len(last_10) > 5 and state['cycle'] % 2 == 0:
            force_trend = np.random.choice([-1, 1])
            if force_trend == 1:
                for j in range(-5, 0):
                    prices[j] = prices[j] * (1 + 0.005 * (6 + j))
                logger.info("💪 Forced UP trend for XAUUSD")
            else:
                for j in range(-5, 0):
                    prices[j] = prices[j] * (1 - 0.005 * (6 + j))
                logger.info("💪 Forced DOWN trend for XAUUSD")
        
        df = pd.DataFrame({
            'open': prices,
            'high': [p * (1 + np.random.uniform(0, 0.004)) for p in prices],
            'low': [p * (1 - np.random.uniform(0, 0.004)) for p in prices],
            'close': prices,
            'volume': np.random.randint(100, 1000, bars)
        })
        
        logger.info(f"📊 XAUUSD - Price: {prices[-1]:.2f}, Trend: {'UP' if state['trend'] == 1 else 'DOWN'}")
        
        return df
