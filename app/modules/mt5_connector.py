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
        logger.info("MT5 Connector initialized")
    
    def connect(self):
        self.is_connected = True
        logger.info("MT5 Connected")
        return True
    
    def disconnect(self):
        self.is_connected = False
        logger.info("MT5 Disconnected")
    
    def get_market_data(self, symbol, timeframe="M1", bars=100):
        """Generate realistic market data with trends"""
        
        # Initialize trend state for this symbol
        if symbol not in self.trend_state:
            self.trend_state[symbol] = {
                'trend': np.random.choice([-1, 1]),  # -1 down, 1 up
                'strength': np.random.uniform(0.5, 1.5),
                'phase': 0,
                'base_price': self._get_base_price(symbol)
            }
        
        state = self.trend_state[symbol]
        
        # Occasionally change trend (every 20-30 bars)
        if np.random.random() < 0.03:  # 3% chance per bar
            state['trend'] *= -1
            state['strength'] = np.random.uniform(0.5, 1.5)
            logger.info(f"🔄 Trend changed for {symbol}: {'UP' if state['trend'] == 1 else 'DOWN'}")
        
        # Generate price data with realistic movements
        prices = []
        current_price = state['base_price']
        
        for i in range(bars):
            # Add trend component
            trend_move = state['trend'] * state['strength'] * 0.002 * current_price
            
            # Add random noise
            noise = np.random.normal(0, 0.002) * current_price
            
            # Add occasional spikes (like real markets)
            if np.random.random() < 0.02:  # 2% chance of spike
                spike = np.random.choice([-1, 1]) * 0.01 * current_price
            else:
                spike = 0
            
            # Calculate new price
            change = trend_move + noise + spike
            current_price += change
            
            # Keep price reasonable
            if current_price < state['base_price'] * 0.95:
                current_price = state['base_price'] * 0.95
                state['trend'] = 1  # Bounce up
            elif current_price > state['base_price'] * 1.05:
                current_price = state['base_price'] * 1.05
                state['trend'] = -1  # Bounce down
            
            prices.append(current_price)
        
        # Update base price for next run
        state['base_price'] = prices[-1]
        
        # Create DataFrame
        df = pd.DataFrame({
            'open': prices,
            'high': [p * (1 + np.random.uniform(0, 0.003)) for p in prices],
            'low': [p * (1 - np.random.uniform(0, 0.003)) for p in prices],
            'close': prices,
            'volume': np.random.randint(100, 1000, bars)
        })
        
        # Log if we're getting good signals
        self.signal_counter += 1
        if self.signal_counter % 5 == 0:
            logger.info(f"📊 {symbol} - Current price: {prices[-1]:.4f}, Trend: {'UP' if state['trend'] == 1 else 'DOWN'}")
        
        return df
    
    def _get_base_price(self, symbol):
        """Get base price for each symbol"""
        base_prices = {
            'USDJPY': 145.0,
            'USDCHF': 0.89,
            'USDBRL': 5.80,
            'JODCNY': 9.20
        }
        return base_prices.get(symbol, 100.0)
