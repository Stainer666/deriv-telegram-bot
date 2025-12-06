import os
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler

# ===== LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== ENV VARIABLES =====
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DERIV_API_TOKEN = os.environ.get("DERIV_API_TOKEN")
RAILWAY_URL = os.environ.get("RAILWAY_URL")  # Railway auto-provides this

if not BOT_TOKEN or not DERIV_API_TOKEN or not RAILWAY_URL:
    logger.error("Missing environment variables!")
    exit(1)

# ===== FLASK APP =====
app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# ===== DERIV API MOCK =====
class MockDerivAPI:
    def predict_next_digit(self):
        import random
        return random.randint(0, 9)
    def execute_trade(self, stake=10, contract="DIGITDIFF 4"):
        return f"Mock trade executed: {contract} with stake {stake}"

deriv = MockDerivAPI()

# ===== COMMAND HANDLERS =====
def start(update, context):
    update.message.reply_text("Hello! Deriv bot is online. 🤖")

def help_command(update, context):
    update.message.reply_text(
        "Available commands:\n"
        "/start - Start bot\n"
        "/help - Show help\n"
        "/predict - Predict next digit\n"
        "/trade - Execute a trade"
    )

def predict(update, context):
    next_digit = deriv.predict_next_digit()
    update.message.reply_text(f"Predicted next digit: {next_digit}")

def trade(update, context):
    result = deriv.execute_trade()
    update.message.reply_text(f"Trade executed: {result}")

# Register commands
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("predict", predict))
dispatcher.add_handler(CommandHandler("trade", trade))

# ===== WEBHOOK ROUTE =====
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"

# ===== MAIN =====
if __name__ == "__main__":
    # Set Telegram webhook
    webhook_url = f"{RAILWAY_URL}/{BOT_TOKEN}"
    bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set to {webhook_url}")
    
    # Start Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
