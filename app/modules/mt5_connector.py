import pandas as pd
import numpy as np
from datetime import datetime
from app.utils.logger import logger

class MT5Connector:
    def __init__(self):
        self.is_connected = False
        self.last_data = {}
        logger.info("MT5 Connector initialized")
    
    def connect(self):
        self.is_connected = True
        logger.info("MT5 Connected")
        return True
    
    def disconnect(self):
        self.is_connected = False
        logger.info("MT5 Disconnected")
    
    def get_market_data(self, symbol, timeframe="M1", bars=100):
        # Generate mock data for testing
        np.random.seed(42)
        base_price = 145.0 if symbol == 'USDJPY' else 0.9 if symbol == 'USDCHF' else 5.5
        if symbol == 'USDBRL':
            base_price = 5.8
        elif symbol == 'JODCNY':
            base_price = 9.2
        
        prices = [base_price]
        for i in range(bars - 1):
            change = np.random.normal(0, 0.001) * base_price
            prices.append(prices[-1] + change)
        
        df = pd.DataFrame({
            'open': prices,
            'high': [p * 1.001 for p in prices],
            'low': [p * 0.999 for p in prices],
            'close': prices,
            'volume': np.random.randint(100, 1000, bars)
        })
        
        return df
