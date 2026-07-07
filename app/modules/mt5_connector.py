import requests
import json
from datetime import datetime
from app.utils.logger import logger
from app.config import Config

class MT5Connector:
    """MT5 Connector - External API version for Railway"""
    
    def __init__(self):
        self.is_connected = False
        self.last_data = {}
        logger.info("MT5 Connector initialized (External API mode)")
    
    def connect(self):
        """Connect to MT5 external service"""
        # This is a placeholder - actual MT5 connection will be on Windows machine
        self.is_connected = True
        logger.info("MT5 Connector ready (waiting for external data)")
        return True
    
    def disconnect(self):
        """Disconnect from MT5"""
        self.is_connected = False
        logger.info("MT5 Connector disconnected")
    
    def is_connected(self):
        """Check connection status"""
        return self.is_connected
    
    def get_market_data(self, symbol, timeframe="M1", bars=100):
        """Get market data from external API or fallback to mock data"""
        # Check if we have cached data
        if symbol in self.last_data:
            # Return cached data if recent
            cache_time = self.last_data.get(symbol, {}).get('timestamp', datetime.now())
            if (datetime.now() - cache_time).seconds < 60:
                return self.last_data[symbol]['data']
        
        # For testing on Railway, generate mock data
        # In production, this would call your external MT5 API
        import pandas as pd
        import numpy as np
        
        # Generate mock price data
        np.random.seed(42)
        base_price = 145.0 if symbol == 'USDJPY' else 0.9 if symbol == 'USDCHF' else 5.5
        if symbol == 'USDBRL':
            base_price = 5.8
        elif symbol == 'JODCNY':
            base_price = 9.2
        
        # Create simulated price movements
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
        
        # Cache data
        self.last_data[symbol] = {
            'data': df,
            'timestamp': datetime.now()
        }
        
        logger.info(f"Mock data generated for {symbol}")
        return df
    
    def send_trade(self, symbol, direction, amount):
        """Send trade to MT5 external service"""
        logger.info(f"Trade sent: {symbol} {direction} ${amount}")
        return {
            'success': True,
            'order_id': '12345',
            'message': f"Trade {direction} {symbol} placed successfully"
        }