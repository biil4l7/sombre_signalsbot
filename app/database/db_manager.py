import sqlite3
import os
import json
from datetime import datetime
import secrets
import string
from app.utils.logger import logger

class DatabaseManager:
    def __init__(self, db_path="data/signals.db"):
        self.db_path = db_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
        logger.info(f"Database initialized at {db_path}")
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL,
                signal_time TIMESTAMP,
                bet_time TIMESTAMP,
                expiry_time TIMESTAMP,
                confidence REAL,
                result TEXT,
                profit_loss REAL,
                indicators_triggered TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                telegram_id TEXT UNIQUE,
                first_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP,
                invite_code TEXT,
                invited_by TEXT,
                is_active BOOLEAN DEFAULT 1,
                total_signals_received INTEGER DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invite_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_count INTEGER DEFAULT 0,
                max_uses INTEGER DEFAULT 1,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE,
                total_signals INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_profit REAL DEFAULT 0,
                win_rate REAL DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            INSERT OR IGNORE INTO invite_codes (code, created_by, max_uses)
            VALUES (?, ?, ?)
        ''', ('SOMMER2026', 'system', 10))
        
        conn.commit()
        conn.close()
    
    def add_user_with_invite(self, username, telegram_id, first_name, invite_code=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if invite_code:
            cursor.execute('''
                SELECT code, max_uses, used_count, is_active
                FROM invite_codes WHERE code = ? AND is_active = 1
            ''', (invite_code,))
            invite = cursor.fetchone()
            if not invite:
                conn.close()
                return False, "❌ Invalid invite code"
            code, max_uses, used_count, is_active = invite
            if max_uses > 0 and used_count >= max_uses:
                conn.close()
                return False, "❌ Invite link expired"
        
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute('''
                UPDATE users SET is_active = 1, last_active = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            ''', (telegram_id,))
            conn.commit()
            conn.close()
            return True, "✅ Welcome back!"
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
        current_users = cursor.fetchone()[0]
        if current_users >= 6:
            conn.close()
            return False, "❌ Group is full (max 6 users)"
        
        cursor.execute('''
            INSERT INTO users (username, telegram_id, first_name, invite_code, invited_by, joined_at, last_active)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (username, telegram_id, first_name, invite_code, 'invite_link'))
        
        if invite_code:
            cursor.execute('''
                UPDATE invite_codes SET used_count = used_count + 1
                WHERE code = ?
            ''', (invite_code,))
        
        conn.commit()
        conn.close()
        return True, f"✅ Welcome {first_name}! (User {current_users + 1}/6)"
    
    def generate_invite_link(self, bot_username, custom_code=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if not custom_code:
            alphabet = string.ascii_uppercase + string.digits
            custom_code = ''.join(secrets.choice(alphabet) for _ in range(8))
        cursor.execute('SELECT id FROM invite_codes WHERE code = ?', (custom_code,))
        if cursor.fetchone():
            conn.close()
            return None, "❌ Code already exists"
        cursor.execute('''
            INSERT INTO invite_codes (code, created_by, max_uses, used_count, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (custom_code, 'telegram_bot', 1, 0, 1))
        conn.commit()
        conn.close()
        invite_link = f"https://t.me/{bot_username}?start=invite_{custom_code}"
        return invite_link, "✅ Invite link created"
    
    def save_signal(self, signal_data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signals (symbol, direction, entry_price, signal_time, bet_time, expiry_time, confidence, indicators_triggered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal_data['symbol'],
            signal_data['direction'],
            signal_data['entry_price'],
            signal_data['signal_time'],
            signal_data['bet_time'],
            signal_data['expiry_time'],
            signal_data.get('confidence', 0),
            json.dumps(signal_data.get('indicators', []))
        ))
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return signal_id
    
    def update_signal_result(self, signal_id, result, profit_loss):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE signals SET result = ?, profit_loss = ?
            WHERE id = ?
        ''', (result, profit_loss, signal_id))
        conn.commit()
        conn.close()
        self.update_performance_stats()
    
    def update_performance_stats(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        today = datetime.now().date()
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(profit_loss) as total_profit
            FROM signals
            WHERE DATE(created_at) = DATE(?)
        ''', (today,))
        result = cursor.fetchone()
        if result and result[0] > 0:
            total = result[0]
            wins = result[1] or 0
            losses = result[2] or 0
            total_profit = result[3] or 0
            win_rate = (wins / total * 100) if total > 0 else 0
            cursor.execute('''
                INSERT OR REPLACE INTO performance (date, total_signals, wins, losses, total_profit, win_rate)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (today, total, wins, losses, total_profit, win_rate))
            conn.commit()
        conn.close()
    
    def get_statistics(self, days=7):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                AVG(CASE WHEN result = 'WIN' THEN profit_loss ELSE 0 END) as avg_win,
                AVG(CASE WHEN result = 'LOSS' THEN profit_loss ELSE 0 END) as avg_loss,
                SUM(profit_loss) as total_profit
            FROM signals
            WHERE created_at >= datetime('now', '-' || ? || ' days')
        ''', (days,))
        result = cursor.fetchone()
        conn.close()
        if result and result[0] > 0:
            return {
                'total_signals': result[0],
                'wins': result[1] or 0,
                'losses': result[2] or 0,
                'win_rate': (result[1] / result[0] * 100) if result[0] > 0 else 0,
                'avg_win': result[3] or 0,
                'avg_loss': result[4] or 0,
                'total_profit': result[5] or 0
            }
        return {
            'total_signals': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'total_profit': 0
        }
    
    def get_user_count(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_user_by_telegram_id(self, telegram_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT username, telegram_id, first_name, joined_at, is_active
            FROM users WHERE telegram_id = ?
        ''', (telegram_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            return {
                'username': user[0],
                'telegram_id': user[1],
                'first_name': user[2],
                'joined_at': user[3],
                'is_active': user[4]
            }
        return None
    
    def update_user_activity(self, telegram_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE telegram_id = ?', (telegram_id,))
        conn.commit()
        conn.close()
    
    def get_top_symbols(self, limit=3):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT symbol, COUNT(*) as total,
                   SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                   AVG(CASE WHEN result = 'WIN' THEN profit_loss ELSE 0 END) as avg_profit
            FROM signals WHERE result IS NOT NULL
            GROUP BY symbol ORDER BY wins DESC LIMIT ?
        ''', (limit,))
        symbols = cursor.fetchall()
        conn.close()
        return [{'symbol': s[0], 'total': s[1], 'wins': s[2], 'win_rate': (s[2]/s[1]*100) if s[1]>0 else 0, 'avg_profit': s[3] or 0} for s in symbols]
    
    def get_today_signals(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM signals WHERE DATE(created_at) = DATE("now")')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_today_profit(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(SUM(profit_loss), 0) FROM signals WHERE DATE(created_at) = DATE("now") AND result IS NOT NULL')
        profit = cursor.fetchone()[0]
        conn.close()
        return profit
