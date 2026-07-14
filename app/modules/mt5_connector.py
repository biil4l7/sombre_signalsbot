import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from app.utils.logger import logger

class MT5Connector:
    def __init__(self):
        self.is_connected = False
        logger.info("MT5 Connector initialized - Real Data (Yahoo Finance)")
    
    def connect(self):
        self.is_connected = True
        logger.info("MT5 Connected")
        return True
    
    def disconnect(self):
        self.is_connected = False
        logger.info("MT5 Disconnected")
    
    def get_market_data(self, symbol, timeframe="M1", bars=100):
        """
        Fetch REAL XAUUSD data from Yahoo Finance.
        Falls back to mock data if fetch fails.
        """
        try:
            # Yahoo Finance symbol for Gold (XAUUSD = GC=F)
            ticker = "GC=F"
            
            # Request 1-minute data for the last 'bars' minutes
            end = datetime.now()
            start = end - timedelta(minutes=bars + 10)  # extra buffer
            
            df = yf.download(ticker, start=start, end=end, interval="1m", progress=False)
            
            if df.empty:
                logger.warning("No data from Yahoo Finance, using mock fallback")
                return self._generate_mock_data(bars)
            
            # Rename columns to match expected format
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Keep only the last 'bars' rows
            df = df.tail(bars)
            
            # Log current price
            current_price = df['close'].iloc[-1]
            logger.info(f"📊 XAUUSD REAL: ${current_price:.2f} at {datetime.now().strftime('%H:%M:%S')}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching real data: {e}")
            logger.info("Using mock data fallback")
            return self._generate_mock_data(bars)
    
    def _generate_mock_data(self, bars=100):
        """Fallback mock data generator (same as before)"""
        np.random.seed(42)
        base_price = 2350.0
        prices = [base_price]
        for i in range(bars - 1):
            change = np.random.normal(0, 0.002) * prices[-1]
            prices.append(prices[-1] + change)
        
        return pd.DataFrame({
            'open': prices,
            'high': [p * 1.001 for p in prices],
            'low': [p * 0.999 for p in prices],
            'close': prices,
            'volume': np.random.randint(100, 1000, bars)
        })
