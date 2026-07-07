import asyncio
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import json
from datetime import datetime, timedelta
from app.utils.logger import logger
from app.config import Config

class TelegramBot:
    """Telegram Bot for sending signals and handling commands with invite system"""
    
    def __init__(self, db_manager, signal_generator):
        self.token = Config.TELEGRAM_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.db = db_manager
        self.signal_generator = signal_generator
        self.bot = Bot(token=self.token)
        self.application = None
        self.is_running = False
        self.bot_username = None
        logger.info("Telegram Bot initialized with Invite System")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - with invite support"""
        user_id = update.effective_user.id
        username = update.effective_user.username or f"user_{user_id}"
        first_name = update.effective_user.first_name or "User"
        
        # Check if user already exists
        existing_user = self.db.get_user_by_telegram_id(str(user_id))
        
        if existing_user and existing_user['is_active']:
            await update.message.reply_text(
                f"👋 Welcome back {first_name}!\n\n"
                "You're already a member of the signal group.\n"
                "Use /status to check your current status."
            )
            return
        
        # Check if this is an invite
        if context.args and context.args[0].startswith('invite_'):
            invite_code = context.args[0].replace('invite_', '')
            logger.info(f"User {username} joining with invite code: {invite_code}")
            
            # Add user with invite
            success, message = self.db.add_user_with_invite(
                username=username,
                telegram_id=str(user_id),
                first_name=first_name,
                invite_code=invite_code
            )
            
            # Send response
            welcome_message = f"""
{message}

📊 **What you can do:**
/status - Check bot status
/stats - View performance statistics
/signals - Last 5 signals
/help - Show all commands
/invite - Get invite link to share

📈 **Signals will be sent automatically!**
━━━━━━━━━━━━━━━━━━
⚠️ **Risk Warning:**
• Trading involves risk
• Only trade with money you can afford to lose
• Past performance doesn't guarantee future results
• Always test on demo first!
"""
            
            await update.message.reply_text(welcome_message, parse_mode='Markdown')
            return
        
        # If no invite code, send welcome with invite info
        welcome_message = f"""
👋 Welcome {first_name}!

This is a private signal bot. To join the group, you need an invite link.

📌 **To get an invite link:**
1. Contact the bot administrator
2. Or use a shared invite link

If you already have a link, use:
/start invite_YOUR_CODE

