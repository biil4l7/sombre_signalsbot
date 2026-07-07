# 🚀 Sombre Signals Bot

Professional trading signal bot for Telegram with auto-join invite system.

## Features

- ✅ Automated trading signals using 8+ technical indicators
- ✅ Telegram integration with instant alerts
- ✅ Auto-join invite system (no passwords needed)
- ✅ User management (max 6 users)
- ✅ Win/Loss tracking
- ✅ Performance statistics
- ✅ SQLite database for full tracking
- ✅ Railway deployment ready

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/invite` | Generate invite link |
| `/join` | Join the group |
| `/leave` | Leave the group |
| `/status` | Check status |
| `/stats` | View statistics |
| `/signals` | Last 5 signals |
| `/help` | Show help |

## Deploy on Railway

1. Push to GitHub
2. Connect to Railway
3. Add environment variables
4. Deploy!

## Environment Variables

- `TELEGRAM_TOKEN` - Your bot token from @BotFather
- `TELEGRAM_CHAT_ID` - Your Telegram group ID
- `MAX_USERS` - Max users (default 6)
- `MIN_CONFIDENCE` - Min confidence % (default 60)
- `SIGNAL_TIMES` - Minutes before trade (default 3,5)
- `TIMEFRAME` - Chart timeframe (default M1)
- `SYMBOLS` - Symbols to monitor

## Disclaimer

Trading involves risk. Past performance does not guarantee future results.
