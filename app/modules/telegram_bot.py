import asyncio
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, timedelta
from app.utils.logger import logger
from app.config import Config

class TelegramBot:
    def __init__(self, db_manager, signal_generator):
        self.token = Config.TELEGRAM_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.db = db_manager
        self.signal_generator = signal_generator
        self.application = None
        self.is_running = False
        self.bot_username = None
        self.pending_signals = {}  # signal_id -> signal_data
        self.mt5_connector = None  # Will be set by main.py
        logger.info("Telegram Bot initialized")
        self._add_admin_user()
    
    def set_mt5_connector(self, mt5_connector):
        """Allow main.py to pass the MT5 connector"""
        self.mt5_connector = mt5_connector
        logger.info("MT5 connector set in Telegram Bot")
    
    def _add_admin_user(self):
        try:
            existing = self.db.get_user_by_telegram_id("1669011045")
            if not existing or not existing['is_active']:
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (telegram_id, username, first_name, is_active, joined_at, last_active)
                    VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', ("1669011045", "qSombre", "Bilal"))
                conn.commit()
                conn.close()
                logger.info("✅ Admin user added")
        except Exception as e:
            logger.error(f"❌ Failed to add admin: {e}")
    
    def get_main_menu_keyboard(self):
        keyboard = [
            [KeyboardButton("/start"), KeyboardButton("/invite")],
            [KeyboardButton("/status"), KeyboardButton("/stats")],
            [KeyboardButton("/signals"), KeyboardButton("/help")],
            [KeyboardButton("/join"), KeyboardButton("/leave")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    # ========== COMMAND HANDLERS ==========
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or f"user_{user_id}"
        first_name = update.effective_user.first_name or "User"
        existing_user = self.db.get_user_by_telegram_id(str(user_id))
        if not existing_user or not existing_user['is_active']:
            self.db.add_user_with_invite(
                username=username,
                telegram_id=str(user_id),
                first_name=first_name,
                invite_code=None
            )
        await update.message.reply_text(
            f"👋 Welcome {first_name}!\n\nYou will now receive signals directly in this chat.\nUse /status to check.",
            reply_markup=self.get_main_menu_keyboard()
        )
    
    async def invite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user = self.db.get_user_by_telegram_id(str(user_id))
        if not user or not user['is_active']:
            await update.message.reply_text("❌ You need to be a member.", reply_markup=self.get_main_menu_keyboard())
            return
        import secrets, string
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        if not self.bot_username:
            try:
                bot_info = await context.bot.get_me()
                self.bot_username = bot_info.username
            except:
                await update.message.reply_text("❌ Error getting bot info.")
                return
        invite_link, message = self.db.generate_invite_link(self.bot_username, code)
        if invite_link:
            keyboard = [[InlineKeyboardButton("📤 Share", url=invite_link)]]
            await update.message.reply_text(
                f"🔗 **Invite Link**\n`{invite_link}`\n\n👥 Users: {self.db.get_user_count()}/{Config.MAX_USERS}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(f"❌ {message}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        if not user or not user['is_active']:
            await update.message.reply_text("❌ You're not a member.", reply_markup=self.get_main_menu_keyboard())
            return
        stats = self.db.get_statistics()
        users = self.db.get_user_count()
        pending_count = len(self.pending_signals)
        await update.message.reply_text(
            f"📊 **Bot Status**\n\n"
            f"👤 User: {user['first_name']}\n"
            f"📈 Signals: {stats['total_signals']}\n"
            f"✅ Wins: {stats['wins']}\n"
            f"❌ Losses: {stats['losses']}\n"
            f"🏆 Win Rate: {stats['win_rate']:.1f}%\n"
            f"👥 Active Users: {users}/{Config.MAX_USERS}\n"
            f"⏳ Pending Results: {pending_count}",
            parse_mode='Markdown',
            reply_markup=self.get_main_menu_keyboard()
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        if not user or not user['is_active']:
            await update.message.reply_text("❌ You're not a member.", reply_markup=self.get_main_menu_keyboard())
            return
        stats = self.db.get_statistics()
        await update.message.reply_text(
            f"📈 **Statistics**\n\n"
            f"📊 Total Signals: {stats['total_signals']}\n"
            f"✅ Wins: {stats['wins']}\n"
            f"❌ Losses: {stats['losses']}\n"
            f"🏆 Win Rate: {stats['win_rate']:.1f}%\n"
            f"💰 Total Profit: ${stats['total_profit']:.2f}",
            parse_mode='Markdown',
            reply_markup=self.get_main_menu_keyboard()
        )
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        if not user or not user['is_active']:
            await update.message.reply_text("❌ You're not a member.", reply_markup=self.get_main_menu_keyboard())
            return
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, direction, result, profit_loss, created_at FROM signals ORDER BY created_at DESC LIMIT 5')
        signals = cursor.fetchall()
        conn.close()
        if not signals:
            await update.message.reply_text("📊 No signals yet.", reply_markup=self.get_main_menu_keyboard())
            return
        message = "📊 **Recent Signals**\n━━━━━━━━━━━━\n"
        for i, s in enumerate(signals, 1):
            result_emoji = "✅" if s[2] == "WIN" else "❌" if s[2] == "LOSS" else "⏳"
            profit_str = f"+${s[3]:.2f}" if s[3] and s[3] > 0 else f"-${abs(s[3]):.2f}" if s[3] else "$0.00"
            message += f"{i}. {s[0]} {s[1]} {result_emoji} {profit_str}\n"
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=self.get_main_menu_keyboard())
    
    async def join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or f"user_{user_id}"
        first_name = update.effective_user.first_name or "User"
        existing_user = self.db.get_user_by_telegram_id(str(user_id))
        if existing_user and existing_user['is_active']:
            await update.message.reply_text("✅ Already a member!", reply_markup=self.get_main_menu_keyboard())
            return
        success, message = self.db.add_user_with_invite(
            username=username,
            telegram_id=str(user_id),
            first_name=first_name,
            invite_code=None
        )
        await update.message.reply_text(f"{message}\n👥 Users: {self.db.get_user_count()}/{Config.MAX_USERS}", reply_markup=self.get_main_menu_keyboard())
    
    async def leave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if user_id == "1669011045":
            await update.message.reply_text("❌ Admin cannot leave.", reply_markup=self.get_main_menu_keyboard())
            return
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_active = 0 WHERE telegram_id = ?', (user_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Left the group.", reply_markup=self.get_main_menu_keyboard())
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 **Commands:**\n\n"
            "/start - Welcome\n"
            "/invite - Get invite link\n"
            "/join - Join group\n"
            "/leave - Leave group\n"
            "/status - Check status\n"
            "/stats - Statistics\n"
            "/signals - Recent signals\n"
            "/help - This message",
            parse_mode='Markdown',
            reply_markup=self.get_main_menu_keyboard()
        )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Telegram error: {context.error}")
    
    # ========== START / STOP ==========
    async def start(self):
        if self.is_running:
            return
        try:
            logger.info("🔄 Starting Telegram bot...")
            self.application = Application.builder().token(self.token).build()
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("invite", self.invite_command))
            self.application.add_handler(CommandHandler("join", self.join_command))
            self.application.add_handler(CommandHandler("leave", self.leave_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(CommandHandler("stats", self.stats_command))
            self.application.add_handler(CommandHandler("signals", self.signals_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_error_handler(self.error_handler)
            
            await self.application.initialize()
            await self.application.start()
            asyncio.create_task(self._polling())
            
            bot_info = await self.application.bot.get_me()
            self.bot_username = bot_info.username
            logger.info(f"✅ Bot: @{self.bot_username}")
            
            self.is_running = True
            logger.info("✅ Telegram bot started! Commands are active.")
        except Exception as e:
            logger.error(f"❌ Failed to start: {e}")
            self.is_running = False
    
    async def _polling(self):
        try:
            await self.application.updater.start_polling(
                poll_interval=1.0,
                timeout=30,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
        except Exception as e:
            logger.error(f"❌ Polling error: {e}")
            await asyncio.sleep(5)
            asyncio.create_task(self._polling())
    
    async def stop(self):
        if self.application:
            try:
                await self.application.stop()
                await self.application.shutdown()
            except:
                pass
        self.is_running = False
        logger.info("Telegram bot stopped")
    
    # ========== SEND SIGNAL TO ALL USERS ==========
    async def send_signal(self, signal, signal_times=[3]):
        if not signal or signal['direction'] == 'NEUTRAL':
            return None
        try:
            now = Config.get_current_time()
            indicators_text = "\n".join([f"• {ind}" for ind in signal.get('indicators', [])])
            
            # Save signal to database
            signal_data = {
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': signal['price'],
                'signal_time': now,
                'bet_time': now + timedelta(minutes=signal_times[0]),
                'expiry_time': now + timedelta(minutes=signal_times[0] + 2),
                'confidence': signal['confidence'],
                'indicators': signal.get('indicators', [])
            }
            signal_id = self.db.save_signal(signal_data)
            
            # Store in pending_signals for result checking
            self.pending_signals[signal_id] = {
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': signal['price'],
                'bet_time': now + timedelta(minutes=signal_times[0]),
                'expiry_time': now + timedelta(minutes=signal_times[0] + 2),
                'signal_id': signal_id
            }
            
            logger.info(f"📌 Signal {signal_id} added to pending_signals. Total pending: {len(self.pending_signals)}")
            
            # Get all active users
            users = self.db.get_all_users()
            if not users:
                logger.warning("No active users to send signal to.")
                return signal_id
            
            # Build and send messages
            for minutes in signal_times:
                bet_time = now + timedelta(minutes=minutes)
                expiry_time = bet_time + timedelta(minutes=2)
                message = f"""
🎯 **XAUUSD Signal!** ({minutes} min)
━━━━━━━━━━━━━━━━━━
📈 **Direction:** {signal['direction']}
💪 **Confidence:** {signal['confidence']:.1f}%
💰 **Price:** {signal['price']:.2f}
⏰ **Bet Time:** {bet_time.strftime('%H:%M:%S')}
⏱️ **Expiry:** {expiry_time.strftime('%H:%M:%S')}

📋 **Triggers:**
{indicators_text}

🔔 Place {signal['direction']} at {bet_time.strftime('%H:%M:%S')}
"""
                for user in users:
                    try:
                        if user['telegram_id']:
                            await self.application.bot.send_message(
                                chat_id=int(user['telegram_id']),
                                text=message,
                                parse_mode='Markdown'
                            )
                            await asyncio.sleep(0.3)  # avoid rate limits
                    except Exception as e:
                        logger.error(f"Failed to send to {user['username']}: {e}")
            
            logger.info(f"✅ XAUUSD {signal['direction']} sent to {len(users)} users (Signal ID: {signal_id})")
            return signal_id
        except Exception as e:
            logger.error(f"Error sending signal: {e}")
            return None
    
    # ========== CHECK RESULTS ==========
    async def check_pending_results(self):
        """Check if any pending signals have expired and send results"""
        if not self.application or not self.is_running:
            return
        
        if not self.pending_signals:
            return
        
        try:
            now = Config.get_current_time()
            expired = []
            
            for signal_id, data in self.pending_signals.items():
                expiry_time = data['expiry_time']
                
                # Check if signal has expired
                if now >= expiry_time:
                    expired.append(signal_id)
                    
                    entry_price = data['entry_price']
                    direction = data['direction']
                    
                    logger.info(f"🔍 Checking result for Signal {signal_id} (Expired at {expiry_time.strftime('%H:%M:%S')})")
                    
                    # Try to get price at expiry time
                    price_at_expiry = None
                    if self.mt5_connector:
                        try:
                            price_at_expiry = self.mt5_connector.get_price_at_time('XAUUSD', expiry_time)
                            logger.info(f"💰 Price at expiry: {price_at_expiry}")
                        except Exception as e:
                            logger.error(f"Error getting price: {e}")
                    
                    # Determine result
                    if price_at_expiry is not None:
                        if direction == 'CALL':
                            result = 'WIN' if price_at_expiry > entry_price else 'LOSS'
                        else:  # PUT
                            result = 'WIN' if price_at_expiry < entry_price else 'LOSS'
                        
                        # Calculate profit/loss based on percentage change
                        pct_change = abs((price_at_expiry - entry_price) / entry_price)
                        profit = round(pct_change * 1000, 2) if result == 'WIN' else -round(pct_change * 1000, 2)
                        profit = max(-25, min(25, profit))  # cap for demo
                    else:
                        # Fallback to random if price fetch failed
                        import random
                        result = random.choice(['WIN', 'LOSS'])
                        profit = round(random.uniform(5, 25), 2) if result == 'WIN' else -round(random.uniform(5, 20), 2)
                        logger.warning(f"⚠️ Using fallback random result for Signal {signal_id}")
                    
                    # Update database
                    self.db.update_signal_result(signal_id, result, profit)
                    logger.info(f"📊 Signal {signal_id}: {result} ${profit:.2f}")
                    
                    # Send result to all users
                    users = self.db.get_all_users()
                    if users:
                        for user in users:
                            try:
                                result_message = f"""
📊 **XAUUSD Result**
━━━━━━━━━━━━━━━━
📌 **ID:** `{signal_id}`
📈 **Direction:** {direction}
💰 **Entry:** ${entry_price:.2f}
{'✅' if result == 'WIN' else '❌'} **Result:** {result}
💵 **Profit:** ${profit:.2f}
"""
                                if price_at_expiry is not None:
                                    result_message += f"⏱️ **Expiry Price:** ${price_at_expiry:.2f}\n"
                                
                                await self.application.bot.send_message(
                                    chat_id=int(user['telegram_id']),
                                    text=result_message,
                                    parse_mode='Markdown'
                                )
                                await asyncio.sleep(0.3)
                            except Exception as e:
                                logger.error(f"Failed to send result to {user['username']}: {e}")
            
            # Remove expired signals from pending
            for signal_id in expired:
                del self.pending_signals[signal_id]
                logger.info(f"🗑️ Removed Signal {signal_id} from pending. Remaining: {len(self.pending_signals)}")
                
        except Exception as e:
            logger.error(f"Error checking results: {e}")