🔒 **Current Status:**
👥 Users: {self.db.get_user_count()}/{Config.MAX_USERS}
📊 Active: ✅ Online
"""
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def invite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate an invite link"""
        user_id = update.effective_user.id
        
        # Check if user is already a member
        user = self.db.get_user_by_telegram_id(str(user_id))
        if not user or not user['is_active']:
            await update.message.reply_text(
                "❌ You need to be a member to generate invite links.\n"
                "Use a valid invite link to join first."
            )
            return
        
        # Generate invite link
        if not self.bot_username:
            # Get bot username
            bot_info = await self.bot.get_me()
            self.bot_username = bot_info.username
        
        # Generate a random code
        import secrets
        import string
        alphabet = string.ascii_uppercase + string.digits
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        
        invite_link, message = self.db.generate_invite_link(self.bot_username, code)
        
        if invite_link:
            # Create share button
            keyboard = [
                [InlineKeyboardButton("📤 Share Invite Link", url=invite_link)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔗 **Your Invite Link**\n\n"
                f"`{invite_link}`\n\n"
                f"📌 **Share this link with anyone you want to join!**\n"
                f"⚠️ Each link works for **1 person only**.\n"
                f"👥 Current users: {self.db.get_user_count()}/{Config.MAX_USERS}\n\n"
                f"💡 You can generate more links anytime.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(f"❌ {message}")
    
    async def join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manual join command (backward compatibility)"""
        user_id = update.effective_user.id
        username = update.effective_user.username or f"user_{user_id}"
        first_name = update.effective_user.first_name or "User"
        
        # Check if user already exists
        existing_user = self.db.get_user_by_telegram_id(str(user_id))
        if existing_user and existing_user['is_active']:
            await update.message.reply_text("✅ You're already a member!")
            return
        
        # Try to add with default invite
        success, message = self.db.add_user_with_invite(
            username=username,
            telegram_id=str(user_id),
            first_name=first_name,
            invite_code=None  # No invite code - will fail if group is full
        )
        
        if success:
            await update.message.reply_text(
                f"{message}\n\n"
                f"👥 Users: {self.db.get_user_count()}/{Config.MAX_USERS}\n"
                "📊 Start receiving signals!"
            )
        else:
            await update.message.reply_text(
                f"❌ {message}\n\n"
                "💡 You need an invite link to join. Contact the bot administrator."
            )
    
    async def leave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /leave command"""
        user_id = str(update.effective_user.id)
        
        # Deactivate user
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET is_active = 0 
            WHERE telegram_id = ?
        ''', (user_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            "✅ You have left the signal group.\n\n"
            "If you want to rejoin, you'll need a new invite link."
        )
        logger.info(f"User {user_id} left the group")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = str(update.effective_user.id)
        
        # Check if user is active
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user['is_active']:
            await update.message.reply_text(
                "❌ You're not a member of the signal group.\n"
                "Use an invite link to join: /invite"
            )
            return
        
        # Update user activity
        self.db.update_user_activity(user_id)
        
        stats = self.db.get_statistics()
        users = self.db.get_user_count()
        invite_stats = self.db.get_invite_stats()
        
        status_message = f"""
📊 **Bot Status**
━━━━━━━━━━━━━━━━━━
👤 **User:** {user['first_name']}
📅 **Joined:** {user['joined_at'][:10]}
🟢 **Status:** Active

📈 **Performance (Last 7 days):**
• Total Signals: {stats['total_signals']}
• Wins: {stats['wins']}
• Losses: {stats['losses']}
• Win Rate: {stats['win_rate']:.1f}%
• Total Profit: ${stats['total_profit']:.2f}

👥 **Group Stats:**
• Active Users: {users}/{Config.MAX_USERS}
• Invite Links: {invite_stats['total_codes']}
• Total Joins: {invite_stats['total_uses']}

⚙️ **Monitoring:**
• Symbols: {', '.join(Config.SYMBOLS)}
• Timeframe: {Config.TIMEFRAME}
• Min Confidence: {Config.MIN_CONFIDENCE}%
• Signal Times: {', '.join(map(str, Config.SIGNAL_TIMES))} min

📌 **Commands:**
/invite - Generate invite link
/status - Check status
/stats - View statistics
/signals - Last 5 signals
/help - Show all commands
/leave - Leave the group
"""
        
        await update.message.reply_text(status_message, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        user_id = str(update.effective_user.id)
        
        # Check if user is active
        user = self.db.get_user_by_telegram_id(user_id)
        if not user or not user['is_active']:
            await update.message.reply_text(
                "❌ You're not a member. Use /invite to join."
            )
            return
        
        stats = self.db.get_statistics()
        top_symbols = self.db.get_top_symbols(3)
        
        stats_message = f"""
📈 **Performance Statistics**
━━━━━━━━━━━━━━━━━━
📊 **Last 7 Days:**
• Total Signals: {stats['total_signals']}
• ✅ Wins: {stats['wins']}
• ❌ Losses: {stats['losses']}
• 🏆 Win Rate: {stats['win_rate']:.1f}%
• 💰 Total Profit: ${stats['total_profit']:.2f}

📊 **Averages:**
• 💚 Avg Win: ${stats['avg_win']:.2f}
• 💔 Avg Loss: ${stats['avg_loss']:.2f}
• 📈 Risk/Reward: {stats['avg_win']/abs(stats['avg_loss']):.2f} if stats['avg_loss'] != 0 else "N/A"

🏆 **Top Performing Symbols:**
"""
        
        for i, symbol in enumerate(top_symbols, 1):
            stats_message += f"{i}. {symbol['symbol']}: {symbol['win_rate']:.1f}% win rate ({symbol['wins']}/{symbol['total']})\n"
        
        stats_message += f"""
⚡ **Today:**
• Signals: {self.db.get_today_signals()}
• Profit: ${self.db.get_today_profit():.2f}

📌 **Your Stats:**
• Total Trades: {stats['total_signals']}
• Your Win Rate: {stats['win_rate']:.1f}%
"""
        
        await update.message.reply_text(stats_message, parse_mode='Markdown')
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /signals command"""
        user_id = str(update.effective_user.id)
        
        # Check if user is active
        user = self.db.get_user_by_telegram_id(user_id)
        if not user or not user['is_active']:
            await update.message.reply_text(
                "❌ You're not a member. Use /invite to join."
            )
            return
        
        # Get last 5 signals
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT symbol, direction, entry_price, result, profit_loss, created_at
            FROM signals
            ORDER BY created_at DESC
            LIMIT 5
        ''')
        
        signals = cursor.fetchall()
        conn.close()
        
        if not signals:
            await update.message.reply_text(
                "📊 No signals yet.\n"
                "The bot is analyzing the markets and will send signals when conditions are right."
            )
            return
        
        message = "📊 **Recent Signals**\n━━━━━━━━━━━━━━━━\n"
        
        for i, signal in enumerate(signals, 1):
            symbol, direction, price, result, profit, time_str = signal
            result_emoji = "✅ WIN" if result == "WIN" else "❌ LOSS" if result == "LOSS" else "⏳ Pending"
            profit_str = f"+${profit:.2f}" if profit and profit > 0 else f"-${abs(profit):.2f}" if profit else "$0.00"
            
            message += f"""
**{i}. {symbol}**
Direction: {direction}
Price: {price:.4f}
Result: {result_emoji}
Profit: {profit_str}
Time: {time_str[:16]}
"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
🤖 **Signal Bot Help**

**Commands:**
/start - Start the bot (use with invite)
/invite - Generate an invite link
/join - Join the group (if you have access)
/leave - Leave the group
/status - Check bot status
/stats - View performance statistics
/signals - Last 5 signals
/help - Show this message

**📋 How to Join:**
1. Get an invite link from an existing member
2. Click the link or use: /start invite_CODE
3. You're automatically added!

**📊 How It Works:**
1. Bot analyzes market data using 8+ indicators
2. When a strong signal is detected, it's sent to the group
3. You receive alerts with exact entry times (3 & 5 minutes ahead)
4. Place trades at the specified time
5. Bot tracks WIN/LOSS and updates statistics

**Signal Format:**
📊 Symbol: USDJPY-OTC
📈 Direction: CALL/PUT
💪 Confidence: 65-75%
💰 Price: 145.23
⏰ Bet Time: 14:33:00

**⚠️ Risk Warning:**
• Trading involves risk
• Past performance doesn't guarantee future results
• Only trade with money you can afford to lose
• Always test on demo first!

**📞 Questions?** Contact your bot administrator
"""
        
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Telegram error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred. Please try again later."
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle non-command messages"""
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        
        # Update user activity if they're a member
        if user and user['is_active']:
            self.db.update_user_activity(user_id)
    
    def start(self):
        """Start the Telegram bot"""
        if self.is_running:
            return
        
        # Create application
        self.application = Application.builder().token(self.token).build()
        
        # Get bot username
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot_info = loop.run_until_complete(self.bot.get_me())
        self.bot_username = bot_info.username
        logger.info(f"Bot username: @{self.bot_username}")
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("invite", self.invite_command))
        self.application.add_handler(CommandHandler("join", self.join_command))
        self.application.add_handler(CommandHandler("leave", self.leave_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("signals", self.signals_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Add message handler for non-commands
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
        
        # Start polling
        self.application.run_polling()
        self.is_running = True
        logger.info(f"Telegram bot started successfully with invite system. Bot username: @{self.bot_username}")
    
    def stop(self):
        """Stop the Telegram bot"""
        if self.application:
            self.application.stop()
        self.is_running = False
        logger.info("Telegram bot stopped")
    
    def send_signal(self, signal, signal_times=[3, 5]):
        """Send a trading signal to Telegram"""
        if not signal or signal['direction'] == 'NEUTRAL':
            return
        
        try:
            # Calculate bet times
            now = datetime.now()
            bet_times = [now + timedelta(minutes=t) for t in signal_times]
            
            # Format indicators
            indicators_text = "\n".join([f"• {ind}" for ind in signal.get('indicators', [])])
            
            for i, bet_time in enumerate(bet_times):
                minutes = signal_times[i]
                bet_time_str = bet_time.strftime("%H:%M:%S")
                expiry_time = (bet_time + timedelta(minutes=2)).strftime("%H:%M:%S")
                
                message = f"""
🎯 **Signal Alert!** (Alert {i+1}/{len(bet_times)})
━━━━━━━━━━━━━━━━━━
📊 **Symbol:** {signal['symbol']}-OTC
📈 **Direction:** {signal['direction']}
💪 **Confidence:** {signal['confidence']:.1f}%
💰 **Entry Price:** {signal['price']:.4f}
⏰ **Bet Time:** {bet_time_str}
⏱️ **Expiry:** {expiry_time}

📋 **Signal Triggers:**
{indicators_text}

🔔 **Action Required:**
Place **{signal['direction']}** at **{bet_time_str}**
⚠️ Set expiry to **{expiry_time}** ({minutes+2} minutes from trade)

📊 **Score:** {signal.get('score', 0)}
━━━━━━━━━━━━━━━━━━
#Signal #{signal['symbol']} #{signal['direction']}
"""
                
                # Send message to group
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                )
                
                logger.info(f"Signal sent to Telegram: {signal['symbol']} - {signal['direction']}")
                
            # Store in database
            signal_data = {
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': signal['price'],
                'signal_time': datetime.now(),
                'bet_time': bet_times[0],
                'expiry_time': bet_times[0] + timedelta(minutes=2),
                'confidence': signal['confidence'],
                'indicators': signal.get('indicators', [])
            }
            
            signal_id = self.db.save_signal(signal_data)
            logger.info(f"Signal saved to database with ID: {signal_id}")
            
            return signal_id
            
        except Exception as e:
            logger.error(f"Error sending signal to Telegram: {e}")
            return None
    
    def send_test_signal(self):
        """Send a test signal for demonstration"""
        test_signal = {
            'symbol': 'USDJPY',
            'direction': 'CALL',
            'confidence': 72.5,
            'price': 145.23,
            'indicators': ['MA Bullish Crossover', 'RSI Oversold', 'MACD Bullish'],
            'score': 45,
            'timestamp': datetime.now()
        }
        
        self.send_signal(test_signal)
        logger.info("Test signal sent")