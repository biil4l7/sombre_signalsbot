import sqlite3
import os
from datetime import datetime, timedelta
import json
import secrets
import string
from app.utils.logger import logger

class DatabaseManager:
    """Database operations for signal bot with invite system"""
    
    def __init__(self, db_path="data/signals.db"):
        self.db_path = db_path
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
        logger.info(f"Database initialized at {db_path}")
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Signals table
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
                strategy_used TEXT,
                indicators_triggered TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Users table - UPDATED with invite tracking
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
        
        # Invite codes table - NEW
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
        
        # Performance stats table
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
        
        # Insert default invite code if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO invite_codes (code, created_by, max_uses)
            VALUES (?, ?, ?)
        ''', ('DEFAULT2026', 'system', 10))
        
        conn.commit()
        conn.close()
        logger.info("Database tables created successfully")
    
    # ============ USER MANAGEMENT WITH INVITE SYSTEM ============
    
    def add_user_with_invite(self, username, telegram_id, first_name, invite_code=None):
        """Add a user using invite code"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if invite code is valid
        if invite_code:
            cursor.execute('''
                SELECT code, max_uses, used_count, is_active
                FROM invite_codes
                WHERE code = ? AND is_active = 1
            ''', (invite_code,))
            
            invite = cursor.fetchone()
            
            if not invite:
                conn.close()
                return False, "❌ Invalid or expired invite code"
            
            code, max_uses, used_count, is_active = invite
            
            # Check if max uses reached
            if max_uses > 0 and used_count >= max_uses:
                conn.close()
                return False, "❌ This invite link has reached its maximum uses"
        
        # Check if user already exists
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Reactivate user
            cursor.execute('''
                UPDATE users 
                SET is_active = 1, last_active = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            ''', (telegram_id,))
            conn.commit()
            conn.close()
            return True, "✅ Welcome back! You have been reactivated."
        
        # Check user limit
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
        current_users = cursor.fetchone()[0]
        
        if current_users >= 6:  # Max 6 users
            conn.close()
            return False, "❌ The group is full (max 6 users). Please try again later."
        
        # Add new user
        cursor.execute('''
            INSERT INTO users 
            (username, telegram_id, first_name, invite_code, invited_by, joined_at, last_active)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (username, telegram_id, first_name, invite_code, 'invite_link'))
        
        # Update invite code usage
        if invite_code:
            cursor.execute('''
                UPDATE invite_codes 
                SET used_count = used_count + 1
                WHERE code = ?
            ''', (invite_code,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"New user joined: {username} (Telegram: {telegram_id}) via invite: {invite_code}")
        return True, f"✅ Welcome {first_name}! You've joined the signal group. (User {current_users + 1}/6)"
    
    def generate_invite_link(self, bot_username, custom_code=None):
        """Generate a new invite link"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Generate random code if not provided
        if not custom_code:
            # Generate a random 8-character code
            alphabet = string.ascii_uppercase + string.digits
            custom_code = ''.join(secrets.choice(alphabet) for _ in range(8))
        
        # Check if code exists
        cursor.execute('SELECT id FROM invite_codes WHERE code = ?', (custom_code,))
        if cursor.fetchone():
            conn.close()
            return None, "❌ This invite code already exists. Please choose another."
        
        # Insert new invite code (max uses: 1 per link)
        cursor.execute('''
            INSERT INTO invite_codes (code, created_by, max_uses, used_count, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (custom_code, 'telegram_bot', 1, 0, 1))
        
        conn.commit()
        conn.close()
        
        # Generate invite link
        invite_link = f"https://t.me/{bot_username}?start=invite_{custom_code}"
        
        logger.info(f"New invite link generated: {invite_link}")
        return invite_link, f"✅ Invite link created: {invite_link}"
    
    def get_invite_stats(self):
        """Get invite statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_codes,
                SUM(used_count) as total_uses
            FROM invite_codes
            WHERE is_active = 1
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            'total_codes': result[0] or 0,
            'total_uses': result[1] or 0
        }
    
    def deactivate_invite_code(self, code):
        """Deactivate an invite code"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE invite_codes
            SET is_active = 0
            WHERE code = ?
        ''', (code,))
        
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    
    # ============ SIGNAL TRACKING ============
    
    def save_signal(self, signal_data):
        """Save a new signal to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO signals 
            (symbol, direction, entry_price, signal_time, bet_time, 
             expiry_time, confidence, indicators_triggered)
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
        
        logger.info(f"Signal saved: {signal_data['symbol']} - {signal_data['direction']}")
        return signal_id
    
    def update_signal_result(self, signal_id, result, profit_loss):
        """Update signal with result"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE signals 
            SET result = ?, profit_loss = ?
            WHERE id = ?
        ''', (result, profit_loss, signal_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Signal {signal_id} updated: {result} (${profit_loss:.2f})")
        
        # Update performance stats
        self.update_performance_stats()
    
    def update_performance_stats(self):
        """Update daily performance statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().date()
        
        # Get today's stats
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
            
            # Update or insert performance record
            cursor.execute('''
                INSERT OR REPLACE INTO performance 
                (date, total_signals, wins, losses, total_profit, win_rate)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (today, total, wins, losses, total_profit, win_rate))
            
            conn.commit()
        
        conn.close()
    
    # ============ STATISTICS ============
    
    def get_statistics(self, days=7):
        """Get bot performance statistics"""
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
        else:
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
        """Get active user count"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def get_all_users(self):
        """Get all users with details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, telegram_id, first_name, joined_at, last_active,
                   total_signals_received, total_trades, wins, losses
            FROM users 
            WHERE is_active = 1
            ORDER BY joined_at DESC
        ''')
        
        users = cursor.fetchall()
        conn.close()
        
        return [{
            'username': u[0],
            'telegram_id': u[1],
            'first_name': u[2],
            'joined_at': u[3],
            'last_active': u[4],
            'total_signals': u[5] or 0,
            'total_trades': u[6] or 0,
            'wins': u[7] or 0,
            'losses': u[8] or 0
        } for u in users]
    
    def get_user_by_telegram_id(self, telegram_id):
        """Get user by Telegram ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, telegram_id, first_name, joined_at, is_active
            FROM users 
            WHERE telegram_id = ?
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
        """Update user's last activity"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users
            SET last_active = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
        ''', (telegram_id,))
        
        conn.commit()
        conn.close()
    
    def get_today_signals(self):
        """Get count of signals today"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) 
            FROM signals 
            WHERE DATE(created_at) = DATE('now')
        ''')
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_today_profit(self):
        """Get today's profit"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COALESCE(SUM(profit_loss), 0)
            FROM signals 
            WHERE DATE(created_at) = DATE('now') AND result IS NOT NULL
        ''')
        
        profit = cursor.fetchone()[0]
        conn.close()
        return profit
    
    def get_top_symbols(self, limit=3):
        """Get top performing symbols"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                symbol,
                COUNT(*) as total,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                AVG(CASE WHEN result = 'WIN' THEN profit_loss ELSE 0 END) as avg_profit
            FROM signals
            WHERE result IS NOT NULL
            GROUP BY symbol
            ORDER BY wins DESC
            LIMIT ?
        ''', (limit,))
        
        symbols = cursor.fetchall()
        conn.close()
        
        return [{
            'symbol': s[0],
            'total': s[1],
            'wins': s[2],
            'win_rate': (s[2] / s[1] * 100) if s[1] > 0 else 0,
            'avg_profit': s[3] or 0
        } for s in symbols]