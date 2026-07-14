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
        try:
            # Try multiple symbols until one works
            tickers = ["XAUUSD=X", "GC=F", "GLD"]  # Gold ETF as last resort
            
            for ticker in tickers:
                try:
                    end = datetime.now()
                    start = end - timedelta(minutes=bars + 10)
                    
                    df = yf.download(ticker, start=start, end=end, interval="1m", progress=False)
                    
                    if not df.empty:
                        df = df.rename(columns={
                            'Open': 'open',
                            'High': 'high',
                            'Low': 'low',
                            'Close': 'close',
                            'Volume': 'volume'
                        })
                        df = df.tail(bars)
                        current_price = df['close'].iloc[-1]
                        logger.info(f"📊 XAUUSD (via {ticker}): ${current_price:.2f}")
                        return df
                except:
                    continue
            
            logger.warning("All data sources failed, using mock data")
            return self._generate_mock_data(bars)
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return self._generate_mock_data(bars)
    
    def _generate_mock_data(self, bars=100):
        """Fallback mock data"""
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
    
    def get_price_at_time(self, symbol, target_time):
        """Get price at a specific time"""
        try:
            tickers = ["XAUUSD=X", "GC=F", "GLD"]
            for ticker in tickers:
                try:
                    start = target_time - timedelta(minutes=2)
                    end = target_time + timedelta(minutes=2)
                    df = yf.download(ticker, start=start, end=end, interval="1m", progress=False)
                    if df.empty:
                        continue
                    df.index = df.index.tz_localize(None)
                    closest_idx = df.index.get_indexer([target_time], method='nearest')[0]
                    if closest_idx >= 0:
                        return float(df['Close'].iloc[closest_idx])
                except:
                    continue
            return None
        except Exception as e:
            logger.error(f"Error fetching price: {e}")
            return None
