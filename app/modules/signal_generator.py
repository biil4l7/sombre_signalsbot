import pandas as pd
import numpy as np
from datetime import datetime
from app.utils.logger import logger
from app.config import Config

class SignalGenerator:
    def __init__(self):
        self.signal_history = []
        self.last_signal_time = {}
        self.symbol_scores = {}  # Track scores per symbol
        logger.info("Signal Generator initialized")
    
    def calculate_indicators(self, df):
        try:
            df['MA5'] = df['close'].rolling(window=5).mean()
            df['MA10'] = df['close'].rolling(window=10).mean()
            df['MA20'] = df['close'].rolling(window=20).mean()
            df['MA50'] = df['close'].rolling(window=50).mean()
            
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            
            df['BB_middle'] = df['close'].rolling(window=20).mean()
            df['BB_std'] = df['close'].rolling(window=20).std()
            df['BB_upper'] = df['BB_middle'] + (df['BB_std'] * 2)
            df['BB_lower'] = df['BB_middle'] - (df['BB_std'] * 2)
            
            low_14 = df['low'].rolling(window=14).min()
            high_14 = df['high'].rolling(window=14).max()
            df['STOCH_K'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
            df['STOCH_D'] = df['STOCH_K'].rolling(window=3).mean()
            
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df, symbol):
        try:
            if len(df) < 50:
                return None
            
            df = self.calculate_indicators(df)
            if df is None or len(df) < 2:
                return None
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            signal = {
                'symbol': symbol,
                'timestamp': Config.get_current_time(),
                'price': float(latest['close']),
                'confidence': 0,
                'direction': 'NEUTRAL',
                'indicators': [],
                'score': 0
            }
            
            score = 0
            indicators_triggered = []
            
            # MA Crossover
            if latest['MA5'] > latest['MA20'] and prev['MA5'] <= prev['MA20']:
                score += 20
                indicators_triggered.append('MA Bullish Crossover')
            elif latest['MA5'] < latest['MA20'] and prev['MA5'] >= prev['MA20']:
                score -= 20
                indicators_triggered.append('MA Bearish Crossover')
            
            # RSI
            if latest['RSI'] < 30:
                score += 15
                indicators_triggered.append('RSI Oversold')
            elif latest['RSI'] > 70:
                score -= 15
                indicators_triggered.append('RSI Overbought')
            
            # MACD
            if latest['MACD'] > latest['MACD_signal'] and prev['MACD'] <= prev['MACD_signal']:
                score += 15
                indicators_triggered.append('MACD Bullish')
            elif latest['MACD'] < latest['MACD_signal'] and prev['MACD'] >= prev['MACD_signal']:
                score -= 15
                indicators_triggered.append('MACD Bearish')
            
            # Bollinger Bands
            if latest['close'] <= latest['BB_lower']:
                score += 10
                indicators_triggered.append('At Lower Band')
            elif latest['close'] >= latest['BB_upper']:
                score -= 10
                indicators_triggered.append('At Upper Band')
            
            # Stochastic
            if latest['STOCH_K'] < 20 and latest['STOCH_K'] > latest['STOCH_D']:
                score += 10
                indicators_triggered.append('Stochastic Bullish')
            elif latest['STOCH_K'] > 80 and latest['STOCH_K'] < latest['STOCH_D']:
                score -= 10
                indicators_triggered.append('Stochastic Bearish')
            
            # Trend
            if latest['close'] > latest['MA50']:
                score += 10
                indicators_triggered.append('Uptrend')
            else:
                score -= 10
                indicators_triggered.append('Downtrend')
            
            signal['score'] = score
            signal['indicators'] = indicators_triggered
            
            if score > 20:
                signal['direction'] = 'CALL'
                signal['confidence'] = min(95, 50 + abs(score) * 0.45)
            elif score < -20:
                signal['direction'] = 'PUT'
                signal['confidence'] = min(95, 50 + abs(score) * 0.45)
            else:
                signal['direction'] = 'NEUTRAL'
                signal['confidence'] = 0
            
            # Log if signal is valid
            if signal['confidence'] >= Config.MIN_CONFIDENCE:
                logger.info(f"📈 Signal: {symbol} - {signal['direction']} (Confidence: {signal['confidence']:.1f}%, Score: {score})")
            
            return signal if signal['confidence'] >= Config.MIN_CONFIDENCE else None
            
        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {e}")
            return None
